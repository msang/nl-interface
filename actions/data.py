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

############################################
# trattamento dati shelly


# per convertire stringhe tipo dizionario in oggetto json
import ast

def parse_json_like(v):
    try:
        # Solo se è stringa e inizia con {
        if isinstance(v, str) and v.strip().startswith('{'):
            return ast.literal_eval(v)
        return v
    except (ValueError, SyntaxError):
        return v  # Se fallisce, lascia il valore così com'è


def import_shelly():
    # dati azzedine:
    df = pd.read_csv('../shelly_simulated.csv', converters={'Value': parse_json_like})  
    
    # se timestamp != datetime
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    
    pivot_df = df.pivot_table(index='Timestamp', columns='Key', values='Value', aggfunc='first')  
    pivot_df.drop(['raw','voltage','current', 'output'], axis=1, inplace=True)
    pivot_df.rename(columns={'Timestamp': 'orario', 'aenergy': 'energia consumata (kWh)', 'apower':'potenza attuale (kW)', 'temperature':'temperatura'}, inplace=True)
    pivot_df['temperatura'] = pivot_df['temperatura'].apply(lambda x: x["tC"])
    pivot_df['energia consumata (kWh)'] = pivot_df['energia consumata (kWh)'].apply(lambda x: x["total"])
    results =  pivot_df.reset_index().to_string(index=False)

    return results
        

##############################################################
### trattamento dati per scambi su blockchain

def parse_float(value):
    try:
        return round(float(str(value).replace(",", ".")), 2)
    except (ValueError, TypeError):
        return 0.0

def parse_energy_data(file_path="test2_scenarios.csv"):
    df = pd.read_csv(file_path, sep=";")
    scenarios = {}
    users = []

    for _, row in df.iterrows():
        date = row["Date"]
        prosumer_user = row['Prosumer_user']
        users.append(prosumer_user)
        members = []
        
        peers = {
            "Peer1": "prosumer", 
            "Peer2": "prosumer", 
            "Peer3": "prosumer", 
            "Peer4": "consumer", 
            "Peer5": "consumer"
        }

        for peer, role in peers.items():
            production = parse_float(row.get(peer + "_production"))
            consumption = parse_float(row.get(peer + "_consumption"))
            is_user = peer == prosumer_user         

            member = {
                "name": peer,
                "is_user": is_user,
                "role": role,
                "production": production if role == "prosumer" else 0.0,
                "consumption": consumption
            }

            members.append(member)
       
        scenarios[date] = members

    return scenarios, users

def parse_energy_excel(file_path="energy_details.xlsx"):

    xl = pd.ExcelFile(file_path)
    members = []

    for idx, sheet_name in enumerate(xl.sheet_names):
        df = xl.parse(sheet_name)

        # normalizzazione header
        df.columns = [str(c).strip() for c in df.columns]
        first_row = df.iloc[20] #riga scelta pseudo-casualmente: 2024-01-21 00:00:00+01:00	Consumi: 10,033	- Produzione: 20,735

        role = "prosumer" if idx < 3 else "consumer"
        member = {
            "name": sheet_name,
            "is_user": (idx == 0),  # primo prosumer è l'utente
            "role": role,
        }
        if role == "prosumer":
            member["production"] = round(float(str(first_row["Production"]).replace(",", ".")), 2)
            member["consumption"] = round(float(str(first_row["Consumption"]).replace(",", ".")), 2)
        else:
            member["production"] = 0.0
            member["consumption"] = round(float(str(first_row["Consumption"]).replace(",", ".")), 2)
        members.append(member)
    #print(members)
    prosumer_user = next((m["name"] for m in members if m["is_user"] and m["role"] == "prosumer"), None)

    return members, prosumer_user

## =======================================================================
# Metodi statici richiamati dall'ottimizzatore per il post-processing
## ========================================================================

def summarize_data(df_optim):
    """
    Riassume una giornata (df_final dell'ottimizzatore) individuando le fasce orarie
    di picco per consumo, produzione, stato di carica ed energia condivisa.
    Restituisce una stringa con dati sintentici in forma semi-strutturata.
    """

    # Identifica fasce di interesse
    peak_consumption = find_peak_range(df_optim["Potenza acquistata"])
    peak_production = find_peak_range(df_optim["Potenza immessa in rete"])
    high_soc = find_peak_range(df_optim["% Carica batteria"])
    peak_shared = find_peak_range(df_optim["Energia condivisa"])
    #min_soc = find_min_range(df_optim["% Carica batteria"])

    # Dati di sintesi
    if peak_production[1] == 0.0:      
        summary = (
                    f"- Consumo maggiore: {peak_consumption[0]} ({peak_consumption[1]:.2f} kWh)\n"
                    f"- Stato di carica massimo della batteria:  {high_soc[0]} ({high_soc[1]:.2f}%)\n"
                    #f"- Livello minimo di carica della batteria: {min_soc[0]} ({min_soc[1]:.2f}%)\n"
                    f"- Valori massimi di energia condivisa: {peak_shared[0]} ({peak_shared[1]:.2f} kWh)\n"
    )

    else:
        summary = (
                    f"- Consumo maggiore: {peak_consumption[0]} ({peak_consumption[1]:.2f} kWh)\n"
                    f"- Surplus maggiore: {peak_production[0]} ({peak_production[1]:.2f} kWh)\n"
                    f"- Stato di carica massimo della batteria:  {high_soc[0]} ({(high_soc[1]):.2f}%)\n"
                    #f"- Livello minimo di carica della batteria: {min_soc[0]} ({(min_soc[1]):.2f}%)\n"
                    f"- Valori massimi di energia condivisa: {peak_shared[0]} ({peak_shared[1]:.2f} kWh)\n"
    )

    return summary

def find_peak_range(series, top_n=3):
    """Restituisce le fasce orarie con i valori più alti (top_n medie consecutive)."""
    """
    rolling = series.rolling(2, min_periods=1).mean()
    top_idx = rolling.nlargest(top_n).index
    times = [i.strftime("%H:%M") for i in sorted(top_idx)]
    return f"{times[0]}–{times[-1]}" if len(times) > 1 else times[0]
    """
    if series.dropna().eq(0).all():
        return "-", 0.0

    rolling = series.rolling(2, min_periods=1).max()
    top_idx = rolling.nlargest(top_n).index

    if top_idx.empty:
        return "-", 0.0

    times = [i.strftime("%H:%M") for i in sorted(top_idx)]
    overall_value = rolling[top_idx].mean()
    time_range = f"{times[0]}–{times[-1]}" if len(times) > 1 else times[0]
    
    return time_range, overall_value
    

def find_min_range(series, bottom_n=3):
    """Fasce con valori più bassi."""
    #"""
    rolling = series.rolling(2, min_periods=1).min()
    bottom_idx = rolling.nsmallest(bottom_n).index
    final_value = rolling[bottom_idx].min()
    times = [i.strftime("%H:%M") for i in sorted(bottom_idx)]
    time_range = f"{times[0]}–{times[-1]}" if len(times) > 1 else times[0]

    return time_range, final_value
    #return f"{times[0]}–{times[-1]}" if len(times) > 1 else times[0]
    #"""


if __name__ == "__main__":
    #path = "test2_scenarios.csv"
    print(parse_energy_data())
    #print(import_shelly())
    """
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
    #pv = PV()
    #pv_fc = pv.get_pv_forecast()
    #H = 12
    #end = datetime.now()
    #start = end-timedelta(hours=H+1)
    #end = end.strftime("%Y-%m-%d %H:%M:%S")
    #start = start.strftime("%Y-%m-%d %H:%M:%S")
    #print(start, end)
    #cons, prod, _, _ = solaredge_api(start, end)
    #print(generate_synth_data(cons, 3))
    """
    