import json, requests 
import pandas as pd
from collections import defaultdict as ddict
from datetime import datetime
from solaredge_interface.api.SolarEdgeAPI import SolarEdgeAPI
from typing import Text

SE_APIKEY = "MDYHBO9KZV0RQ4OS1DWE6YGS4HS9ELPH"

class EnergyMonitoring():
    
     def _init_(self) -> None:
        pass
        
     def get_consumption_data(self) -> Text:          
        api = SolarEdgeAPI(api_key=SE_APIKEY, datetime_response=True, pandas_response=True)
        SITEID = api.get_sites().pandas['sites.site.id'][0]
        data = api.get_site_current_power_flow(SITEID).data
        data = data["siteCurrentPowerFlow"]
        grid = data["GRID"]["currentPower"]
        pv = data["PV"]["currentPower"]
        load = data["LOAD"]["currentPower"]
        storage_stat = data["STORAGE"]["status"]
        storage_pow =  data["STORAGE"]["currentPower"]
        storage_lev = data["STORAGE"]["chargeLevel"]
        grid_import = grid if grid-pv > 0 else 0
        from_pv = min(load, pv-load) if pv > 0 else 0

        #text = f"Al momento stai consumando {load} kW, di cui {grid_import} dalla rete, {from_pv} dal fotovoltaico  \
        #    e {storage_pow} dalla batteria."
            #La batteria è carica al {storage_lev}% "

        return load, grid_import, from_pv, storage_pow#text
     
     def get_renewable_data(self) -> Text:          
        api = SolarEdgeAPI(api_key=SE_APIKEY, datetime_response=True, pandas_response=True)
        SITEID = api.get_sites().pandas['sites.site.id'][0]
        data = api.get_site_current_power_flow(SITEID).data
        data = data["siteCurrentPowerFlow"]
        grid = data["GRID"]["currentPower"]
        pv = data["PV"]["currentPower"]
        load = data["LOAD"]["currentPower"]
        storage_stat = data["STORAGE"]["status"]
        storage_pow =  data["STORAGE"]["currentPower"]
        storage_lev = data["STORAGE"]["chargeLevel"]
        grid_import = grid if grid-pv > 0 else 0
        from_pv = min(load, pv-load) if pv > 0 else 0

        #text = f"Al momento stai consumando {load} kW, di cui {grid_import} dalla rete, {from_pv} dal fotovoltaico  \
        #    e {storage_pow} dalla batteria."
            #La batteria è carica al {storage_lev}% "

        return load, grid_import, from_pv, storage_pow#text
     

if __name__ == "__main__":
    fb = EnergyMonitoring()
    print(fb.get_consumption_data())

     