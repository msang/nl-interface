from solaredge_interface.api.SolarEdgeAPI import SolarEdgeAPI
import json, os, requests
import pandas as pd
import pyomo.environ as po
import matplotlib.pyplot as plt
from collections import defaultdict as ddict
from datetime import datetime
from dotenv import load_dotenv, find_dotenv
from os.path import join, dirname
from typing import List, Optional, Text, Dict, Tuple
#from utils import * #verbalize_result, get_idx
from .utils import *



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


    def get_pv_forecast(self) -> Dict[str, List]:

        #self._solcast_api() ##helper func. che crea il json con le predizioni pv
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            df = pd.DataFrame(data["forecasts"])
            #print(df)
            df["intervals"] = df["period_end"].apply(lambda x: datetime.strptime(x[:-4], "%Y-%m-%dT%H:%M:%S.%f"))
            
            return {"intervals":df["intervals"].to_list(), "values":df["pv_estimate"].to_list()}
 

class Appliance:

    def __init__(self, app_name: str) -> None:

        #dati su elettrodom. definiti a priori (in kWh)
        avg_kWh = {"washing_machine": 1.5, "dryer": 1.5, "hvac":  4.0, "water_heater": 4.0, \
                                  "oven": 3.0, "dishwasher": 1.5} 
        # durata espressa di default in numero di ore
        avg_h = {"dishwasher": 3, "washing_machine": 2, "oven": 2, "dryer": 3}
        
        self.app_name=app_name
        self.cycle_duration = avg_h[app_name] if app_name in avg_h else 0 # durata media di un ciclo d'uso espressa in numero di intervalli temporali (cambia quindi in base alla risoluzione)
        self.start_time = self.end_time = None #orario di avvio stabilito per un dato elettrodom (user-defined/istante corrente/niente)
        self.start_idx = self.end_idx = 0 #indice di posizione che corrisponde, nell'array degli intervalli, all'orario di avvio/fine
        self.avg_demand = avg_kWh[app_name] #consumo medio orario dell'elettrodom.
        self.temp_min = self.temp_max = 0 #limiti temperatura (laddove impostabili-attributo non applicabile a tutti gli elettrodom.)
        self.is_tcl = self.app_name in ("hvac","water_heater") 

    def __repr__(self) -> str:

        avvio = f"Avvio desiderato: {self.start_time}" if self.start_time is not None else "Nessun avvio programmato."
        if self.is_tcl:
            status = f"Elettrodomestico: {self.app_name} \n Per tipo di intervallo considerato: \n  -- Consumi medi: {self.avg_demand} kWh \n {avvio}"
        else:
            status = f"Elettrodomestico: {self.app_name} \n Per tipo di intervallo considerato: \n  -- Consumi medi: {self.avg_demand} kWh \n  -- Durata media di un ciclo: {self.cycle_duration} intervalli \n {avvio}"

        return status 
    

    def get_total_consumption(self) -> float :
        return self.avg_demand * self.cycle_duration  # in kWh
    
    def set_parameters(self, 
                       start_idx:int,
                       time_resolution:int=60) -> None:
        
        #riparametrizzo indici degli intervalli e durata d'uso (quando impostata) in base a risoluz. temporale
        if time_resolution == 15:
            self.cycle_duration = self.cycle_duration*4 # interv. di 15 min 
            self.start_idx = (start_idx-1)*4
            self.avg_demand = self.avg_demand / 4
        elif time_resolution == 30:
            self.cycle_duration = self.cycle_duration*2 #interv. di 30 min
            self.start_idx = (start_idx-1)*2
            self.avg_demand = self.avg_demand / 2
        else:
            self.start_idx = start_idx
            #cycle_duration e avg_demand restano quelle già stabilite di default

        self.end_idx = self.start_idx + self.cycle_duration
        
        #aggiorno l'ora di fine uso, se è impostato un avvio
        if self.start_time is not None:
            delta = self.cycle_duration * timedelta(minutes=time_resolution)
            self.end_time = self.start_time + delta


    def set_temp_bounds(self) -> tuple:

        if self.is_tcl:
            if self.app_name == "hvac":
                self.temp_min = 18
                self.temp_max = 35
            elif self.app_name == "water_heater":
                self.temp_min = 35
                self.temp_max = 55
    

class Preferences:

    def __init__(self) -> None:
        self.user_temp = None
        self.user_time = None
        self.appliance = None


    def __repr__(self) -> str:

        return f"Preferenze di temperatura: {self.user_temp} gradi \n Preferenze di tempo: {self.user_time}"
    

    def set_time_interval(self) -> tuple:
        pass


    def check_temp_bounds(self, appl: Appliance,
            temp: int,
            ) -> bool:

        return temp in range(appl.temp_min, appl.temp_max)
    

    def set_interval_constraint(self, appliance: str, start_time: datetime, end_time: datetime, temp_min, temp_max):

        print(f"APPSET: {appliance}")
        if start_time < self.end_window:#Intervallo nella finestra di ottimizzazione
            if end_time > self.end_window: end_time = self.end_window
            start_index = int((start_time - self.start_window).total_seconds() // self.delta)
            end_index = int((end_time - self.start_window).total_seconds() // self.delta) 
            print("\nECCOMI")
            for i in range(start_index, end_index + 1):
                print(f"{appliance}, {temp_min}, {i}")
                self.theta_min[appliance][i] = temp_min
                self.theta_max[appliance][i] = temp_max
        
    


class Optimizer:

    def __init__(self, 
                 app_name: Optional[str]="") -> None:
        self.appliance = Appliance(app_name) if app_name != "" else None
        self.user = Preferences()


    def set_appliance(self, appliance:Appliance) -> None:
        self.appliance = appliance
    

    def grid_optimizer(self, 
                       start_time: datetime, 
                       pv_forecast: dict, 
                       time_resolution: Optional[int]=30) -> Tuple[float, float, str]:
        
        pv_time_intervals = pv_forecast["intervals"]
        pv_values = pv_forecast["values"]
        #print(pv_time_intervals)
        #print(pv_values)

        if self.appliance is not None:
            self.appliance.start_time = start_time #passo all'eltettrodom. l'avvio identificato nella custom action (o user-defined o datetime.now())
            start_idx = get_idx(pv_time_intervals, start_time) #recupero l'indice a partire dall'orario esteso
            self.appliance.set_parameters(start_idx, time_resolution)
            print(self.appliance.start_idx, self.appliance.start_time, self.appliance.cycle_duration)

        if time_resolution != "30":
            pv_values = redefine_values(pv_values, time_resolution)
            pv_time_intervals = redefine_intervals(pv_time_intervals, time_resolution)

        print(len(pv_values), len(pv_time_intervals))
        
        model = po.ConcreteModel()

        # set: 
        T = len(pv_values) #numero di intervalli considerati nelle prossime variabili è sempre definito in funzione delle previsioni disponibili
        time_steps = range(T)
        model.time_steps = po.Set(initialize=time_steps)

        # parametri:
        appliance_consumption = [self.appliance.avg_demand if t >= self.appliance.start_idx and t < self.appliance.end_idx else 0 for t in time_steps]
        FIXED_LOAD = [0.1]*T  # stabilisco dei carichi fissi non controllabili per ciascun intervallo
        tot_load = list(map(lambda x,y: x+y, appliance_consumption, FIXED_LOAD )) # lista con curva finale dei carichi previsti
        #print(start_time,"\n", tot_load)
        
        #"""
        ### definisco i parametri relativi alle previsioni di pv e dei consumi come param di pyomo
        model.load_demand = po.Param(model.time_steps, initialize=tot_load)
        model.pv = po.Param(model.time_steps, initialize=pv_values)

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
        #model.tcl_temp = po.Var(model.time_steps, bounds=(theta_min, theta_max))
        

        #funzione obiettivo 
        def minimize_import(m):
            return sum(m.grid_imp[t] for t in m.time_steps)
        
        model.minimize_grid = po.Objective(rule=minimize_import, sense=po.minimize)

        #vincoli
        model.grid_at_t = po.ConstraintList()
        model.bess_charge_level_at_t = po.ConstraintList()
        #model.user_temp_preference_at_t = po.ConstraintList()

        for t in time_steps:
            # bilanciamento energetico
            model.grid_at_t.add(model.pv[t] + model.grid_imp[t] + model.bess_cd[t] == model.grid_exp[t] + model.load_demand[t] )
            if t == 0:
                model.bess_charge_level_at_t.add(model.bess_soc[t] == b_0 - model.bess_cd[t])
            else:
                model.bess_charge_level_at_t.add(model.bess_soc[t] == model.bess_soc[t-1] - model.bess_cd[t])
            # TODO: aggiungere qui vincolo di temperatura-tempo
            #if t in user_interval:
                #model.user_temp_preference_at_t.add(model.tcl_temp[t] == )

        solver = po.SolverFactory("glpk")
        solver.solve(model)

        print(f"Quantità totale di energia consumata dalla rete: {model.minimize_grid():.2f} kWh")
        print("Stato iniziale della batteria:", b_0)
        print("t \t PV \t Load \t Ch/Dis \t SoC \t Grid  \t Feed-in")
        for t, pv_t in zip(time_steps, pv_time_intervals):
            print(f"{pv_t} \t {model.pv[t]:.3f} \t {model.load_demand[t]:.3f} \t {model.bess_cd[t].value:.3f} \t {model.bess_soc[t].value:.3f} \t {model.grid_imp[t].value:.3f} \t {model.grid_exp[t].value:.3f}")

        _, ax = plt.subplots()
        #fig.subplots_adjust(right=0.75)
        #twin = ax.twinx()
        p1, = ax.plot(time_steps, pv_values, "green", label="PV forecast")
        p2, = ax.plot(time_steps, tot_load, "orange", label="Load")
        p3, = ax.plot(time_steps, [model.grid_imp[t].value for t in time_steps], "red", label="Grid")
        #p4, = twin.plot(time_steps, [model.bess_soc[t].value for t in time_steps], "yellow", label="Charge level")
        p5, = ax.plot(time_steps, [model.grid_exp[t].value for t in time_steps], label="Feed-in")
        ax.set_xlabel("Time steps")
        ax.set_ylabel("kWh")
        #twin.set_ylabel("kW")
        #ax.legend(handles=[p1, p2, p3, p4, p5])
        ax.legend(handles=[p1, p2, p3, p5])
        plt.savefig('grid_minimization.png')
        #https://matplotlib.org/3.4.3/gallery/ticks_and_spines/multiple_yaxis_with_spines.html

        #text_verbose = f"Sulla base del livello di carica attuale della batteria ({b_0}) e delle previsioni disponibili di produzione dal fotovoltaico nelle prossime 48 h, \
        #    prenderai dalla rete {model.minimize_grid():.2f} kWh se avvii l'elettrodomestico alle {start_time}"    
        #text = f"Se avvii l'elettrodomestico alle {start_time} consumerai dalla rete {model.minimize_grid():.2f} kWh"
        grid_import_values = [model.grid_imp[t].value for t in model.time_steps]
        text = verbalize_result(T, time_resolution, grid_import_values, self.appliance.cycle_duration)
        
        return b_0, model.minimize_grid(), text

    
def solaredge_api():
    dotenv_path = join(dirname(__file__), '.env')
    load_dotenv(dotenv_path)
    APIKEY = os.environ.get("SOLAREDGE_KEY")
    api = SolarEdgeAPI(api_key=APIKEY, datetime_response=True, pandas_response=True)
    SITEID = api.get_sites().pandas['sites.site.id'].iloc[0]
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
    #net_load = load-pv-bess_discharge # 
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
    #print(get_pv_forecast("data.json"))
    pv = PV()
    pv_fc = pv.get_pv_forecast()
    #print(pv_fc, type(pv_fc))
    #"""
    start = datetime.now()  # avvio tra 7 ore - NON alle 7 (come prima) (TODO: mappare orario con dati previsioni)

    opt = Optimizer("washing_machine")
    opt_start=datetime.now()
    print(opt.grid_optimizer(opt_start, pv_fc, time_resolution=60))
    #"""



 