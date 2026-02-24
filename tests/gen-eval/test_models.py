import csv, json, os, requests, time, torch
import pandas as pd
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
#from ollama import Client as OllamaClient
from transformers import AutoTokenizer, AutoModelForCausalLM
from typing import Optional


####################################
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
    "ask_optimization": BASE_ENERGY_PROMPT + "- Fornisci raccomandazioni miranti a massimizzare l'autoconsumo e l'utilizzo di energia condivisa nella comunità energetica.\n- Mantieni la risposta sotto i 150 token.",
    "ask_netload_forecast": BASE_ENERGY_PROMPT + " - Mantieni la risposta sotto i 150 token.",
    "check_consumption": BASE_ENERGY_PROMPT + " - Mantieni la risposta sotto i 150 token.",
    "check_production": BASE_ENERGY_PROMPT + " - Mantieni la risposta sotto i 150 token."
}


MODEL_CATALOG = [
    #"gemma3:4b-it-qat",
    #"jobautomation/OpenEuroLLM-Italian",
    #"wizardlm2:8x22b-q2_K",
    #"gemma3:27b-it-q4_K_M",
    #"llama3:70b-instruct-q4_0",
    #"ollama:mixtral:8x22b"
    #"swap-uniba/LLaMAntino-3-ANITA-8B-Inst-DPO-ITA",
    "google/gemma-3-4b-it",
    #"mistralai/Mixtral-8x22B-Instruct-v0.1",
    #"meta-llama/Llama-3.3-70B-Instruct"
    #"google/gemma-3-27b-it"
]

LOG_FILE = "generated_hf.csv" 
TEST_FILE = "LLM_test_set.csv"  # <-- csv con tutti gli intent

# === Classe LLM di base ===
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
# wrapper huggingface
# ------------------------------
class HFLLM(BaseLLM):
    def __init__(self, model_name:str, torch_dtype=torch.bfloat16, max_new_tokens: int = 256, temperature: float = 0.0):
        self.model_name = model_name
        print(self.model_name)
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.model = AutoModelForCausalLM.from_pretrained(model_name, dtype=torch_dtype, device_map="auto")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
        self.model.config.pad_token_id = self.tokenizer.pad_token_id
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if self.device == "cpu":
                os.environ["TOKENIZERS_PARALLELISM"] = "false"

        self.model.eval()


    def inference(self, messages: list, intent: str) -> str:
        try:
            inputs = self.tokenizer.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_tensors="pt",
                return_dict=True
            )
    
            if isinstance(inputs, torch.Tensor):
                input_ids = inputs.to(self.model.device)
                attention_mask = None
            else:
                input_ids = inputs["input_ids"].to(self.model.device)
                attention_mask = inputs.get("attention_mask", None)
                if attention_mask is not None:
                    attention_mask = attention_mask.to(self.model.device)
    
            with torch.inference_mode():
                outputs = self.model.generate(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    max_new_tokens=self.max_new_tokens,
                    #temperature=self.temperature,
                    do_sample=False,
                    #eos_token_id=eos_token_id,
                )
    
            generated = outputs[0][input_ids.shape[-1]:]
            decoded = self.tokenizer.decode(generated, skip_special_tokens=True).strip()
            print(decoded)
            
            return decoded
    
        except Exception as e:
            print(f"Errore in inferenza: {e}")
            return "ERRORE"

            
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
            start = time.time()
            payload = {
                      "model": self.model_name,
                      "messages": messages,
                      "options": {"temperature": 0.0},
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
# Classe router
# ------------------------------
class LLM:
    def __init__(self, name):
        self.name = name
        self.hf_model = HFLLM(name)
        #self.ollama_model = OllamaLLM(name)

        # aggiungo memoria semplice di contesto
        self.context = [] 
        self.MAX_TURNS = 2 #nb: 1 turno è dato da coppia interazioni user-assistant, ne prendo max 2 per ora


    def add_to_context(self, role:str, content:str) -> None:
        self.context.append({"role": role, "content": content})

        if len(self.context) > self.MAX_TURNS*2: # faccio *2 perché la riga sopra prende solo una interazione, non il turno completo
            self.context = self.context[-self.MAX_TURNS*2:] # tengo in modalità FIFO
            

    def create_prompt(self, intent:str , utterance: str, energy_data:str, training_examples: Optional[list]=None) -> list:
        #model = self.ollama_model#self._select_model(intent)
        model = self.hf_model#self._select_model(intent)
        # prompt principale
        base_user_prompt = model.create_prompt(intent, utterance, energy_data)
        
        messages = []
        system_prompt = SYSTEM_PROMPTS.get(intent, BASE_ENERGY_PROMPT)
        messages.append({"role": "system", "content": system_prompt})
        
        # aggiunta esempi di training:
        if training_examples is not None:
            for ex in training_examples:
                messages.append({"role": "user", "content": ex["user"]})
                messages.append({"role": "assistant", "content": ex["assistant"]})

        # aggiunta memoria conversazione
        #for msg in self.context:
       #     messages.append(msg)

        # aggiunta nuova richiesta
        messages.append({"role": "user", "content": base_user_prompt})

        # salva richiesta in memoria
        #self.add_to_context("user", utterance)

        # restituisce la lista di turni (1s+memo conversazione)
        return messages  

        
    def inference(self, prompt_messages:list, intent:str) -> str:
        model = self.hf_model #self._select_model(intent)
        response = model.inference(prompt_messages, intent)
        #self.add_to_context("assistant", response)

        return response
        
    """
    def _select_model(self):
        if "ollama" in self.name:
            return self.ollama_model
        return self.hf_model
    """

# ================== save log ==========================
def save_log(model_name, intent, prompt, energy_data, utterance, n, result, gen_time, gold):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, 'a', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "modello","intent", "prompt","riepilogo_dati","richiesta_utente","shot", "risposta", "tempo_esecuzione","gold"])
        writer.writerow([datetime.now().isoformat(), model_name, intent,prompt, energy_data, utterance, n, result, gen_time, gold])


# === MAIN ===
def main():
    print("Caricamento dati test set...")
    df_test = pd.read_csv(TEST_FILE, sep=";")

    #"""
    for model_name in MODEL_CATALOG:
        print(f"🤖 Modello: {model_name}")
        try:
            model = LLM(model_name)
            for idx, row in df_test.iterrows():
                energy_data = row["energy_data"]
                intent = row["intent"]
                utterance = row["utterance"]
                gold=row["gold"]

                if intent != "ask_optimization":
                    print(f"🗣️ Intent: {intent} -- Test with utterance: {utterance}")
    
                    ex_shots = df_test[(df_test["intent"]==intent) & (df_test["utterance"] != utterance)]
                    shot_range = [0,1,3,5]
                    for n in shot_range:
                        print(f"📚 Prompt Setting: {n}-shot...")
                        if n==0:
                            prompt = model.create_prompt(intent, utterance, energy_data)
                        else:                    
                            shots = ex_shots.sample(n)
                            training_examples = []
                            for _, ex in shots.iterrows():
                                example_user_prompt = model.hf_model.create_prompt(
                                    ex["intent"], 
                                    ex["utterance"], 
                                    ex["energy_data"]
                                )
                            
                                training_examples.append({
                                    "user": example_user_prompt,
                                    "assistant": ex["gold"]
                                })
    
                            prompt = model.create_prompt(intent, utterance, energy_data, training_examples)
                                                           
                        start = time.time()
                        result = model.inference(prompt,intent)
                        gen_time = round(time.time() - start, 2)
                        save_log(model_name, intent, prompt, energy_data, utterance, n, result, gen_time, gold)
                        print(f"✅ Risposta ricevuta in {gen_time}\n") 
        except Exception as e:
            print(f"❌ Errore con {model_name}: {e}\n")
    #"""


if __name__ == "__main__":
    main()
