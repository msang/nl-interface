from datetime import timedelta, datetime
from typing import List, Tuple
import numpy as np


def create_time_intervals(T:int, delta:int) -> List:
    now = datetime.now()
    step = timedelta(minutes=delta)
    time_intervals = []

    for i in range(T):
        time_intervals.append(now)
        now+=step
        
    return time_intervals


def date_to_string(start_time: datetime, end_time: datetime = None) -> str:
     today = datetime.now().date()
     tomorrow = today + timedelta(days=1)
     text = ""

    # Se viene passato solo start_time
     if start_time == end_time:
          if start_time.date() == today:
               text = f"alle {start_time.strftime('%H:%M')}"
          elif start_time.date() == tomorrow:
               text = f"alle {start_time.strftime('%H:%M')} di domani"
          else:
               text = f"alle {start_time.strftime('%H:%M')} del {start_time.strftime('%d/%m/%Y')}"
     # Se viene passato un intervallo illimitato inferiormente (stringhe temporanee)
     elif start_time is None:
        if end_time.date() == today:
            text = f"prima delle {end_time.strftime('%H:%M')}"
        elif end_time.date() == tomorrow:
            text = f"prima delle {end_time.strftime('%H:%M')} di domani"
        else:
            text = f"prima delle {end_time.strftime('%H:%M')} del {end_time.strftime('%d/%m/%Y')}"
     # Se viene passato un intervallo illimitato superiormente (stringhe temporanee)
     elif end_time is None:
        if start_time.date() == today:
            text = f"dopo le {start_time.strftime('%H:%M')}"
        elif start_time.date() == tomorrow:
            text = f"dopo le {start_time.strftime('%H:%M')} di domani"
        else:
            text = f"dopo le {start_time.strftime('%H:%M')} del {start_time.strftime('%d/%m/%Y')}"
     # Se viene passato un intervallo
     else:
          if start_time.date() == today and end_time.date() == today:
               text = f"dalle {start_time.strftime('%H:%M')} alle {end_time.strftime('%H:%M')}"
          elif start_time.date() == tomorrow and end_time.date() == tomorrow:
               text = f"dalle {start_time.strftime('%H:%M')} alle {end_time.strftime('%H:%M')} di domani"
          else:
               start_text = f"del {start_time.strftime('%d/%m/%Y')}" if start_time.date() != today and start_time.date() != tomorrow else ""
               end_text = f"del {end_time.strftime('%d/%m/%Y')}" if end_time.date() != today and end_time.date() != tomorrow else ""
               
               text = f"dalle {start_time.strftime('%H:%M')} {start_text} alle {end_time.strftime('%H:%M')} {end_text}"
     return text


def create_matrix(time_steps:range, time_intervals:list, grid_import) -> np.array:

    matrix = []
     
    for interval, t in zip(time_intervals, time_steps):        
        row = [interval, grid_import[t]]
        matrix.append(row)

    return np.array(matrix)


def get_idx(pv_intervals:List[datetime], appl_time: datetime) -> int:
    """
    restituisce la posizione dell'array in cui l'orario di avvio dell'elettrodomestico rientra nella fascia oraria 
    di predizione del pv (rilasciata a intervalli 30 min)
    """
    start_idx=0
    for i, pv_interval in enumerate(pv_intervals):
        #print(pv_interval, i)
        if appl_time == pv_interval:
            start_idx = i
        elif appl_time > pv_interval and appl_time <= pv_intervals[i+1]:
            start_idx = i+1

    return start_idx


def redefine_values(time_intervals: list, time_resolution:int) -> list:
    #per ora le sole altre risoluzioni ammesse sono di 15 o 60 min.
    if time_resolution==15:
        time_intervals = [t/2 for t in time_intervals for _ in range(2)]
    elif time_resolution==60:
        if len(time_intervals) % 2 == 0:
            time_intervals = [time_intervals[e] + time_intervals[e+1] for e in range(0, len(time_intervals), 2)]
        else:
            time_intervals = [time_intervals[e] + time_intervals[e+1] for e in range(0, len(time_intervals) - 1, 2)]

    return time_intervals


def redefine_intervals(time_intervals: list, time_resolution:int) -> list:
      
    if time_resolution == 15:
        time_intervals = [t + timedelta(minutes=i * time_resolution) for t in time_intervals for i in range(2)]
   
    elif time_resolution==60:
        time_intervals = [t for i, t in enumerate(time_intervals) if i % 2 == 0]

    return time_intervals
        

def find_min_sum(grid_import, time_intervals, time_window: int=0) -> Tuple[datetime, datetime, float]:

    min_sum=float('inf')
    start = end = 0

    for i in range(0, len(grid_import) - time_window + 1):
        current_sum = np.sum(grid_import[i:i+time_window])  
        #print(i, "import:", grid_import[i], "somma temp. da ", i, "a", i + time_window - 1, current_sum)
        if current_sum < min_sum:
            min_sum = current_sum
            start = i

    end = start+time_window
    start_time = time_intervals[start]
    end_time= time_intervals[end]

    return start_time, end_time, round(min_sum, 2)


def verbalize_result(T, delta, grid_import, time_window=0):
    time_intervals = create_time_intervals(T, delta) #crea array di oggetti datetime a partire dall'ora corrente; T è uguale alla lunghezza dell'array delle previsioni PV
    start, end, _ = find_min_sum(grid_import, time_intervals, time_window)

    return date_to_string(start, end)


if __name__ == "__main__":
    import random
    T = 10
    delta = 30
    intervals = create_time_intervals(T,delta)
    text0 = date_to_string(None, intervals[0])
    text = date_to_string(intervals[0])
    text1 = date_to_string(intervals[0], intervals[1])
    #print(text0)
    #print(text)
    #print(text1)
    #random_grid_imp = [round(random.uniform(0,2), 2) for i in range(T)] #[0.88, 1.64, 0.14, 0.11, 0.66, 0.41, 1.51, 1.93, 1.09, 0.71, 0.69, 0.13]
    #time_steps=range(12)
    #matrix = create_matrix(time_steps, intervals, random_grid_imp)
    #print(matrix)
    #da, a, somma = find_min_sum(random_grid_imp, intervals, 4)
    #print(da, a , somma)
    #text4 = date_to_string(da, a)
    #print(text4)
    #print(intervals)
    #print(datetime.now())
    print(get_idx(intervals, datetime.now()))

