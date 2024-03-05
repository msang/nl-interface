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
#
#

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
         
          data = EnergyMonitoring()
          load, grid_import, from_pv, storage_pow = data.get_renwable_data()
          text = f"Al momento stai consumando {load} kW, di cui {grid_import} dalla rete, {from_pv} dal fotovoltaico  \
                         e {storage_pow} dalla batteria."

          dispatcher.utter_message(text=text)

          return []
     
class AnswerOptimizationRequest(Action):

     def name(self) -> Text:
         return "answer_optimization_request"
     
     def run(self, dispatcher: CollectingDispatcher,
             tracker: Tracker,
             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
         
          ##gli slot che deve prendere dall'utente sono relativi all'elettrodomestico e all'orario di avvio
          appliance = tracker.get_slot("device_name")
          start_time = 7  ### PER ORA DEFINISCO QUI
          print(appliance)
          text=""

          if appliance is not None:
               # Chiamare il modulo Optimizer con gli slot forniti
               opt = Optimizer(appliance)
               pv = PV()
               #pv.set_pv_data(CONFIG_FILE)
               forecast=pv.get_pv_forecast()
               _, start_time, model_result = opt.grid_optimizer(start_time, forecast)
               text = f"Se avvii l'elettrodomestico alle {start_time} consumerai dalla rete {model_result:.2f} kWh. Vuoi saperne di più?"
          else:
               dispatcher.utter_message(text="Mi servirebbe sapere quale elettrodomestico ti interessa")

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
         dispatcher.utter_message(text="[TEMPLATE DA COMPETARE]")

         return []


if __name__ == "__main__":
     monit = AnswerConsumptionRequest()
     monit.run()
