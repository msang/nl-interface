import csv, os, time, torch
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from parse_energy_data import parse_energy_excel
from ollama import Client as OllamaClient
from transformers import AutoTokenizer, AutoModelForCausalLM


# === CONFIG ===
MODEL_CATALOG = ["mistral:7b", "gemma3:4b-it-qat","jobautomation/OpenEuroLLM-Italian","mii-llm/maestrale-v0.4beta.q4_k_m","VitoF/llama-3.1-8b-italian"]
#"hf": [
 #       "swap-uniba/LLaMAntino-3-ANITA-8B-Inst-DPO-ITA",
  #      "giux78/zefiro-7b-beta-ITA-v0.1"
   # ]
#"deepseek-r1:7b",
#"DeepMount00/Mistral-RAG",
#"mii-llm/maestrale-chat-v0.4-beta",
LOG_FILE = "results.csv"
TEMPLATE_PATH = "../templates/template_p2p.j2"
ENERGY_EXCEL = "energy_details.xlsx"
SYSTEM_PROMPT = "Sei un assistente esperto in comunità energetiche e gestione peer-to-peer dell’energia su blockchain. Rispondi con linguaggio tecnico ma comprensibile, senza ridondanze, e mantieni la risposta sotto i 250 token."

# === PROMPT CREATION ===
def create_prompt(members, user):
    env = Environment(loader=FileSystemLoader('../templates'))
    template = env.get_template("template_p2p-interact.j2")
    return template.render(members=members, prosumer_user=user)

# === LOGGING ===
def save_log(model, prompt, response, gen_time):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, 'a', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "modello", "prompt", "risposta", "tempi esecuzione"])
        writer.writerow([datetime.now().isoformat(), model, prompt, response, gen_time])

# === MODEL RUN ===
def run_with_ollama(model, prompt):
    client = OllamaClient()
    response = client.generate(
        model=model,
        prompt = SYSTEM_PROMPT + "\n" + prompt,
         options={"num_predict": 250, "temperature":0}        
    )

    return response["response"]
    """
    response = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    )
    return response['message']['content']
    """    

# === MAIN ===
def main():
    print("\n Caricamento dati energetici da Excel...")
    members, user = parse_energy_excel(ENERGY_EXCEL)
    utterance = "suggeriscimi a chi vendere e a quanto"
    prompt = create_prompt(members, user, utterance)
    print(f"\n Prompt generato: {prompt}")

    for model in MODEL_CATALOG:
        print(f"\n🔁 Test su {model}")
        start = time.time()
        try:
            result = run_with_ollama(model, prompt)
            print(result)
            tot = time.time() - start
            save_log(model, prompt, result, tot)
        except Exception as e:
            print(f"❌ Errore Ollama {model}: {e}")
            save_log(model, prompt, f"[ERRORE] {e}", tot)


if __name__ == "__main__":
    main()
