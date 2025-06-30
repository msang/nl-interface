from typing import Any, Text, Dict, List, Tuple
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, Form, FollowupAction
import json, logging, requests
from .monitoring import EnergyMonitoring
from .optimization import Optimizer
from .appliance import Appliance
from .forecasting import MLPModel
from datetime import datetime, timedelta
from .utils import date_to_string


logger = logging.getLogger(__name__)


def send_to_nlg(intent: str, utterance: str, energy_data: str) -> str:
    """
    Invia una richiesta al server NLG e restituisce il testo generato o fallback.
    """
    try:
        nlg_server_url = "http://localhost:5056/nlg"
        payload = {
            "intent": intent,
            "utterance": utterance,
            "energy_data": energy_data
        }

        headers = {"Content-Type": "application/json"}
        response = requests.post(nlg_server_url, json=payload, headers=headers, timeout=90)
        response.raise_for_status()

        return response.json().get("text", "")

    except (requests.exceptions.Timeout, 
            requests.exceptions.HTTPError, 
            requests.exceptions.RequestException, 
            ValueError) as e:
        #Exception as e:
        logger.error(f"Errore nella comunicazione con il server NLG: {e}")
        return f"Di seguito le informazioni richieste:\n{energy_data}"



class AnswerMonitoringRequest(Action):
    
    def name(self):
        return "answer_monitoring_request"

    def run(self, dispatcher, tracker, domain):
        intent = tracker.latest_message['intent'].get('name')
        utterance = tracker.latest_message.get("text")
        em = EnergyMonitoring()
        energy_data = ""

        if em.api is None:
            dispatcher.utter_message(text="Mi dispiace, non ho modo di recuperare i dati in questo momento. Richiedimelo più tardi.")
            return []

        try:
            em.update_all_data()
            if intent == "check_consumption":
                energy_data = em.get_consumption_info()   
            elif intent == "check_production":
                energy_data = em.get_production_info()
        except Exception as e:
            dispatcher.utter_message(text="Mi dispiace, non ho modo di recuperare i dati in questo momento. Richiedimelo più tardi.")
            return []

        generated_text = send_to_nlg(intent, utterance, energy_data)
        dispatcher.utter_message(text=generated_text)
        return []



class AnswerOptimizationRequest(Action):

    def name(self) -> Text:
        return "answer_optimization_request"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        opt = Optimizer()
        user_start = user_end = None
        opt_start = datetime.now()
        intent = tracker.latest_message['intent'].get('name')
        utterance = tracker.latest_message.get("text")

        try:
            app = tracker.get_slot("device_name") or "hvac"
            opt.appliance = Appliance(app)
        except Exception:
            opt.appliance = Appliance("hvac")

        try:
            print(intent)
            if intent == "set_constraints":
                user_start, user_end = ("","")
            energy_data = opt.grid_optimizer(opt_start, user_start, user_end)
        except Exception as e:
            logger.error(f"Errore durante l'ottimizzazione: {e}")
            dispatcher.utter_message(text="Mi dispiace, non ho modo di recuperare i dati dell'ottimizzatore in questo momento. Richiedimelo più tardi.")
            return []

        generated_text = send_to_nlg(intent, utterance, energy_data)
        dispatcher.utter_message(text=generated_text)
        return []


class AnswerNetLoadForecastRequest(Action):

    def name(self) -> Text:
        return "answer_netload_forecast_request"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        intent = tracker.latest_message['intent'].get('name')
        utterance = tracker.latest_message.get("text")

        try:
            mlp=MLPModel()
            latitude = 39.2305400
            longitude = 9.1191700
            now = datetime.now()
            local_timezone = pytz.timezone("Europe/Rome")
            start_date = now.astimezone(local_timezone).replace(second=0, microsecond=0).replace(tzinfo=None)
            end_date = start_date + timedelta(hours=24) 
            energy_data =  mlp.run_pipeline(latitude, longitude, start_date, end_date)

        except Exception as e:
            logger.error(f"Errore durante l'elaborazione delle predizioni: {e}")
            dispatcher.utter_message(text="Mi dispiace, non ho modo di recuperare i dati in questo momento. Richiedimelo più tardi.")
            return []

        generated_text = send_to_nlg(intent, utterance, energy_data)
        dispatcher.utter_message(text=generated_text)
        return []


if __name__ == "__main__":
     slots = {"device_name":"hvac", "time": "2025-01-14T16:30:12.000+01:00", "temperature": 55}
     #intent = {"name": "check_production","text": "l'azione mi serve adesso"}
     intent = {"name": "ask_optimization","text": "quando usare le pompe"}
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
     #opt = 