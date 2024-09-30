# Altre possibili librerie da importare:

# import arrow  # per gestire date e orari in vari formati (però mi sa che funziona solo per l'inglese)
# import dateparser # gestisce formati delle date in varie lingue, ma ha comunque funzionalità limitate per l'italiano
# from rasa_sdk.events import SlotSet

from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import json
from actions.monitoring import EnergyMonitoring
from actions.optimization import Appliance, Optimizer, PV
from datetime import datetime, timedelta
#
#

device_translation = {
     "washing_machine": "la lavatrice",
     "dryer": "l'asciugatrice",
     "dishwasher": "la lavastoviglie",
     "hvac":"il riscaldamento",
     "water_heater": "l'acqua calda"
}

def dateToString(start_time: datetime, end_time: datetime = None) -> str:
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)

    # Se viene passato solo start_time
    if start_time == end_time:
        if start_time.date() == today:
            return f"alle {start_time.strftime('%H:%M')}"
        elif start_time.date() == tomorrow:
            return f"alle {start_time.strftime('%H:%M')} di domani"
        else:
            return f"alle {start_time.strftime('%H:%M')} del {start_time.strftime('%d-%m-%Y')}"
    # Se viene passato un intervallo
    else:
        if start_time.date() == today and end_time.date() == today:
            return f"dalle {start_time.strftime('%H:%M')} alle {end_time.strftime('%H:%M')}"
        elif start_time.date() == tomorrow and end_time.date() == tomorrow:
            return f"dalle {start_time.strftime('%H:%M')} alle {end_time.strftime('%H:%M')} di domani"
        else:
            start_text = f"del {start_time.strftime('%d-%m-%Y')}" if start_time.date() != today and start_time.date() != tomorrow else ""
            end_text = f"del {end_time.strftime('%d-%m-%Y')}" if end_time.date() != today and end_time.date() != tomorrow else ""
            
            return f"dalle {start_time.strftime('%H:%M')} {start_text} alle {end_time.strftime('%H:%M')} {end_text}"

def time_constraint(tracker: Tracker):
     start_time = None
     end_time = None

     print(tracker.latest_message['entities'])
     for entity in tracker.latest_message['entities']:
          if entity['entity'] == 'time':
               print(entity)
               value = entity['value']
               print(value)
               # Se il valore è una stringa ISO 8601 singola
               if isinstance(value, str):
                    start_time = datetime.fromisoformat(value)
                    end_time = start_time  # Per un singolo tempo, start_time ed end_time acquisiscono lo stesso valore

               # Se il valore è un dizionario (intervallo di tempo)
               elif isinstance(value, dict):
                    if 'from' in value and 'to' in value:
                         start_time_str = value['from']
                         end_time_str = value['to']

                         start_time = datetime.fromisoformat(start_time_str)
                         end_time = datetime.fromisoformat(end_time_str)

                    elif 'value' in value:
                         start_time_str = value['value']
                         start_time = datetime.fromisoformat(start_time_str)
                         end_time = start_time  

     return start_time, end_time


class AnswerRequest(Action):
#
     def name(self) -> Text:
         return "answer_request"
#
     def run(self, dispatcher: CollectingDispatcher,
             tracker: Tracker,
             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
#
         dispatcher.utter_message(text="Per questa richiesta ho bisogno di accedere ad alcune informazioni nel sistema. Ti chiedo di pazientare qualche secondo. \n --- \n ")

         return []
     

class AnswerConsumptionRequest(Action):
    
     def name(self) -> Text:
          return "answer_consumption_request"
        
     def run(self, dispatcher: CollectingDispatcher,
             tracker: Tracker,
             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
         
          data = EnergyMonitoring()
          load, grid_import, from_pv, storage_pow = data.get_consumption_data()
          text =  f"Al momento stai consumando {load} kW, di cui {grid_import} dalla rete, {from_pv} dal fotovoltaico  \
                         e {storage_pow} dalla batteria."

          dispatcher.utter_message(text=text)

          return []
     
class AnswerRenewableRequest(Action):
    
     def name(self) -> Text:
          return "answer_renewable_request"
        
     def run(self, dispatcher: CollectingDispatcher,
             tracker: Tracker,
             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
          text = ""
          data = EnergyMonitoring()
          pv, storage_lev, storage_status, storage_pow, storage_on_charge = data.get_renwable_data()
          if storage_on_charge :
               text = f"Al momento i pannelli solari stanno producendo {pv} kW, di cui {storage_pow} kW sono diretti alla batteria"
          else:
               text = f"Al momento i pannelli solari stanno producendo {pv} kW"
          

          dispatcher.utter_message(text=text)

          return []
     
class AnswerOptimizationRequest(Action):

     def name(self) -> Text:
         return "answer_optimization_request"
     
     def run(self, dispatcher: CollectingDispatcher,
             tracker: Tracker,
             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
         
          text=""

          appliance = tracker.get_slot("device_name")
          start_time, end_time = time_constraint(tracker)


          print(appliance)

          if appliance is not None:
               # Chiamare il modulo Optimizer con gli slot forniti
               #opt = Optimizer(appliance)
               #pv = PV()
               #pv.set_pv_data(CONFIG_FILE)
               #forecast=pv.get_pv_forecast()
               #_, start_time, model_result = opt.grid_optimizer(start_time, forecast)
               model_result = 13.122#DA RIMUOVERE
               text= f"Se avvii {device_translation.get(appliance)} {dateToString(start_time, end_time)} consumerai dalla rete {model_result:.2f} kWh. Vuoi saperne di più?"
           
          else:
               text = "Mi servirebbe sapere quale elettrodomestico ti interessa"

          dispatcher.utter_message(text=text)
          return []
     
     

     

class ActOnDevice(Action):
#
     def name(self) -> Text:
         return "act_on_device"
#
     def run(self, dispatcher: CollectingDispatcher,
             tracker: Tracker,
             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
#
         dispatcher.utter_message(text="Mi spiace, al momento non posso interagire con i dispositivi della casa.")

         return []
     
class AnswerExplanationRequest(Action):
#
     def name(self) -> Text:
         return "answer_explanation_request"
#
     def run(self, dispatcher: CollectingDispatcher,
             tracker: Tracker,
             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
#
         dispatcher.utter_message(text="[TEMPLATE DA COMPLETARE]")

         return []


if __name__ == "__main__":
     monit = AnswerConsumptionRequest()
     monit.run()
