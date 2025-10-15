from typing import Any, Text, Dict, List, Tuple
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, Form, FollowupAction
from datetime import datetime, timedelta
import json, logging, pytz, random, requests
from .monitoring import EnergyMonitoring
from .optimization import Optimizer
from .appliance import Appliance
from .forecasting import MLPModel
from .utils import date_to_string

logger = logging.getLogger(__name__)


def send_to_nlg(intent: str, utterance: str, energy_data: str) -> str:
    """
    Invia una richiesta al server NLG e restituisce o il testo generato o un fallback.
    """
    try:
        nlg_server_url = "http://localhost:5056/nlg"
        payload = {
            "intent": intent,
            "utterance": utterance,
            "energy_data": energy_data
        }

        headers = {"Content-Type": "application/json"}
        response = requests.post(nlg_server_url, json=payload, headers=headers, timeout=120)
        response.raise_for_status()

        return response.json().get("text", "")

    except (requests.exceptions.Timeout, 
            requests.exceptions.HTTPError, 
            requests.exceptions.RequestException, 
            ValueError) as e:
        logger.error(f"Errore nella comunicazione con il server NLG: {e}")
        return f"Di seguito le informazioni richieste:\n{energy_data}"


class AnswerMonitoringRequest(Action):
    
    def name(self):
        return "answer_monitoring_request"

    def run(self, dispatcher, tracker, domain):
        print(self.name)
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
        
        print(self.name)
        opt = Optimizer()
        user_start = user_end = None #TODO: aggiornare qui
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
                user_start, user_end = ("","")  #TODO: aggiornare qui
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

        print(self.name)
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


class AnswerSellingAdviceRequest(Action):

    def name(self) -> Text:
        return "answer_selling_advice_request"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        print(self.name)
        intent = tracker.latest_message['intent'].get('name')
        utterance = tracker.latest_message.get("text")

        try:
            energy_data = _create_rec_profiles()
        except Exception as e:
            logger.error(f"Errore durante l'elaborazione dei dati: {e}")
            dispatcher.utter_message(text="Mi dispiace, non ho modo di recuperare i dati relativi alla comunità in questo momento. Richiedimelo più tardi.")
            return []

        generated_text = send_to_nlg(intent, utterance, energy_data)
        #print(generated_text)
        dispatcher.utter_message(text=generated_text)
        return []

def _create_rec_profiles():
    em = EnergyMonitoring()
    em.fetch_energy_details()
    user_p = em.daily_production
    user_c = em.daily_consumption
    ###genero profili random di produzione e consumo
    SYNTH_PROSUMERS = 2
    SYNTH_CONSUMERS = 4
    random_production = [round(user_p * random.random(), 2) for i in range(SYNTH_PROSUMERS)] 
    random_consumption = [round(user_c * random.random(), 2) for i in range(SYNTH_CONSUMERS)]

    energy_data = f"""- Peer1 (Utente): produzione: {user_p} - consumo: {user_c}
    - Peer2: produzione: {random_production[0]} - consumo: {random_consumption[0]}
    - Peer3: produzione: {random_production[1]} - consumo: {random_consumption[1]}
    - Peer4: consumo: {random_consumption[2]}
    - Peer5: consumo: {random_consumption[3]}
    """
    
    return energy_data
    

if __name__ == "__main__":
    intent = {"name": "ask_selling_advice"}
    latest_message = {
                "intent": intent,
                "text": "ho prodotto un sacco e non voglio regalarla alla rete, dimmi a chi e a quanto vendere",  # <-- Spostato fuori da 'intent'
                "entities": []
            }
    tracker = Tracker(
        sender_id="x",
        slots=[],
        latest_message=latest_message,
        events=[],
        paused=False,
        followup_action=None,
        active_loop=None,
        latest_action_name=None
    )
    dispatcher = CollectingDispatcher()
    domain={}
    monit = AnswerSellingAdviceRequest()
    monit.run(dispatcher, tracker, domain)