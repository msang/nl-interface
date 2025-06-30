import json, os, requests
import pandas as pd
import pyomo.environ as po
import matplotlib.pyplot as plt
from collections import defaultdict as ddict
from datetime import datetime, timedelta
from dotenv import load_dotenv, find_dotenv
from os.path import join, dirname
from typing import List, Optional, Text, Dict, Tuple
from .utils import *
from .data import PV, get_bess_soc
from .appliance import Appliance


class Optimizer:
    def __init__(self, app_name: Optional[str] = "") -> None:
        self.appliance = Appliance(app_name) if app_name != "" else None
        self.pv_forecast = {}

    def set_appliance(self, appliance: Appliance) -> None:
        self.appliance = appliance

    def set_pv_data(self):
        pv = PV()
        self.pv_forecast = pv.get_pv_forecast()

    def grid_optimizer(self, start_time: datetime, preferred_start: datetime, preferred_end: datetime, time_resolution: Optional[int] = 30) -> Tuple[float, float, str]:
        
        self.set_pv_data()
        
        pv_time_intervals = self.pv_forecast["intervals"]
        pv_values = self.pv_forecast["values"]   
        #print(pv_time_intervals, pv_values)

        if self.appliance is not None:
            self.appliance.start_time = start_time
            start_idx = get_idx(pv_time_intervals, start_time)
            self.appliance.set_parameters(start_idx, time_resolution)

        if time_resolution != 30:
            pv_values = redefine_values(pv_values, time_resolution)
            pv_time_intervals = redefine_intervals(pv_time_intervals, time_resolution)

        max_len = min(len(pv_values), len(pv_time_intervals))
        pv_values, pv_time_intervals = pv_values[:max_len], pv_time_intervals[:max_len] #ridefinisco gli intervalli per fare in modo che abbiano lunghezza uguale
        #print(len(pv_values), len(pv_time_intervals))

        model = po.ConcreteModel()

        T = len(pv_values)
        time_steps = range(T)
        model.time_steps = po.Set(initialize=time_steps)
        #print(time_steps)

        preferred_start_idx = preferred_end_idx = -1

        # Converto anche i tempi dell'utente in indici
        if preferred_start is not None:
            preferred_start_idx = get_idx(pv_time_intervals, preferred_start)
        if preferred_end is not None:
            preferred_end_idx = get_idx(pv_time_intervals, preferred_end)
        #print(preferred_start_idx, preferred_end_idx)

        # Variabile binaria per decidere se l'elettrodomestico è acceso
        model.state = po.Var(model.time_steps, domain=po.Binary, initialize=0)

        # Definizione del consumo dell'elettrodomestico in base a "state"
        def appliance_demand_rule(m, t):
            return self.appliance.avg_demand * m.state[t]
        
        model.appliance_consumption = po.Expression(model.time_steps, rule=appliance_demand_rule)

        FIXED_LOAD = [0.1] * T
        model.load_demand = po.Expression(model.time_steps, rule=lambda m, t: model.appliance_consumption[t] + FIXED_LOAD[t])

        model.pv = po.Param(model.time_steps, initialize={t: pv_values[t] for t in time_steps})

        # Parametri batteria
        b_0 = get_bess_soc()
        bess_capacity = 10.0
        ch_dis_rate = bess_capacity / 4  
        bess_min = bess_capacity * 0.1
        grid_capacity = 6.0

        # Variabili decisionali
        model.grid_imp = po.Var(model.time_steps, bounds=(0.0, grid_capacity))
        model.grid_exp = po.Var(model.time_steps, bounds=(0.0, None))
        model.bess_soc = po.Var(model.time_steps, bounds=(bess_min, bess_capacity))
        model.bess_cd = po.Var(model.time_steps, bounds=(-ch_dis_rate, ch_dis_rate))

        # Vincolo per rispettare l'orario scelto dall'utente
        def user_preference_constraint_rule(m, t):
            if preferred_start_idx != -1 and preferred_end_idx != -1:
                if t >= preferred_start_idx and t <= preferred_end_idx:
                    return m.state[t] == 1
            return po.Constraint.Skip

        model.user_preference_constraint = po.Constraint(model.time_steps, rule=user_preference_constraint_rule)

        # Vincolo per garantire che il ciclo venga rispettato
        cycle_duration = self.appliance.cycle_duration

        def cycle_constraint_rule(m, t):
            if t <= T - cycle_duration:
                return sum(m.state[t + j] for j in range(cycle_duration)) >= cycle_duration * m.state[t]
            return po.Constraint.Skip

        model.cycle_constraints = po.Constraint(model.time_steps, rule=cycle_constraint_rule)

        # Funzione obiettivo: minimizzare l'energia prelevata dalla rete
        def minimize_import(m):
            return sum(m.grid_imp[t] for t in m.time_steps)

        model.minimize_grid = po.Objective(rule=minimize_import, sense=po.minimize)

        # Vincoli di bilanciamento energetico
        model.grid_at_t = po.ConstraintList()
        model.bess_charge_level_at_t = po.ConstraintList()

        for t in time_steps:
            model.grid_at_t.add(model.pv[t] + model.grid_imp[t] + model.bess_cd[t] == model.grid_exp[t] + model.load_demand[t])
            if t == 0:
                model.bess_charge_level_at_t.add(model.bess_soc[t] == b_0 - model.bess_cd[t])
            else:
                model.bess_charge_level_at_t.add(model.bess_soc[t] == model.bess_soc[t-1] - model.bess_cd[t])

        solver = po.SolverFactory("glpk")
        #solver.solve(model)
        result = solver.solve(model, tee=True)  # tee=True stampa il log del solver
        print("Solver status:", result.solver.status)
        print("Solver termination condition:", result.solver.termination_condition)


        """
        print(f"Quantità totale di energia consumata dalla rete: {model.minimize_grid():.2f} kWh")
        print("t \t PV \t Load \t Ch/Dis \t SoC \t Grid  \t Feed-in \t State")
        for t, pv_t in zip(time_steps, pv_time_intervals):
            print(f"{pv_t} \t {model.pv[t]:.3f} \t {model.load_demand[t]():.3f} \t {model.bess_cd[t].value:.3f} \t {model.bess_soc[t].value:.3f} \t {model.grid_imp[t].value:.3f} \t {model.grid_exp[t].value:.3f} \t {model.state[t].value}")
        """
        #print(f"Quantità totale di energia consumata dalla rete: {model.minimize_grid():.2f} kWh")
        #print("t \t PV \t Load  \t SoC \t Grid  \t Feed-in \t State")
        #for t, pv_t in zip(time_steps, pv_time_intervals):
        #    print(f"{pv_t} \t {model.pv[t]:.3f} \t {model.load_demand[t]():.3f} \t {model.bess_soc[t].value:.3f} \t {model.grid_imp[t].value:.3f} \t {model.grid_exp[t].value:.3f} \t {model.state[t].value}")

        _, ax = plt.subplots()
        p1, = ax.plot(pv_time_intervals, pv_values, "green", label="PV forecast")
        p2, = ax.plot(pv_time_intervals, [model.load_demand[t]() for t in time_steps], "orange", label="Load")
        p3, = ax.plot(pv_time_intervals, [model.grid_imp[t].value for t in time_steps], "red", label="Grid")
        p4, = ax.plot(pv_time_intervals, [model.state[t].value * self.appliance.avg_demand for t in time_steps], "blue", label="Appliance State")
        ax.set_xlabel("Time steps")
        ax.set_ylabel("kW")
        ax.legend(handles=[p1, p2, p3, p4])
        plt.savefig('grid_minimization.png')

        grid_import_values = [round(model.grid_imp[t].value, 2) for t in model.time_steps]
        time_steps = [t for t in pv_time_intervals]
        pv_data = [round(model.pv[t], 2) for t in model.time_steps]
        bess = [round(model.bess_soc[t].value, 2)*10 for t in model.time_steps]
        #state = [model.state[t].value for t in model.time_steps]
        state = ["Sì" if model.state[t].value > 0 else "No" for t in model.time_steps]
        #final = {"state":state, "grid":grid_import_values,"PV forecast":pv_data,"BESS SoC":bess}
        final = {'orario':time_steps, 'Accensione consigliata':state, 'Potenza presa dalla rete (kW)':grid_import_values,'Produzione solare prevista (kW)':pv_data,'Stato batteria (%)':bess}

        #df = pd.DataFrame(final, index=time_steps)
        df = pd.DataFrame(final)
        #print(df)

        #text = verbalize_result(T, time_resolution, grid_import_values, self.appliance.cycle_duration)
        #print(df.head(12).to_string())
        return df.head(12).to_string(index=False) #mantengo solo i risultati delle prime 12 ore, per limitare il contesto


if __name__ == "__main__":
    start = datetime.now()
    opt = Optimizer("hvac")
    opt_start = datetime.now()
    user_start = opt_start.replace(hour=21)
    user_end = opt_start.replace(hour=22)
    print(opt_start, user_start, user_end)
    print(opt.grid_optimizer(opt_start, user_start, user_end, time_resolution=60))
