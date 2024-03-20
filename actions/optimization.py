from solaredge_interface.api.SolarEdgeAPI import SolarEdgeAPI
import json, os, requests
import pandas as pd
import pyomo.environ as po
import matplotlib.pyplot as plt
from collections import defaultdict as ddict
from datetime import datetime
from dotenv import load_dotenv, find_dotenv
from os.path import join, dirname
from typing import List, Optional, Text



class PV:

    """
    # inizializzo valori da file di configurazione
    def __init__(self, config_file)->None:
        pass
    """

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
        #url = f"https://api.solcast.com.au/data/forecast/rooftop_pv_power?latitude={latitude}&longitude={longitude}&output_parameters=pv_power_rooftop&capacity={pv_capacity}&format=json&api_key={APIKEY}&tilt={tilt}&azimuth={azimuth}"
        url= f"https://api.solcast.com.au/rooftop_sites/{RT_SITE}/forecasts?format=json&api_key={APIKEY}"
        response = requests.request("GET", url, headers=headers)
        #print(response.text)
        data = response.json()

        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)


    def get_pv_forecast(self) -> List[float]:

        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            forecasts = ddict(list)
            for i in data["forecasts"]:
                forecasts["pv_estimate"].append(i["pv_estimate"])
                dt = i["period_end"].split("T")
                d = datetime.strptime(dt[0], '%Y-%m-%d')
                t = datetime.strptime(dt[1], '%H:%M:%S.%f0%z').time()
                forecasts["date"].append(d)
                forecasts["time"].append(t)
            df = pd.DataFrame(forecasts)
            #df["today"] = df["date"].apply(lambda x: pd.to_datetime(x).date() == date.today())
            #return df.loc[df["today"]==True, :] ### per ora estraggo solo i dati relativi alla giornata corrente
            
            return df["pv_estimate"].to_list()
 

class Appliance:

    def __init__(self, app_name: str) -> None:

        #dati su elettrodom. definiti a priori (in kWh -- ovv. quanta energia consumano mediamente in 1 ora di utilizzo)
        avg_kWh = {"washing_machine": 1.5, "dryer": 1.5, "heat_pump":  4.0, "boiler": 4.0, \
                                  "oven": 3.0, "dishwasher": 1.5} 
        # durata espressa di default in numero di ore
        avg_h = {"dishwasher": 3, "washing_machine": 2, "oven": 2, "dryer": 3}
        
        self.app_name=app_name
        self.cycle_duration = avg_h[app_name]  # interv. di 1 ora 
        self.start_time = 0
        self.avg_demand = avg_kWh[app_name]
        self.end_time = 0

    def __repr__(self) -> str:
        status = ""
        if self.start_time == 0:
            status = f"Elettrodomestico: {self.app_name} \n Per tipo di intervallo considerato: \n  -- Consumi medi: {self.avg_demand} kWh \n  -- Durata media di un ciclo: {self.cycle_duration} intervalli \n Nessun avvio programmato"
        else:
            status = f"Elettrodomestico: {self.app_name} \n Per tipo di intervallo considerato: \n  -- Consumi medi: {self.avg_demand} kWh \n  -- Durata media di un ciclo: {self.cycle_duration} intervalli \n Intervallo di avvio: {self.start_time} \n Intervallo di fine: {self.end_time}"

        return status 
    
    def get_total_consumption(self) -> float :
        return self.avg_demand * self.cycle_duration  # in kWh
    
    def set_parameters(self, 
                       start_time:int, 
                       time_resolution:int) -> None:
        
        if time_resolution == 15:
            self.cycle_duration = self.cycle_duration*4 # interv. di 15 min
            self.start_time = (start_time-1)*4 
            self.avg_demand = self.avg_demand / 4
        elif time_resolution == 30:
            self.cycle_duration = self.cycle_duration*2 #interv. di 30 min
            self.start_time = (start_time-1)*2
            self.avg_demand = self.avg_demand / 2
        else:
            self.start_time = start_time
            #cycle_duration e avg_demand restano quelle già stabilite di default

        self.end_time = self.start_time + self.cycle_duration
    

class Optimizer:

    def __init__(self, 
                 app_name: str) -> None:
        self.appliance = Appliance(app_name)

    def start_optimizer(self, **kwargs) -> None:
        pass

    """
    def start_optimizer(self, 
                        appliance: Optional[str]=None, 
                        pv_forecast: Optional[List[float]]=[], 
                        objective: Optional[str]=None, 
                        user_preference: Optional[str]=None)  -> None :
        pass
    """


    def grid_optimizer(self, 
                       start_time: int, 
                       pv_forecast: List, 
                       time_resolution: Optional[int]=30) -> Text:

        self.appliance.set_parameters(start_time, time_resolution)
        #print(pv_forecast, type(pv_forecast))

        #ridefinisco gli intervalli delle previsioni pv in base alla risoluzione temporale
        ## quella da 30 min è la risoluzione disponibile di default
        if time_resolution== 15:
            pv_forecast = [t/2 for t in pv_forecast for _ in range(2)]
        elif time_resolution==60:
            if len(pv_forecast)%2 == 0:
                pv_forecast = [ pv_forecast[e] + pv_forecast[e+1] for e in range(0, len(pv_forecast), 2)]
            else:
                pv_forecast = [ pv_forecast[e] + pv_forecast[e+1] for e in range(0, len(pv_forecast)-1, 2)]
        
        model = po.ConcreteModel()

        # set: 
        T = len(pv_forecast) #numero di intervalli considerati (definito qui in funzione delle previsioni disponibili)
        time_steps = range(T)
        model.time_steps = po.Set(initialize=time_steps)

        # parametri:
        appliance_consumption = [ self.appliance.avg_demand if t >= self.appliance.start_time and t < self.appliance.end_time else 0 for t in time_steps]
        FIXED_LOAD = [0.1]*T  # stabilisco dei carichi fissi non controllabili per ciascun quarto d'ora
        tot_load = list(map(lambda x,y: x+y, appliance_consumption, FIXED_LOAD )) # lista con curva finale dei carichi previsti
        #"""
        ### definisco i parametri relativi alle previsioni di pv e dei consumi come param di pyomo
        model.load_demand = po.Param(model.time_steps, initialize=tot_load)
        model.pv = po.Param(model.time_steps, initialize=pv_forecast)

        # altre costanti:
        b_0 = solaredge_api()["bess_charge_level"] # stato iniziale della batteria
        bess_capacity = 10.0
        # TODO: rivedere anche un modo più flessibile di determinare la batteria
        ch_dis_rate = bess_capacity/4  # tasso di carica/scarica max per quarto d'ora -- assumendo una carica/scarica completa in 4 ore
        bess_min = bess_capacity*0.1  # soglia minima di carica
        grid_capacity=6.0 #quantità max di energia che posso prendere dalla rete

        #variabili decisionali:
        model.grid_imp = po.Var(model.time_steps, bounds=(0.0, grid_capacity))
        model.grid_exp = po.Var(model.time_steps, bounds=(0.0, None))
        model.bess_soc = po.Var(model.time_steps, bounds=(bess_min, bess_capacity))
        model.bess_cd = po.Var(model.time_steps, bounds=(-ch_dis_rate, ch_dis_rate))

        #funzione obiettivo 
        def minimize_import(m):
            return sum(m.grid_imp[t] for t in m.time_steps)
        
        model.minimize_grid = po.Objective(rule=minimize_import, sense=po.minimize)

        #vincoli
        model.grid_at_t = po.ConstraintList()
        model.bess_charge_level_at_t = po.ConstraintList()

        for t in time_steps:
            # bilanciamento energetico
            model.grid_at_t.add(model.pv[t] + model.grid_imp[t] + model.bess_cd[t] == model.grid_exp[t] + model.load_demand[t] )
            if t == 0:
                model.bess_charge_level_at_t.add(model.bess_soc[t] == b_0 - model.bess_cd[t])
            else:
                model.bess_charge_level_at_t.add(model.bess_soc[t] == model.bess_soc[t-1] - model.bess_cd[t])

        solver = po.SolverFactory("glpk")
        solver.solve(model)

        #print(f"Quantità totale di energia consumata dalla rete: {model.minimize_grid():.2f} kWh")
        #print("Stato iniziale della batteria:", b_0)
        #print("t \t PV \t Load \t Ch/Dis \t SoC \t Grid  \t Feed-in")
        #for t in time_steps:
        #    print(f"{t+1} \t {model.pv[t]:.3f} \t {model.load_demand[t]:.3f} \t {model.bess_cd[t].value:.3f} \t {model.bess_soc[t].value:.3f} \t {model.grid_imp[t].value:.3f} \t {model.grid_exp[t].value:.3f}")

        _, ax = plt.subplots()
        #fig.subplots_adjust(right=0.75)
        twin = ax.twinx()
        p1, = ax.plot(time_steps, pv_forecast, "green", label="PV forecast")
        p2, = ax.plot(time_steps, tot_load, "orange", label="Load")
        p3, = ax.plot(time_steps, [model.grid_imp[t].value for t in time_steps], "red", label="Grid")
        p4, = twin.plot(time_steps, [model.bess_soc[t].value for t in time_steps], "yellow", label="Charge level")
        p5, = ax.plot(time_steps, [model.grid_exp[t].value for t in time_steps], label="Feed-in")
        ax.set_xlabel("Time steps")
        ax.set_ylabel("kWh")
        twin.set_ylabel("kW")
        ax.legend(handles=[p1, p2, p3, p4, p5])
        plt.savefig('grid_minimization.png')
        #https://matplotlib.org/3.4.3/gallery/ticks_and_spines/multiple_yaxis_with_spines.html

        #text_verbose = f"Sulla base del livello di carica attuale della batteria ({b_0}) e delle previsioni disponibili di produzione dal fotovoltaico nelle prossime 48 h, \
        #    prenderai dalla rete {model.minimize_grid():.2f} kWh se avvii l'elettrodomestico alle {start_time}"    
        #text = f"Se avvii l'elettrodomestico alle {start_time} consumerai dalla rete {model.minimize_grid():.2f} kWh"
        
        return b_0, start_time, model.minimize_grid() #text


# TODO: rivedere l'ottimizzatore in modo che stabilisca l'orario migliore di avvio di un dato elettrodomestico
    
def solaredge_api():
    dotenv_path = join(dirname(__file__), '.env')
    load_dotenv(dotenv_path)
    APIKEY = os.environ.get("SOLAREDGE_KEY")
    api = SolarEdgeAPI(api_key=APIKEY, datetime_response=True, pandas_response=True)
    SITEID = api.get_sites().pandas['sites.site.id'][0]
    data = api.get_site_current_power_flow(SITEID).data
    data = data["siteCurrentPowerFlow"]
    grid = data["GRID"]["currentPower"]
    current_pv = data["PV"]["currentPower"]
    load = data["LOAD"]["currentPower"]
    #bess_status = data["STORAGE"]["status"]
    #bess_discharge =  data["STORAGE"]["currentPower"] ###in relatà dipende da status
    bess_soc = data["STORAGE"]["chargeLevel"]*0.1 ## da % a kW

    #self_consumption = round(((load-grid)/grid)*100)# --> formula da rivedere
    #self_sufficiency = round(((load-grid)/current_pv)*100)# --> formula da rivedere
    #net_load = load-grid-bess_discharge # --> formula da rivedere!
    overview = {"power_from_grid": grid, "load": load, "pv_power": current_pv, "bess_charge_level": bess_soc}

    return overview

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
    start = 7  # avvio tra 7 ore - NON alle 7 (come prima) (TODO: mappare orario con dati previsioni)
    pv = PV()
    pv_fc = pv.get_pv_forecast()
    #print(pv_fc, type(pv_fc))
    opt = Optimizer("washing_machine")
    print(opt.grid_optimizer(start, pv_fc, time_resolution=60))



 