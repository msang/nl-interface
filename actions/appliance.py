from datetime import timedelta

class Appliance:

    def __init__(self, app_name: str) -> None:

        #dati su elettrodom. definiti a priori (in kWh)
        avg_kWh = {"washing_machine": 1.5, "dryer": 1.5, "hvac":  3.5, "water_heater": 3.5, \
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
        upsilon = 60/time_resolution
        if upsilon > 1:
            self.cycle_duration = self.cycle_duration*upsilon
            self.start_idx = (start_idx-1)*upsilon
            self.avg_demand = self.avg_demand/upsilon
            """
            elif time_resolution == 5:
                self.cycle_duration = self.cycle_duration*12 # interv. di 5 min 
                self.start_idx = (start_idx-1)*12
                self.avg_demand = self.avg_demand / 12
            elif time_resolution == 15:
                self.cycle_duration = self.cycle_duration*4 # interv. di 15 min 
                self.start_idx = (start_idx-1)*4
                self.avg_demand = self.avg_demand / 4
            elif time_resolution == 30:
                self.cycle_duration = self.cycle_duration*2 #interv. di 30 min
                self.start_idx = (start_idx-1)*2
                self.avg_demand = self.avg_demand / 2
            """
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
    
