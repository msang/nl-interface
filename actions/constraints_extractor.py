from typing import Any, Text, Dict, List, Tuple
from rasa_sdk import Tracker
from datetime import datetime, timedelta

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

def acquire_constraints(tracker: Tracker) -> List[Tuple[datetime, datetime]]:

    time_intervals = []
    # temperature = None
    for entity in tracker.latest_message['entities']:
        if entity['entity'] == 'time':
            time_intervals = time_constraint(entity)
        #elif entity['entity'] == 'temperature':
        #    temperature = temperature_constraint(entity)
    current_time = datetime.now()         
    return time_intervals if time_intervals else [(current_time, current_time)]


def adjust_end_interval(end_time, grain):
     if grain == "minute":
          end_time -= timedelta(minutes=1)
     elif grain == "hour":
          end_time -= timedelta(hours=1)
     elif grain == "day":
          end_time -= timedelta(days=1)
     return end_time

     
def time_constraint(entity):

    start_time = None
    end_time = None

    time_intervals = []

    values = entity['additional_info']['values']
    i=0
    for value in values:
        if value['type'] == 'value':
                start_time = datetime.fromisoformat(value['value']).replace(tzinfo=None)
                end_time = start_time  # Per un tempo singolo, start_time ed end_time acquisiscono lo stesso valore
        elif value['type'] == 'interval':
                if 'from' in value:
                    start_time_str = value['from']['value']
                    start_time = datetime.fromisoformat(start_time_str).replace(tzinfo=None)

                if 'to' in value:
                    end_time_str = value['to']['value']
                    grain = value['to']['grain']
                    end_time = datetime.fromisoformat(end_time_str).replace(tzinfo=None)
                    if start_time is not None:      
                        end_time = adjust_end_interval(end_time, grain) 

        time_intervals.append((start_time, end_time))
        i+=1
    
    return time_intervals 

def temperature_constraint(entity):
    
    return entity['additional_info']['value']

