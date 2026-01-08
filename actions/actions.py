from typing import Any, Text, Dict, List, Tuple
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, Form, FollowupAction
from datetime import datetime, timedelta
import argparse, json, logging, pytz, random, requests, sys
from .monitoring import EnergyMonitoring
from .optimization import Optimizer
from .appliance import Appliance
from .forecasting.MLPRegressor import SolarMLPModel
from .forecasting.NetLoadRegressor import NetLoadMLPModel
from .forecasting.LSTMRegressor import SolarLSTMModel
from .utils import extract_entity_text

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)  #-->manda tutti i log sulla console standard, e di rimando, nel file actions.log
    ]
)

logger = logging.getLogger(__name__)


########
# ---- cache globale ----
CACHE = {
    "ask_optimization": None,
    "ask_netload_forecast": None,
    "timestamp": None
}
###########


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
        print(energy_data)
        return f"Di seguito le informazioni richieste:\n{energy_data}"


class AnswerMonitoringRequest(Action):
    
    def name(self):
        return "answer_monitoring_request"

    def run(self, dispatcher, tracker, domain):
        print(self.name,flush=True)
        intent = tracker.latest_message['intent'].get('name')
        utterance = tracker.latest_message.get("text")
        em = EnergyMonitoring()
        energy_data = ""

        if em.api is None:
            logger.warning("API non disponibile")
            dispatcher.utter_message(text="Mi dispiace, non ho modo di recuperare i dati in questo momento. Richiedimelo più tardi.")
            return []

        try:
            print(intent, flush=True)
            em.update_all_data()
            if intent == "check_consumption":
                energy_data = em.get_consumption_info()   
            elif intent == "check_production":
                energy_data = em.get_production_info()
        except Exception as e:
            logger.error(f"Errore nel recupero dei dati: {e}", exc_info=True) #exc_info stampa il traceback completo
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
        
        print(self.name,flush=True) #flush consente la stampa nel file di log
        intent = tracker.latest_message['intent'].get('name')
        print(intent, flush=True)
        utterance = tracker.latest_message.get("text")

        appliance = tracker.get_slot("appliance")
        user_preference = None

        for ent in tracker.latest_message.get("entities", []):
            if ent.get("entity") == "constr_time":
                user_preference = utterance[ent["start"]:ent["end"]]
        print(appliance,user_preference )
        opt = Optimizer()
        opt.start = datetime.now().astimezone(pytz.timezone("Europe/Rome")).replace(second=0, microsecond=0).replace(tzinfo=None)
        #"""
        if CACHE.get(intent) is not None:
            energy_data = CACHE[intent]
            print("Energy_data già presente")
        else:
            try:
                opt.data_folder='forecasting'
                if user_preference is not None:
                    energy_data = opt.ec_optimizer(appliance, user_preference)
                else:                   
                    energy_data = opt.ec_optimizer()
            except Exception as e:
                logger.error(f"Errore durante l'ottimizzazione: {e}", exc_info=True)
                dispatcher.utter_message(text="Mi dispiace, non ho modo di recuperare i dati dell'ottimizzatore in questo momento. Richiedimelo più tardi.")                
                return []

            print("Cache vuota")
            CACHE[intent] = energy_data
            CACHE["timestamp"] = datetime.now()

        generated_text = send_to_nlg(intent, utterance, energy_data)
        dispatcher.utter_message(text=generated_text)
        #"""
        return []


class AnswerNetLoadForecastRequest(Action):

    def name(self) -> Text:
        return "answer_netload_forecast_request"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        print(self.name, flush=True)
        intent = tracker.latest_message['intent'].get('name')
        print(intent, flush=True)
        utterance = tracker.latest_message.get("text")

        try:
            mlp=NetLoadMLPModel()
            latitude = 39.2305400
            longitude = 9.1191700
            now = datetime.now()
            local_timezone = pytz.timezone("Europe/Rome")
            start_date = now.astimezone(local_timezone).replace(second=0, microsecond=0).replace(tzinfo=None)
            end_date = start_date + timedelta(hours=24) 
            energy_data =  mlp.run_pipeline(latitude, longitude, start_date, end_date)

        except Exception as e:
            logger.error(f"Errore durante l'elaborazione delle predizioni: {e}", exc_info=True)
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

        print(self.name, flush=True)
        intent = tracker.latest_message['intent'].get('name')
        print(intent, flush=True)
        utterance = tracker.latest_message.get("text")

        try:
            energy_data = _create_rec_profiles()
        except Exception as e:
            logger.error(f"Errore durante l'elaborazione dei dati: {e}", exc_info=True)
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
    ### profili random di produzione e consumo
    SYNTH_PROSUMERS = 2
    SYNTH_CONSUMERS = 4
    random_production = [round(user_p * random.random(), 2) for i in range(SYNTH_PROSUMERS)] 
    random_consumption = [round(user_c * random.random(), 2) for i in range(SYNTH_CONSUMERS)]

    energy_data = f"""- Utente: produzione: {user_p} - consumo: {user_c}
    - Peer2: produzione: {random_production[0]} - consumo: {random_consumption[0]}
    - Peer3: produzione: {random_production[1]} - consumo: {random_consumption[1]}
    - Peer4: consumo: {random_consumption[2]}
    - Peer5: consumo: {random_consumption[3]}
    """
    
    return energy_data
    

if __name__ == "__main__":
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--intent", default="ask_optimization")
    parser.add_argument("-u", "--utterance", default="quale orario è più efficiente per lo scaldabagno? vorrei usarlo adesso")
    args = parser.parse_args()
    
    entities = [{
        "entity": "appliance",
        "value": "water_heater",
        "start": 38,
        "end": 49,
        "confidence": 1.0
    }, 
      {
        "entity": "constr_time",
        "start": 64,
        "end": 71,
        "confidence": 1.0
    }
    ]

    latest_message = {
        "intent": {
            "name": args.intent,
            "confidence": 1.0
        },
        "text": args.utterance,
        "entities": entities
    }

    slots = {
        "appliance": "water_heater"
    }

    tracker = Tracker(
        sender_id="test_user",
        slots=slots,                      # <-- slot corretti
        latest_message=latest_message,    # <-- messaggio completo
        events=[],
        paused=False,
        followup_action=None,
        active_loop=None,
        latest_action_name=None
    )

    dispatcher = CollectingDispatcher()
    domain={}
    monit = AnswerOptimizationRequest()
    monit.run(dispatcher, tracker, domain)
    """
    # Mappa intent → classe della custom action
    intent_action_map = {
        "ask_optimization": AnswerOptimizationRequest,
        "ask_netload_forecast": AnswerNetLoadForecastRequest,
        "check_consumption": AnswerMonitoringRequest,
        "check_production": AnswerMonitoringRequest
    }

    # Utterance di test per ciascun intent
    utterances = {
        "ask_optimization": "quale orario è più efficiente per lo scaldabagno? vorrei usarlo adesso",
        "ask_netload_forecast": "mi puoi dare le previsioni di carico netto per domani?",
        "check_consumption": "vorrei sapere i consumi di ieri",
        "check_production": "quanta energia ho prodotto la settimana scorsa?"
    }

    # Entità di test (puoi personalizzarle)
    base_entities = [
        {
            "entity": "appliance",
            "value": "water_heater",
            "start": 38,
            "end": 49,
            "confidence": 1.0
        },
        {
            "entity": "constr_time",
            "start": 64,
            "end": 71,
            "confidence": 1.0
        }
    ]

    # Lista per salvare risultati
    results = []

    # Loop su ciascun intent
    for intent, action_class in intent_action_map.items():
        print(f"\n TEST INTENT: {intent}")

        for i in range(1):
            print(f"  → iterazione {i+1}/10")

            # Costruzione latest_message
            latest_message = {
                "intent": {
                    "name": intent,
                    "confidence": 1.0
                },
                "text": utterances[intent],
                "entities": base_entities
            }

            # Slots
            slots = {"appliance": "water_heater"}

            # Tracker
            tracker = Tracker(
                sender_id=f"test_user_{intent}_{i}",
                slots=slots,
                latest_message=latest_message,
                events=[],
                paused=False,
                followup_action=None,
                active_loop=None,
                latest_action_name=None
            )

            dispatcher = CollectingDispatcher()
            domain = {}

            # Instanziazione della custom action
            action = action_class()

            # Esecuzione
            action.run(dispatcher, tracker, domain)

            # Salva risultato
            results.append({
                "intent": intent,
                "iteration": i + 1,
                "response": dispatcher.messages
            })

    # Output finale su console
    print("\n RISULTATI TOTALI:")
    for r in results:
        print(f"\nIntent: {r['intent']} | Iterazione: {r['iteration']}")
        print("Risposta:", r["response"])