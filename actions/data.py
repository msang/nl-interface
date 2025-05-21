from datetime import datetime, timedelta
from dotenv import load_dotenv, find_dotenv
from os.path import join, dirname
from solaredge_interface.api.SolarEdgeAPI import SolarEdgeAPI
import json, os, random, requests
import numpy as np
import pandas as pd
from typing import List, Dict


dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)
APIKEY = os.environ.get("SOLAREDGE_KEY")
SITEID = os.environ.get("SOLAREDGE_SITE_ID")

class PV:

    def __init__(self):
        self.latitude=""
        self.longitude=""
        self.tilt=""
        self.azimuth=""
        self.pv_capacity=""

    
    def _solcast_api(self) -> None:

        load_dotenv(find_dotenv())
        APIKEY=os.environ.get("SOLCAST_KEY")
        RT_SITE=os.environ.get("ROOFTOP_SITE")
        headers = {'Content-Type': 'application/json'}
        url= f"https://api.solcast.com.au/rooftop_sites/{RT_SITE}/forecasts?format=json&api_key={APIKEY}"
        response = requests.request("GET", url, headers=headers)
        #print(response.text)
        data = response.json()

        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)


    def get_pv_forecast(self) -> Dict[str, List]:

        pv_filename = 'data.json'
        #print("FILE EXISTS? -> ", os.path.isfile(pv_filename))
        if not os.path.isfile(pv_filename):
            self._solcast_api() ##helper func. che crea il json con le predizioni pv -> lo crea solo se non c'è, altrimenti si usa campione già creato (causa limiti di chiamate api)
        with open(pv_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            df = pd.DataFrame(data["forecasts"])
            #print(df)
            df["intervals"] = df["period_end"].apply(lambda x: datetime.strptime(x[:-4], "%Y-%m-%dT%H:%M:%S.%f"))
            
            return {"intervals":df["intervals"].to_list(), "values":df["pv_estimate"].to_list()}
        

        
############################################
def solaredge_api(start_time, end_time):
    dotenv_path = join(dirname(__file__), '.env')
    load_dotenv(dotenv_path)
    APIKEY = os.environ.get("SOLAREDGE_KEY")
    SITEID = os.environ.get("SOLAREDGE_SITE_ID")
    api = SolarEdgeAPI(api_key=APIKEY, datetime_response=True, pandas_response=True)
    power_data = api.get_site_power_details(SITEID, start_time,end_time).pandas
    df = pd.DataFrame(power_data).pivot(index = "powerDetails.meters.values.date", columns="powerDetails.meters.type", values="powerDetails.meters.values.value")
    #df_kW = df.apply(lambda x: x*0.001) 
    
    steps = df.index.to_list()
    time_delta = (steps[-1] - steps[-2]).seconds//60
    net_load_data = df["Purchased"].apply(lambda x: x*0.001).to_list()
    production_data = df["Production"].apply(lambda x: x*0.001).to_list()
    fed_in_data =  df["FeedIn"].apply(lambda x: x*0.001).to_list()
    #print(len(net_load_data), len(production_data))

    #bess_soc_0 = api.get_site_current_power_flow(SITEID).data['siteCurrentPowerFlow']['STORAGE']['chargeLevel']

    return net_load_data, production_data, fed_in_data, time_delta


def get_bess_soc():
    dotenv_path = join(dirname(__file__), '.env')
    load_dotenv(dotenv_path)
    APIKEY = os.environ.get("SOLAREDGE_KEY")
    api = SolarEdgeAPI(api_key=APIKEY, datetime_response=True, pandas_response=True)
    SITEID = api.get_sites().pandas['sites.site.id'].iloc[0]
    data = api.get_site_current_power_flow(SITEID).data["siteCurrentPowerFlow"]
    #return {"bess_charge_level": data["STORAGE"]["chargeLevel"] * 0.1}
    return data["STORAGE"]["chargeLevel"] * 0.1


def generate_synth_data(data, prosumers):

    final =  np.zeros((prosumers, len(data))) # dim. NxT, N=num. di prosumer, T=num. di intervalli temporali
   
    for i in range(prosumers):
        roll = random.randint(-16, 8)
        d = np.roll(data, roll, axis=0).flatten() #stessi dati di C1/G1, ma sfasati -- vd. righe 16-24 problem_data.m
        final[i] = d 
 
    return final



if __name__ == "__main__":

    #coordinate di cagliari (https://dateandtime.info/it/citycoordinates.php?id=2525473):
    LAT = 39.2305400
    LONG =  9.1191700
    ALTITUDE=6

    # dati impianto pv
    TILT=9.1
    AZIMUTH=90
    PV_CAPACITY= 6.68 #capacità dell'impianto (kWh)
    PEAK_POW=6.75

    #solcast_api(LAT, LONG, TILT, AZIMUTH, PV_CAPACITY)
    #forecast = get_pv_forecast("data.json")
    #pv = forecast["pv_estimate"].to_list()
    #print(get_pv_forecast("data.json"))
    pv = PV()
    #pv_fc = pv.get_pv_forecast()
    H = 12
    end = datetime.now()
    start = end-timedelta(hours=H+1)
    end = end.strftime("%Y-%m-%d %H:%M:%S")
    start = start.strftime("%Y-%m-%d %H:%M:%S")
    print(start, end)
    cons, prod, _, _ = solaredge_api(start, end)
    #print(generate_synth_data(cons, 3))