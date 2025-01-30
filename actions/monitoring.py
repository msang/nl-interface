import os
from solaredge_interface.api.SolarEdgeAPI import SolarEdgeAPI
from time import localtime, strftime
from typing import Text
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())
SE_APIKEY = os.environ.get("SOLAREDGE_KEY")  
SITE_ID= os.environ.get("SOLAREDGE_SITE_ID") 


class EnergyMonitoring():
    
    def __init__(self) -> None:
        api = SolarEdgeAPI(api_key=SE_APIKEY, datetime_response=True, pandas_response=True)
        #print(api)
        #print(api.get_site_overview(str(SITE_ID)))
        data = api.get_site_current_power_flow(SITE_ID).data
        today = f"{strftime('%Y-%m-%d', localtime())} 00:00:00"
        now=strftime("%Y-%m-%d %H:%M:%S", localtime())
        #print(SITE_ID, data)
        energy = api.get_site_energy_details(SITE_ID, today, now).pandas 
        meter = energy['energyDetails.meters.type']
        self.daily_production = energy.loc[meter == 'Production', 'energyDetails.meters.values.value'].values[0]* 0.001
        self.daily_purchased = energy.loc[meter == 'Purchased', 'energyDetails.meters.values.value'].values[0]* 0.001
        self.daily_feed_in = energy.loc[meter == 'FeedIn', 'energyDetails.meters.values.value'].values[0]* 0.001
        self.daily_consumption = energy.loc[meter == 'Consumption', 'energyDetails.meters.values.value'].values[0]* 0.001
        self.daily_self_consumption = energy.loc[meter == 'SelfConsumption', 'energyDetails.meters.values.value'].values[0]* 0.001
        self.current = data["siteCurrentPowerFlow"]
        self.power_flows = self.current["connections"]
        self.pv_power = self.current["PV"]["currentPower"]
        self.storage_level = self.current["STORAGE"]["chargeLevel"]
        
        bess_statuses = {"Charging": "in carica", "Discharging":"in scarica", "Idle": "inattiva"}
        self.storage_status = bess_statuses.get(self.current["STORAGE"]["status"]) 
        

    def get_consumption_info(self):

        pv_to_load=0.0
        bess_to_load=0.0
        grid_to_load=0.0

        for flow in self.power_flows:
            source = flow['from']
            destination = flow['to']

            if source == "PV" and destination == "Load":
                pv_to_load = self.current["LOAD"]["currentPower"]
            if source == "STORAGE" and destination == "Load":
                bess_to_load = self.current["STORAGE"]["currentPower"]
            if source == "GRID" and destination == "Load":
                grid_to_load = self.current['GRID']['currentPower']
        
        daily = f"- energia utilizzata dalla casa in tutta la giornata: {self.daily_consumption:.2f} kWh\n- energia acquistata dalla rete in tutta la giornata: {self.daily_purchased:.2f} kWh\n"

        tot_current = pv_to_load + bess_to_load + grid_to_load
        current = f"- potenza istantanea fornita dall'impianto solare: {pv_to_load:.2f} kW\n- potenza istantanea fornita dalla batteria: {bess_to_load:.2f} kW\n- potenza istantanea fornita dalla rete: {grid_to_load:.2f} kW\n- potenza totale utilizzata: {tot_current:.2f} kW"
        
        return daily + current
         
     
    def get_production_info(self): 

        pv_to_grid=0.0
        pv_to_bess=0.0
        
        for flow in self.power_flows:
            source = flow['from']
            destination = flow['to']

            if source == "LOAD" and destination == "Grid":                
                pv_to_grid = self.current['GRID']['currentPower']
            if source == "PV" and destination == "Storage":   
                pv_to_bess = self.current["STORAGE"]["currentPower"]   

        daily = f"- energia totale prodotta dai pannelli in tutta la giornata: {self.daily_production:.2f} kWh\n- auto-consumo della giornata: {self.daily_self_consumption:.2f}kWh\n- energia immessa in rete in tutta la giornata: {self.daily_feed_in:.2f}kWh\n"

        current = f"- potenza prodotta ora dall'impianto fotovoltaico: {self.pv_power:.2f}kW\n- stato di carica attuale della batteria: {self.storage_level}%\n- status della batteria: {self.storage_status}\n- potenza immessa dal fotovolatico alla batteria: {pv_to_bess:.2f} kW\n- potenza immessa dal fotovoltaico alla rete: {pv_to_grid:.2f}\n"

        return daily + current
     

if __name__ == "__main__":
    em = EnergyMonitoring()
    print(em.__dict__)
    #print(em.get_consumption_info())
    #print(em.get_production_info())

     