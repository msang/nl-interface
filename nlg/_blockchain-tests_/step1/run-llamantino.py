import argparse, csv, os, time, torch
from datetime import datetime
from jinja2 import Template, Environment, FileSystemLoader
import pandas as pd
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from typing import Text

LOG_FILE = "results.csv"

# === LOGGING ===
def save_log(model, prompt, response, gen_time):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, 'a', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "modello", "prompt", "risposta", "tempi esecuzione"])
        writer.writerow([datetime.now().isoformat(), model, prompt, response, gen_time])



class LLM:
        def __init__(self, model_id="swap-uniba/LLaMAntino-3-ANITA-8B-Inst-DPO-ITA") -> None:
            self.model = AutoModelForCausalLM.from_pretrained(model_id, device_map="auto", torch_dtype='auto')
            self.tokenizer = AutoTokenizer.from_pretrained(model_id, padding_side="left")
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.model.generation_config.pad_token_id = self.tokenizer.eos_token_id
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.model_name = model_id.split("/")[1]
            if self.device == "cpu":
                os.environ["TOKENIZERS_PARALLELISM"] = "false"
    
        def __repr__(self):
            return f"MODEL FULL NAME: {self.model_name}"


        def create_prompt(self, template):
            system="Sei un assistente esperto in comunità energetiche e gestione peer-to-peer dell’energia su blockchain. Rispondi con linguaggio tecnico ma comprensibile, senza ridondanze, e mantieni la risposta sotto i 250 token."
            complete = [{"role": "system", "content":f"{system}"},{"role": "user", "content":f"{template}"}]
            formatted = self.tokenizer.apply_chat_template(complete, tokenize=False, add_generation_prompt=True)

            return formatted


        def inference(self, prompt):
            pipe = pipeline(model=self.model,
                            tokenizer=self.tokenizer,
                            return_full_text=False,  
                            task='text-generation',
                            num_return_sequences=1,
                            temperature=0.1,
                            device_map="auto",
                            torch_dtype='auto',
                            max_new_tokens=250
                            )
            result = pipe(prompt)[0]["generated_text"]

            return result             
    

if __name__ == "__main__":
    llm = LLM()
    data_ex = """
Stai supportando un prosumer appartenente a una comunità energetica composta da membri che possono essere o prosumer (con produzione e consumo giornalieri di energia) o consumer (solo consumo, nessuna produzione).

La comunità scambia energia utilizzando una blockchain:
- Ogni kWh è rappresentato da un NFT ERC721.
- Ogni centesimo di euro è rappresentato da 1 token ERC20.
- I membri scelgono liberamente a che prezzo vendere l’energia in surplus, con un vincolo:
  - Il prezzo deve essere maggiore di 0,04 € (prezzo di vendita alla rete)
  - E minore di 0,16 € (prezzo di acquisto dalla rete)

Applica le seguenti regole per stabilire a chi può essere venduto il surplus:

1. Ordine di priorità: 
   - Prima i prosumer in deficit (cioè coloro che hanno consumato più di quanto prodotto).
   - Solo il surplus residuo può essere venduto ai consumer.
2. Ogni transazione è espressa in NFT (1 kWh) + corrispondente quantità di token (in cent).
3. L’obiettivo è vendere quanto più possibile del proprio surplus, ottimizzando il prezzo.

Di seguito trovi i dati giornalieri dei membri della comunità (in kWh):


- Peer1 (utente): produzione = 20.73, consumo = 10.03

- Peer2: produzione = 20.04, consumo = 11.04

- Peer3: produzione = 9.63, consumo = 3.28

- Peer4: consumo = 0.45

- Peer5: consumo = 5.59


Sulla base dei dati sopra, fornisci un suggerimento **per il prosumer utente (che in questo caso è Peer1)** indicando:
1. A chi può vendere il surplus, in quale ordine e in che misura.
2. A quale prezzo (in centesimi di euro) vendere ciascun blocco di kWh, tenendo conto delle regole.

Riassumi il suggerimento in modo chiaro ed efficace (es. tabella o elenco).
"""
    prompt = llm.create_prompt(data_ex)
    print(prompt)
    start = time.time()
    response = llm.inference(prompt)
    print(response)
    tot = time.time() - start
    save_log(llm.model_name, prompt, response, tot)
    

    