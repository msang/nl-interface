from collections import defaultdict
from datetime import datetime, timedelta
from os.path import join, dirname
from solaredge_interface.api.SolarEdgeAPI import SolarEdgeAPI
from time import localtime, strftime
from typing import Text
from dotenv import load_dotenv
import os
import pandas as pd

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)
APIKEY = os.environ.get("SOLAREDGE_KEY")
SITEID = os.environ.get("SOLAREDGE_SITE_ID")


class EnergyMonitoring():
    
    """
    def __init__(self) -> None:
        api = SolarEdgeAPI(api_key=APIKEY, datetime_response=True, pandas_response=True)
        #print(api)
        #print(api.get_site_overview(str(SITE_ID)))
        data = api.get_site_current_power_flow(SITEID).data
        today = f"{strftime('%Y-%m-%d', localtime())} 00:00:00"
        now=strftime("%Y-%m-%d %H:%M:%S", localtime())
        #print(SITE_ID, data)
        energy = api.get_site_energy_details(SITEID, today, now).pandas 
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
    """

    bess_statuses = {"Charging": "in carica", "Discharging": "in scarica", "Idle": "inattiva"}

    def __init__(self, api_key: str = APIKEY, site_id: str = SITEID) -> None:
        """Inizializza la classe con i parametri di accesso all'API e prepara gli attributi della classe."""
        self.api_key = api_key
        self.site_id = site_id
        try:
            self.api = SolarEdgeAPI(api_key=self.api_key, datetime_response=True, pandas_response=True)
            #print(self.api)
        except:
            self.api = None

        # Attributi inizializzati a None, verranno impostati dai metodi setter
        self.daily_production = None
        self.daily_purchased = None
        self.daily_feed_in = None
        self.daily_consumption = None
        self.daily_self_consumption = None
        self.current = None
        self.power_flows = None
        self.pv_power = None
        self.storage_level = None
        self.storage_status = None

    def fetch_data(self) -> None:
        """Recupera i dati attuali dal sito SolarEdge e imposta gli attributi della classe."""
        self.current = self.api.get_site_current_power_flow(self.site_id).data["siteCurrentPowerFlow"]
        self.power_flows = self.current["connections"]
        self.pv_power = self.current["PV"]["currentPower"]
        self.storage_level = self.current["STORAGE"]["chargeLevel"]
        self.storage_status = self.bess_statuses.get(self.current["STORAGE"]["status"], "Stato sconosciuto")

    def fetch_energy_details(self) -> None:
        """Recupera i dettagli energetici giornalieri e imposta gli attributi corrispondenti."""
        today = f"{strftime('%Y-%m-%d', localtime())} 00:00:00"
        now = strftime("%Y-%m-%d %H:%M:%S", localtime())

        energy = self.api.get_site_energy_details(self.site_id, today, now).pandas
        meter = energy['energyDetails.meters.type']

        self.daily_production = self._get_energy_value(energy, meter, 'Production')
        self.daily_purchased = self._get_energy_value(energy, meter, 'Purchased')
        self.daily_feed_in = self._get_energy_value(energy, meter, 'FeedIn')
        self.daily_consumption = self._get_energy_value(energy, meter, 'Consumption')
        self.daily_self_consumption = self._get_energy_value(energy, meter, 'SelfConsumption')

    @staticmethod
    def _get_energy_value(energy, meter, key: str) -> float:
        """Metodo di utilità per estrarre il valore energetico corrispondente a una chiave specifica."""
        value = energy.loc[meter == key, 'energyDetails.meters.values.value'].values
        return value[0] * 0.001 if len(value) > 0 else 0.0

    def update_all_data(self) -> None:
        """Aggiorna tutti i dati chiamando i metodi appropriati."""
        self.fetch_data()
        self.fetch_energy_details()
        

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

    #----------------------------------------
    # recupero dati storici (in W) di batteria, produzione e consumi
    #----------------------------------------

    def get_historic_bess_data(self, end_time):
        """ 
        Fa una chiamata all'api per il periodo richiesto e salva in un dataframe. 
        Interpola i dati alla risoluzione di 1 minuto. 
        Comportamento simile anche per metodi di recupero dati di produzione e consumi.
        """
        start_time = end_time - timedelta(minutes=35)#vado a ritroso per recuperare i dati dell'ultima mezz'ora partendo da ora (aumento il delta per assicuarrmi che ci siano poi 30 valori finali effettivi
        bess_ch_dis = defaultdict(list)
 
        response = self.api.get_site_storage_data(SITEID,start_time,end_time) ##non creo loop perché fino a una settimana posso recuperare dati
        bess = response.data['storageData']['batteries'][0]['telemetries']
        #print(bess)
        #"""
        for t in bess:
            #print(t['timeStamp'], t['power'])
            charge = t['power'] if t['power'] is not None and t['power'] >0  else 0
            discharge = abs(t['power']) if t['power'] is not None and t['power'] <0  else 0
            soc = round(t['batteryPercentageState'], 2) if t['batteryPercentageState'] is not None else 0
            bess_ch_dis['timestamp'].append(t['timeStamp'])
            bess_ch_dis['Charge(W)'].append(charge)
            bess_ch_dis['Discharge(W)'].append(discharge)
            bess_ch_dis['State of Charge(%)'].append(soc)
            #"""
    
        df_bess = pd.DataFrame(bess_ch_dis)
        #print(df_bess)
        df_bess['timestamp'] = pd.to_datetime(df_bess['timestamp'])
        df_bess.set_index('timestamp',inplace=True)
        df_bess.index = df_bess.index.round('min') #round seconds to the closer minute... ###risostituisci in T se dà problemi
        df_bess = df_bess[~df_bess.index.duplicated(keep='last')] #...and then remove duplicated indexes
        df_bess_resampled = df_bess.resample('1min').interpolate() ###risostituisci in 1T se dà problemi
        
        return df_bess_resampled


    def get_historic_production_and_consumption_data(self, end_time, forecast_row):
        """ 
            Prende come parametro aggiuntivo la dimensione di predizione da restituire
            forecast_row='Consumption' | 'Production' 
        """
        start_time = end_time - timedelta(minutes=35)
        power = self.api.get_site_power_details(SITEID,start_time, end_time).pandas
        #print(power.head(5))
        meter = power['powerDetails.meters.type']
        filtered_cols = ['powerDetails.meters.values.date', 'powerDetails.meters.values.value']
        df_power = power.loc[meter == forecast_row, filtered_cols].copy() ##filtro le righe del df in cui compare la dimensione da predire
        
        df_power.rename(columns={'powerDetails.meters.values.date':'timestamp', 'powerDetails.meters.values.value':f"{forecast_row}(W)"}, inplace=True)
        df_power['timestamp'] = pd.to_datetime(df_power['timestamp'])
        df_power.set_index('timestamp',inplace=True)
        df_power.index = df_power.index.round('min') 
        df_power = df_power[~df_power.index.duplicated(keep='last')] 
        df_power_resampled = df_power.resample('1min').interpolate() 

        #print(df_power_resampled.head(5))
        return df_power_resampled
        

if __name__ == "__main__":
    em = EnergyMonitoring()
    print(em.__dict__)
    em.update_all_data()
    print(em.__dict__)
    #print(em.get_consumption_info())
    #print(em.get_production_info())

     