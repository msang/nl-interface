# Altre possibili librerie da importare:

# import arrow  # per gestire date e orari in vari formati (però mi sa che funziona solo per l'inglese)
# import dateparser # gestisce formati delle date in varie lingue, ma ha comunque funzionalità limitate per l'italiano
# from rasa_sdk.events import SlotSet

from typing import Any, Text, Dict, List, Tuple
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, Form, FollowupAction
import json, requests
from .monitoring import EnergyMonitoring
from .optimization import Appliance, Optimizer, PV
from datetime import datetime, timedelta
from .constraints_extractor import acquire_time_intervals, date_to_string, time_constraint
from .utils import date_to_string


device_translation = {
     "washing_machine": "la lavatrice",
     "dryer": "l'asciugatrice",
     "dishwasher": "la lavastoviglie",
     "hvac":"il riscaldamento",
     "water_heater": "l'acqua calda",
     "oven":"il forno"
}

bess_status={"Idle": "inattiva", 
             "Charging": "in carica",
             "Discharging": "in scarica"}


class AnswerMonitoringRequest(Action):
    
    def name(self):
        return "answer_monitoring_request"

    def run(self, dispatcher, tracker, domain):
        intent = tracker.latest_message['intent'].get('name')
        utterance = tracker.latest_message.get("text")
        em = EnergyMonitoring()
        energy_data=""

        try:

          if intent == "check_consumption":
               energy_data = em.get_consumption_info()   
          elif intent== "check_production":
               energy_data = em.get_production_info()

        except Exception as e:
             dispatcher.utter_message(text="Mi dispiace, non ho modo di recuperare i dati in questo momento. Richiedimelo più tardi.")
             
        try:               
               nlg_server_url = "http://10.25.0.23:5056/nlg"
               response = requests.post(nlg_server_url, json={"intent": intent,"utterance": utterance,"energy_data": energy_data})
               generated_text = response.json().get("text", "Mi dispiace, non ho modo di recuperare i dati in questo momento. Richiedimelo più tardi.")
               followup= "Vorresti chiedermi altro?"
               dispatcher.utter_message(text=f"{generated_text}\n{followup}")

        except Exception as e:
               text = f"Di seguito le informazioni richieste:\n{energy_data}\n{followup}"
               dispatcher.utter_message(text=text)
               print(f"Errore nel server NLG: {e}")
        
        
class AnswerOptimizationRequest(Action):

     def name(self) -> Text:
         return "answer_optimization_request"
     
     def run(self, dispatcher: CollectingDispatcher,
             tracker: Tracker,
             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
         
          text=""
          time_intervals=[]
          opt = Optimizer()
          try:
               app = tracker.get_slot("device_name")
               app_obj = Appliance(app)
               opt.set_appliance(app_obj)
               print(opt.appliance)
          except:
               opt.appliance=None
          #"""
          time_entities = [entity for entity in tracker.latest_message['entities'] if entity.get("entity") == "time"]
          #print(time_entities)

          if time_entities != []:
               time_intervals = time_constraint(time_entities[0])
               start_time, end_time = time_intervals[0]  
               print(f"\n\nSTART - END: {start_time} - {end_time}") 
          else:
               start_time = datetime.now() 
               print(f"\n\nSTART: {start_time}")
          #print(f"\n\nTIME INTERVALS: {time_intervals}")    
          #"""

          if opt.appliance is not None:
               if opt.appliance.is_tcl:
                    text="Modifico le impostazioni dell'ottimizzatore in base alla tua richiesta."
                    ## TODO:  richiama qui le azioni per il settaggio dei vincoli
               else:
                    ## richiama l'ottimizzatore base
                    pv = PV()
                    forecast=pv.get_pv_forecast()
                    #opt_start_time = start_time.hour+1
                    _, _, response = opt.grid_optimizer(start_time, forecast)
                    appliance_string = device_translation.get(opt.appliance.app_name)
                    text=f"Il momento migliore per avviare {appliance_string} potrebbe essere {response}."
          else:
               text="Non ho riconosciuto il dispositivo. Potresti riscriverlo?"
     
          dispatcher.utter_message(text=text)
          return []
            

class ValidateDeviceForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_device_form"

    async def validate_device_name(
        self,
        slot_value: Any, 
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:

        # Controlla se l'entità è accettabile
        if slot_value not in device_translation:
            dispatcher.utter_message(text="Dispositivo non riconosciuto. Potresti riscriverlo?")
            return [SlotSet("device_name", None)]  # Resetta lo slot per richiedere un nuovo input
        else:
            return [SlotSet("device_name", slot_value)]


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
               text=f"Al momento nessun elettrodomestico è in funzione."

          dispatcher.utter_message(text=text)


          return []


class ValidateTemperatureScheduleForm(FormValidationAction):

     def name(self) -> Text:
          return "validate_temperature_schedule_form"
     

     def validate_time(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
     ) -> Dict[Text, Any]:
          try:
               time_intervals = acquire_time_intervals(tracker) #TODO 21/01: ctrl perché prende tracker e non slot_value
               start_time, end_time = time_intervals[0]
               print("sono passato da time")
               if not time_intervals or len(time_intervals) == 0:
                    dispatcher.utter_message(text="Non ho trovato intervalli di tempo validi.")
                    return {"time": None}
               return {"start_time": start_time.isoformat(),"end_time": end_time.isoformat()}
          except Exception as e:
               dispatcher.utter_message(text="C'è stato un problema nell'estrazione degli orari.")
               return {"time": None}
          

     def validate_temperature(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        try:
            temperature = int(slot_value)
            print("sono passato da temperature")
            
            # Controllo intervallo di temperatura consentito #TODO 21/01: aggiungere qui un controllo dei valori di temp.
          #   if 10 <= temperature <= 30:
          #       return {"temperature": temperature}
          #   else:
          #       dispatcher.utter_message(text="La temperatura deve essere compresa tra 10°C e 30°C.")
          #       return {"temperature": None}
            return {"temperature": temperature}
        
        except ValueError:
            dispatcher.utter_message(text="Non ho riconosciuto una temperatura valida. Inserisci un valore numerico.")
            return {"temperature": None}
        

     def validate_device_name(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
          
          print("sono passato da device")
          if slot_value in device_translation:
               return {"device_name": slot_value}
          else:
               dispatcher.utter_message(text="Non ho riconosciuto il dispositivo. Potresti riscriverlo?")
               return {"device_name": None}
     

class AnswerSetConstraint(Action):
    def name(self) -> Text:
        return "answer_set_constraint"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
          text=""
          opt = FakeOptimizer()
         
          appliance = tracker.get_slot("device_name")
          print(f"Appliance: {appliance}")
          temperature = tracker.get_slot("temperature")
          print(f"Temperature: {temperature}")
          start_time = datetime.fromisoformat(tracker.get_slot("start_time"))
          end_time = datetime.fromisoformat(tracker.get_slot("end_time"))
          print("Time window: ",start_time, end_time)
      
          text= f"Avrai {device_translation[appliance]} ad una temperatura di {temperature} {date_to_string(start_time, end_time)}. Va bene?"
          opt.save_constraint(appliance, start_time,end_time,temperature-1,temperature+1)
          dispatcher.utter_message(text=text)
          
          return [SlotSet("device_name", None),
            SlotSet("temperature", None),
            SlotSet("time", None),
            SlotSet("start_time", None),
            SlotSet("end_time", None),]
    

if __name__ == "__main__":
     slots = {"source_name": "bess","device_name":"oven", "time": "2025-01-14T16:30:12.000+01:00", "temperature": 55}
     intent = {"name": "check_production","text": "l'azione mi serve adesso"}
     entities = [{
            "start": 18,
            "end": 24,
            "text": "adesso",
            "value": "2025-01-14T16:30:12.000+01:00",
            "confidence": 1,
            "additional_info": {
              "values": [
                {
                  "value": "2025-01-14T16:30:12.000+01:00",
                  "grain": "second",
                  "type": "value"
                }
              ],
              "value": "2025-01-14T16:30:12.000+01:00",
              "grain": "second",
              "type": "value"
            },
            "entity": "time",
            "extractor": "DucklingEntityExtractor"
          }]
     tracker = Tracker(sender_id="x", slots=slots, latest_message={"intent": intent, "entities": entities}, events=[], paused=False, followup_action=None, active_loop=None, latest_action_name=None)
     dispatcher = CollectingDispatcher()
     domain={}
     monit = AnswerOptimizationRequest()
     monit.run(dispatcher, tracker, domain)