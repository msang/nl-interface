# Altre possibili librerie da importare:

# import arrow  # per gestire date e orari in vari formati (però mi sa che funziona solo per l'inglese)
# import dateparser # gestisce formati delle date in varie lingue, ma ha comunque funzionalità limitate per l'italiano
# from rasa_sdk.events import SlotSet

from typing import Any, Text, Dict, List, Tuple
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, Form
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

bess_status={"Idle": "inattiva", 
             "Charging": "in carica",
             "Discharging": "in scarica"}

def dateToString(start_time: datetime, end_time: datetime = None) -> str:
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

def time_constraint(tracker: Tracker) -> List[Tuple[datetime, datetime]]:
     start_time = None
     end_time = None

     time_intervals = []

     for entity in tracker.latest_message['entities']:
          if entity['entity'] == 'time':
               print(f"\nENTITA: {entity}\n")
               values = entity['additional_info']['values']
               print(f"\values: {values}\n")
               i=0
               for value in values:
                    print(f'Value {i}: {value}')
                    if value['type'] == 'value':
                         start_time = datetime.fromisoformat(value['value'])
                         end_time = start_time  # Per un tempo singolo, start_time ed end_time acquisiscono lo stesso valore
                    elif value['type'] == 'interval':
                         if 'from' in value:
                              start_time_str = value['from']['value']
                              print(f"\nStart: {start_time_str}\n\n")
                              start_time = datetime.fromisoformat(start_time_str)

                         if 'to' in value:
                              end_time_str = value['to']['value']
                              print(f"\nEnd: {end_time_str}\n\n")
                              grain = value['to']['grain']
                              end_time = datetime.fromisoformat(end_time_str)   
                              if start_time is not None:      
                                   end_time = adjust_end_interval(end_time, grain) 

                    time_intervals.append((start_time, end_time))
                    
                    i+=1
     current_time = datetime.now()
     return time_intervals or [(current_time, current_time)]

def adjust_end_interval(end_time, grain):
     if grain == "minute":
          end_time -= timedelta(minutes=1)
     elif grain == "hour":
          end_time -= timedelta(hours=1)
     elif grain == "day":
          end_time -= timedelta(days=1)
     return end_time

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
          source = tracker.get_slot("source_name")
          print(source)
          pv, storage_lev, storage_status, storage_pow, storage_on_charge = data.get_renewable_data()
          if storage_on_charge :
               text = f"Al momento i pannelli solari stanno producendo {pv} kW, di cui {storage_pow} kW sono diretti alla batteria"
          if source == "bess":
               text = f"Al momento la batteria è al {storage_lev}% ed è {bess_status[storage_status]}"
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
          time_intervals = time_constraint(tracker)
          print(time_intervals)
          start_time, end_time = time_intervals[0]

          print(appliance)
     
     
          if appliance is not None:
               # Chiamare il modulo Optimizer con gli slot forniti
               #opt = Optimizer(appliance)
               #pv = PV()
               #pv.set_pv_data(CONFIG_FILE)
               #forecast=pv.get_pv_forecast()
               #_, start_time, model_result = opt.grid_optimizer(start_time, forecast)

               model_result = 13.122#DA RIMUOVERE

               appliance_string = device_translation.get(appliance)
               if(appliance_string is not None):
                    text= f"Se avvii {appliance_string} {dateToString(start_time, end_time)} consumerai dalla rete {model_result:.2f} kWh. Vuoi saperne di più?"
               else:
                    dispatcher.utter_message(text="Non ho riconosciuto il dispositivo. Potresti riscriverlo?")
                    #return [Form("device_form")]
          
          else:
               text = "Mi servirebbe sapere quale elettrodomestico ti interessa"
          
          dispatcher.utter_message(text=text)
          return []
            

class ValidateDeviceForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_device_form"

    async def validate_device_name(
        self,
        slot_value: Any, #Verificare se Any o text
        dispatcher: CollectingDispatcher,
        tracker: "Tracker",
        domain: "DomainDict"
    ) -> Dict[Text, Any]:

        # Controlla se l'entità è accettabile
        if slot_value not in device_translation:
            dispatcher.utter_message(text="Dispositivo non riconosciuto. Potresti riscriverlo?")
            return {"device_name": None}  # Resetta lo slot per richiedere un nuovo input
        else:
            return {"device_name": slot_value}


class AnswerActOnDevice(Action):
#
     def name(self) -> Text:
         return "answer_act_on_device"

     def run(self, dispatcher: CollectingDispatcher,
             tracker: Tracker,
             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
          text = ""
          appliance = tracker.get_slot("device_name")
          if appliance is not None:
               text = f"Mi spiace, al momento non posso interagire con {device_translation[appliance]}."
          else:
               text = "Mi spiace, al momento non posso interagire con gli elettrodomestici."
          dispatcher.utter_message(text=text)
          return []
     

class AnswerStatusRequest(Action):
#
     def name(self) -> Text:
         return "answer_status_request"
#
     def run(self, dispatcher: CollectingDispatcher,
             tracker: Tracker,
             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
          appliance = tracker.get_slot("device_name")
          if appliance is not None:
               text=f"Al momento {device_translation[appliance]} risulta in funzione."
          else:
               text=f"Al momento non rilevo nessun elettrodomestico."

          dispatcher.utter_message(text=text)


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
