from datetime import datetime, timedelta

class FakeOptimizer:
    """
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(FakeOptimizer, cls).__new__(cls)
        return cls.instance
    """
    
    def __init__(self):
        #if not hasattr(self, 'initialized'):
        self.appliances = ["water_heater","hvac"]
        self.delta = 15*60 #intervallo tra i campioni
        self.H = 24*60*60 #finestra temporale di ottimizzazione
        self.T = int(self.H/self.delta)  #numero di campioni
        self.start_window = datetime.now().replace(microsecond=0)
        self.end_window = self.start_window + timedelta(seconds=self.H)
        self.thetaDefault = 18 #temperatura base
        self.theta_min = {appliance: [self.thetaDefault] * self.T for appliance in self.appliances} #temperatura minima nei vari campioni
        self.theta_max = {appliance: [self.thetaDefault + 2] * self.T for appliance in self.appliances} #temperatura massima nei vari campioni
        #self.theta_min [self.thetaDefault] * self.T 


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
    
        
    def update_opt_window(self):
        while self.start_window + timedelta(minutes=self.delta) < datetime.today():
            self.start_window += timedelta(minutes=self.delta)
        constraints = self.read_constraints()
        print(constraints)
        new_lines = []
        for appliance, start, end, temp_min, temp_max in constraints:
            #Ignora intervalli o porzioni precedenti all'inizio
            if end < self.start_window: continue 
            if start < self.start_window: start = self.start_window 

            if start <= self.end_window:
                #Se l'intervallo è completamente nel range di ottimizzazione allora modifica gli array, altrimenti salva l'intervallo esterno 
                if end <= self.end_window:
                    self.set_interval_constraint(appliance, start,end,temp_min,temp_max)
                else:
                    self.set_interval_constraint(appliance, start,self.end_window,temp_min,temp_max)
                    new_lines.append(f"{appliance}, {self.end_window.isoformat()}, {end.isoformat()}, {temp_min}, {temp_max}\n")
            else:
                # Nessuna sovrapposizione: mantiene l'intervallo originale
                new_lines.append(f"{appliance}, {start.isoformat()}, {end.isoformat()}, {temp_min}, {temp_max}\n")

        self.print_theta()
        
        with open("constraints.txt", "w") as file:
            file.writelines(new_lines)
        

    def save_constraint(self, appliance, start_time, end_time, temp_min, temp_max):
        with open("constraints.txt", "a") as file:
            line = f"{appliance}, {start_time.replace(microsecond=0)}, {end_time.replace(microsecond=0)}, {temp_min}, {temp_max}\n"
            file.write(line)
        self.update_opt_window()


    def read_constraints(self):
        results = []
        with open("constraints.txt", "r") as file:
            for line in file:
                elements = line.strip().split(", ")
                if len(elements) == 5:
                    appliance = elements[0]
                    start_time = datetime.fromisoformat(elements[1])
                    end_time = datetime.fromisoformat(elements[2])
                    temp_min = int(elements[3])
                    temp_max = int(elements[4])
                
                    results.append((appliance, start_time, end_time, temp_min, temp_max))
        return results
    
    
    def print_theta(self):
        print(self.theta_min)
        for appliance in self.appliances:
            print("hey")
            print(f"Theta_min {appliance}: {self.theta_min[appliance]}")
            print(f"Theta_max {appliance}: {self.theta_max[appliance]}")



if __name__ == "__main__":
    opt = FakeOptimizer()

    # # Stampa dei valori iniziali di theta_min e theta_max
    print("Valori iniziali di theta_min:")
    print(opt.theta_min)
    print("\nValori iniziali di theta_max:")
    print(opt.theta_max)

    # # Definizione di un intervallo temporale e impostazione di vincoli
    start_time = opt.start_window + timedelta(minutes=15)  # Intervallo a partire dal secondo campione
    end_time = opt.start_window + timedelta(minutes=60)    # Intervallo fino al quinto campione
    temp_min = 20
    temp_max = 25

    # # Chiamata della funzione per impostare i vincoli
    for app in opt.appliances:
        opt.set_interval_constraint(app, start_time, end_time, temp_min, temp_max)

    # # Stampa dei valori aggiornati di theta_min e theta_max
    print("\nValori aggiornati di theta_min:")
    print(opt.theta_min)
    print("\nValori aggiornati di theta_max:")
    print(opt.theta_max)

    opt.update_opt_window()
    # # Stampa dei valori di theta_min e theta_max dopo 
    print("\nValori di theta_min dopo update_window():")
    print(opt.theta_min)
    print("\nValori di theta_max  dopo update_window():")
    print(opt.theta_max)


#  # Aggiunge intervalli di test usando la funzione save_constraint
# opt.save_constraint(datetime.now() - timedelta(hours=3), datetime.now() - timedelta(hours=1), 5, 50)
# opt.save_constraint(datetime.now() - timedelta(hours=1), datetime.now() + timedelta(hours=2), 6, 60)
# opt.save_constraint(datetime.now() + timedelta(hours=3), datetime.now() + timedelta(hours=5), 7, 70)
# opt.save_constraint(datetime.now() + timedelta(hours=22), datetime.now() +timedelta(hours=26), 8, 80)
# opt.save_constraint(datetime.now() + timedelta(days=2), datetime.now() + timedelta(days=3), 9, 90)

# print("Prima dell'update:")
# print("Theta min:", opt.theta_min)
# print("Theta max:", opt.theta_max)

# # Aggiorna la finestra di ottimizzazione
# opt.update_opt_window()

# print("\nDopo l'update:")
# print("Theta min:", opt.theta_min)
# print("Theta max:", opt.theta_max)

