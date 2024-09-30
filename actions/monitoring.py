import os
from solaredge_interface.api.SolarEdgeAPI import SolarEdgeAPI
from typing import Text
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())
SE_APIKEY = os.environ.get("SOLAREDGE_KEY")   

class EnergyMonitoring():
    
     def __init__(self) -> None:
        api = SolarEdgeAPI(api_key=SE_APIKEY, date6iuy7ttime_response=True, pandas_response=True)
        SITEID = api.get_sites().pandas['sites.site.id'][0]
        data = api.get_site_current_power_flow(SITEID).data
        self.data = data["siteCurrentPowerFlow"]
        self.grid = self.data["GRID"]["currentPower"]
        self.pv = self.data["PV"]["currentPower"]
        self.load = self.data["LOAD"]["currentPower"]
        self.storage_status = self.data["STORAGE"]["status"] # Active, Idle o Disabled. 
        self.storage_pow =  self.data["STORAGE"]["currentPower"] # corrente(positiva) in entrata o in uscita
        self.storage_lev = self.data["STORAGE"]["chargeLevel"]# percentuale di carica

        self.connections = self.data["connections"]#Da controllare la corretta acquisizione, in teoria serve per la direzione della batteria
        
     def get_consumption_data(self) -> Text:       

        from_pv = min(self.load, self.pv-self.load) if self.pv > 0 else 0

        return self.load, self.grid, from_pv, self.storage_pow
     
     def get_renewable_data(self) -> Text: 
                  
         storage_on_charge = any(flow['from'] == "PV" and flow['to'] == "STORAGE" for flow in self.connections)
         #surplus = any(flow['from'] == "PV" and flow['to'] == "GRID" for flow in self.connections) ##controlla se viene spedita alla rete dai fotovoltaici

         return self.pv, self.storage_lev, self.storage_status, self.storage_pow, storage_on_charge
     

if __name__ == "__main__":
    fb = EnergyMonitoring()
    print(fb.__dict__)
    print(fb.get_consumption_data())
    print(fb.get_renewable_data())

     