# Altre possibili librerie da importare:

# import arrow  # per gestire date e orari in vari formati (però mi sa che funziona solo per l'inglese)
# import dateparser # gestisce formati delle date in varie lingue, ma ha comunque funzionalità limitate per l'italiano
# from rasa_sdk.events import SlotSet

from typing import Any, Text, Dict, List, Tuple
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, Form, FollowupAction
import matlab.engine
import json
from actions.monitoring import EnergyMonitoring
from actions.optimization import Appliance, Optimizer, PV
from datetime import datetime, timedelta
from .constraints_extractor import acquire_constraints, date_to_string, time_constraint
from .fake_optimizer import FakeOptimizer
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
          opt = FakeOptimizer()

          appliance = tracker.get_slot("device_name")
          print(f"Appliance: {appliance}")
     
          time_intervals,temperature = acquire_constraints(tracker)

          print(f"\n\nTIME INTERVALS: {time_intervals}\n\nTEMPERATURE: {temperature}\n\n")

          start_time, end_time = time_intervals[0]

     
     
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
                    if temperature is not None:
                         text= f"Se avvii {appliance_string} {date_to_string(start_time, end_time)} ad una temperatura di {temperature} gradi consumerai dalla rete {model_result:.2f} kWh. Vuoi saperne di più?"
                         opt.save_constraint(start_time,end_time,temperature-1,temperature+1)
                    else:
                         text= f"Se avvii {appliance_string} {date_to_string(start_time, end_time)} consumerai dalla rete {model_result:.2f} kWh. Vuoi saperne di più?"
  
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
               text=f"Al momento sono in funzione la lavatrice e lo scaldabagno."

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
               time_intervals = acquire_constraints(tracker)
               start_time, end_time = time_intervals[0]
               print("sono passato da time")
               if not time_intervals or len(time_intervals) == 0:
                   # dispatcher.utter_message(text="Non ho trovato intervalli di tempo validi.")
                    return {"time": None}
               return {"start_time": start_time.isoformat(),"end_time": end_time.isoformat()}
          except Exception as e:
               #dispatcher.utter_message(text="C'è stato un problema nell'estrazione degli orari.")
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
            
            # Controllo intervallo di temperatura consentito 
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
               #dispatcher.utter_message(text="Non ho riconosciuto il dispositivo. Potresti riscriverlo?")
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
      
          start_time = datetime.fromisoformat(tracker.get_slot("start_time"))
          end_time = datetime.fromisoformat(tracker.get_slot("end_time"))

          print(start_time)

          print(end_time)
      
          text= f"Avrai {device_translation[appliance]} ad una temperatura di {temperature} {date_to_string(start_time, end_time)}. Va bene?"
          opt.save_constraint(appliance, start_time,end_time,temperature-1,temperature+1)
         
          
          dispatcher.utter_message(text=text)
          
          return [SlotSet("device_name", None),
            SlotSet("temperature", None),
            SlotSet("time", None),
            SlotSet("start_time", None),
            SlotSet("end_time", None),]
    
if __name__ == "__main__":
     monit = AnswerConsumptionRequest()
     monit.run()