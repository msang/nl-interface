import os
from solaredge_interface.api.SolarEdgeAPI import SolarEdgeAPI
from typing import Text
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())
SE_APIKEY = os.environ.get("SOLAREDGE_KEY")   

class EnergyMonitoring():
    
     def __init__(self) -> None:
        api = SolarEdgeAPI(api_key=SE_APIKEY, datetime_response=True, pandas_response=True)
        SITEID = api.get_sites().pandas['sites.site.id'][0]
        data = api.get_site_current_power_flow(SITEID).data
        self.data = data["siteCurrentPowerFlow"]
        self.grid = self.data["GRID"]["currentPower"]
        self.pv = self.data["PV"]["currentPower"]
        self.load = self.data["LOAD"]["currentPower"]
        self.storage_status = self.data["STORAGE"]["status"]
        self.storage_pow =  self.data["STORAGE"]["currentPower"]
        self.storage_lev = self.data["STORAGE"]["chargeLevel"]
        
     def get_consumption_data(self) -> Text:       

        from_pv = min(self.load, self.pv-self.load) if self.pv > 0 else 0

        return self.load, self.grid, from_pv, self.storage_pow
     
     def get_renewable_data(self) -> Text:          

        return self.pv, self.storage_lev, self.storage_status
     

if __name__ == "__main__":
    fb = EnergyMonitoring()
    print(fb.__dict__)
    print(fb.get_consumption_data())
    print(fb.get_renewable_data())

     