import os, requests, torch
from typing import Optional, Text
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from jinja2 import Environment, FileSystemLoader


# ==== SYS. PROMPT =====
BASE_ENERGY_PROMPT = (
    "Sei un assistente esperto in comunità energetiche, ottimizzazione dell’energia e analisi dei consumi. "
    "Rispondi in modo tecnico ma comprensibile, senza ridondanze, né spiegazioni non richieste."
    "L'utente a cui devi rispondere è membro di una comunità energetica dotato di impianto fotovoltaico e batteria di accumulo."
    "REGOLE GENERALI PER LE RISPOSTE:\n"
    "- Usa SEMPRE i dati forniti dall’utente, senza inventare.\n"
    "- Mantieni uno stile diretto e professionale.\n"
    "- Non ripetere i dati: interpretali e produci raccomandazioni utili."
)

SYSTEM_PROMPTS = {
    "ask_optimization": BASE_ENERGY_PROMPT + " - Mantieni la risposta sotto i 150 token.",
    "ask_selling_advice": (
        "Sei un assistente esperto in comunità energetiche e gestione peer-to-peer "
        "dell’energia su blockchain. Rispondi con linguaggio tecnico ma comprensibile, "
        "senza ridondanze. Mantieni la risposta sotto i 200 token."
    ),
    "ask_netload_forecast": BASE_ENERGY_PROMPT + " - Mantieni la risposta sotto i 150 token.",
    "check_consumption": BASE_ENERGY_PROMPT + " - Mantieni la risposta sotto i 150 token.",
    "check_production": BASE_ENERGY_PROMPT + " - Mantieni la risposta sotto i 150 token."
}

ONE_SHOT_EX = {
    "check_consumption": [
        {
            "user": 
            """DATI:" 
            - energia utilizzata dalla casa in tutta la giornata: 11.23 kWh
            - energia acquistata dalla rete in tutta la giornata: 3.89 kWh
            - potenza istantanea fornita dall'impianto solare: 0.67 kW
            - potenza istantanea fornita dalla batteria: 0.43 kW
            - potenza istantanea fornita dalla rete: 0.05 kW
            - potenza totale utilizzata: 1.15 kW
            
            RICHIESTA:
            ho l'asciugatrice in funzione, quanto sto consumando""",
            "assistant": "Non ho a disposizione i dati esatti sui consumi dell'asciugatrice, ma al momento stai prendendo complessivamente 1,15 kW dalla rete."
        }
    ],
    "check_production": [
        {
            "user": 
            """DATI:
            - energia totale prodotta dai pannelli in tutta la giornata: 9.27 kWh
            - auto-consumo della giornata: 7.17kWh
            - energia immessa in rete in tutta la giornata: 2.11kWh
            - potenza prodotta ora dall'impianto fotovoltaico: 0.57kW
            - stato di carica attuale della batteria: 98%
            - status della batteria: in scarica
            - potenza immessa dal fotovolatico alla batteria: 0.00 kW
            - potenza immessa dal fotovoltaico alla rete: 0.00
    
            RICHIESTA: 
            a quanto sono di batteria""",
            "assistant":
            "Al momento la tua batteria è al 98% ed è in scarica, quindi la stai usando per coprire il tuo fabbiosogno energetico corrente."
        }    
    ],
    "ask_optimization": [
        {
            "user": 
            """DATI:
            Riepilogo ottimizzazione:
            - Consumo maggiore: - (0.00 kWh)
            - Surplus maggiore: 08:00–10:00 (5.12 kWh)
            - Stato di carica massimo della batteria:  06:00–08:00 (100.00%)
            - Valori massimi di energia condivisa: - (0.00 kWh)
    
            RICHIESTA:
            non sto producendo tanto, però mi serve il riscaldamento""",
            "assistant": "Tra le 8 e le 10 è previsto il maggiore surplus di energia. Puoi riscaldare la casa in quelle ore e tenere invece il  riscaldamento spento quando non potrai più sfruttare l'autoconsumo."
        }
    ],
    "ask_netload_forecast": [
        {
            "user": 
            """DATI:           
                                           Previsione consumi (kWh)
            Ora                                                
            2025-11-25 16:00:00+01:00                      0.10
            2025-11-25 17:00:00+01:00                      0.68
            2025-11-25 18:00:00+01:00                      1.01
            2025-11-25 19:00:00+01:00                      0.98
            2025-11-25 20:00:00+01:00                      1.05
            2025-11-25 21:00:00+01:00                      1.03
            2025-11-25 22:00:00+01:00                      1.03
            2025-11-25 23:00:00+01:00                      1.06
            2025-11-26 00:00:00+01:00                      0.46
    
            RICHIESTA:
            anche oggi nuvole: quanto sarà il mio consumo, considerato che non posso contare su pannelli o batteria?""",
            "assistant": "Consumerai principalmente nella fascia oraria delle 18 (circa un kWh), e poi nuovamente nelle ore serali, tra le 20 e le 23 (complessivamente 3,12 kWh)."
        }
    ]
}


# ------------------------------
# wrapper generico - classe di base da cui ereditano le altre
# ------------------------------
class BaseLLM:
    
    def create_prompt(self, intent: str, utterance: str, energy_data: str) -> str:
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("template.j2")
    
        # contenuto dell'utente generato da jinja
        user_content = template.render(
            intent=intent,
            utterance=utterance,
            data=energy_data
        )
    
        return user_content

    def inference(self, prompt: str, intent:str) -> str:
        raise NotImplementedError


# ------------------------------
# wrapper hf (impostato su llamantino-anita -- TODO: generalizzarlo meglio)
# ------------------------------
class HFLLM(BaseLLM):
    def __init__(self, model_id: str):
        self.model_name = model_id
        self.model = AutoModelForCausalLM.from_pretrained(model_id, device_map="auto")
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, padding_side="left")
        self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model.generation_config.pad_token_id = self.tokenizer.eos_token_id
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if self.device == "cpu":
                os.environ["TOKENIZERS_PARALLELISM"] = "false"

    
    def inference(self, messages:list, intent:str) -> str:
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
    
        generator = pipeline(
            model=self.model,
            tokenizer=self.tokenizer,
            task="text-generation",
            do_sample=True,
            top_k=40,
            top_p=0.9,
            temperature=0.6,
            max_new_tokens=150,
        )
    
        full_text = generator(prompt)[0]["generated_text"]

        split_token = "|assistant|"

        if split_token in full_text:
            out = full_text.split(split_token)[-1]
        else:
            # fallback generale se cambia il template
            out = full_text[len(prompt):].strip()
        
        return out


# ------------------------------
# wrapper ollama
# ------------------------------
class OllamaLLM(BaseLLM):
    def __init__(self, model_name: str, host:str ='http://localhost:11434'):
        #self.client = OllamaClient()
        self.model_name = model_name
        self.host = host
        print(self.model_name)


    def inference(self, messages:list, intent:str) -> str:

        try:
            payload = {
                      "model": self.model_name,
                      "messages": messages,
                      "options": {"temperature": 0.6},
                      "stream":False
                    }  
            
            response = requests.post( f"{self.host}/api/chat",json=payload, timeout=120)
            print(response, flush=True)
            #response.raise_for_status()
            response_data = response.json()
            print(response_data, flush=True)
            
        except (requests.exceptions.Timeout, 
            requests.exceptions.HTTPError, 
            requests.exceptions.RequestException, 
            ValueError) as e:
                 return "Mi dispiace. Si è verificato un errore nella generazione della risposta. Riprova più tardi."
        
        return response_data['message']['content']


# ------------------------------
# Classe richiamata dal server - fa il routing del modello in base all'intent
# ------------------------------
class LLM:
    def __init__(self):
        self.hf_model = HFLLM("swap-uniba/LLaMAntino-3-ANITA-8B-Inst-DPO-ITA")
        self.ollama_model = OllamaLLM("gemma3:4b-it-qat") 
        #self.ollama_model = OllamaLLM("mixtral:8x22b")

        # aggiungo memoria semplice di contesto
        self.context = [] 
        self.MAX_TURNS = 2 #nb: 1 turno è dato da coppia interazioni user-assistant, ne prendo max 2 per ora


    def add_to_context(self, role:str, content:str) -> None:
        self.context.append({"role": role, "content": content})

        if len(self.context) > self.MAX_TURNS*2: # faccio *2 perché la riga sopra prende solo una interazione, non il turno completo
            self.context = self.context[-self.MAX_TURNS*2:] # tengo in modalità FIFO
            

    def create_prompt(self, intent:str , utterance: str, energy_data:str) -> list:
        model = self._select_model(intent)
        # prompt principale
        base_user_prompt = model.create_prompt(intent, utterance, energy_data)
        
        messages = []
        system_prompt = SYSTEM_PROMPTS.get(intent, BASE_ENERGY_PROMPT)
        messages.append({"role": "system", "content": system_prompt})
        
        # aggiunta degli esempi di training:
        example = ONE_SHOT_EX.get(intent, [])
        for ex in example:
            messages.append({"role": "user", "content": ex["user"]})
            messages.append({"role": "assistant", "content": ex["assistant"]})

        # aggiunta memoria conversazione
        for msg in self.context:
            messages.append(msg)

        # aggiunta nuova richiesta
        messages.append({"role": "user", "content": base_user_prompt})

        # salva richiesta in memoria
        self.add_to_context("user", utterance)

        # restituisce la lista di turni (1s+memo conversazione)
        return messages  

        
    def inference(self, prompt_messages:list, intent:str) -> str:
        model = self._select_model(intent)
        response = model.inference(prompt_messages, intent)
        self.add_to_context("assistant", response)

        return response
        

    def _select_model(self, intent: Optional[str]):
        # "forzo" per ora all'uso del solo modello ollama
        ollama_intents = ("ask_netload_forecast", "ask_optimization", "check_consumption", "check_production") 
        if intent in ollama_intents:
            return self.ollama_model
        return self.hf_model


#-------------------------       
if __name__ == "__main__":
    model = LLM()
    intent = "ask_netload_forecast"
    utterance = "anche oggi nuvole: quanto sarà ilmio consumo, considerato che non posso contare su pannelli o batteria?"
    energy_data = """
                                   Previsione consumi (kWh)
    Ora                                                
    2025-11-25 16:00:00+01:00                      0.10
    2025-11-25 17:00:00+01:00                      0.68
    2025-11-25 18:00:00+01:00                      1.01
    2025-11-25 19:00:00+01:00                      0.98
    2025-11-25 20:00:00+01:00                      1.05
    2025-11-25 21:00:00+01:00                      1.03
    2025-11-25 22:00:00+01:00                      1.03
    2025-11-25 23:00:00+01:00                      1.06
    2025-11-26 00:00:00+01:00                      0.46
    """
    prompt = model.create_prompt(intent, utterance, energy_data)
    print(model.inference(prompt,intent))
