import csv, os, time, torch
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from parse_energy_data import parse_energy_data
from ollama import Client as OllamaClient
from transformers import AutoTokenizer, AutoModelForCausalLM


# === CONFIG ===
MODEL_CATALOG = ["gemma3:4b-it-qat","jobautomation/OpenEuroLLM-Italian"]
LOG_FILE = "results_step2.csv"
TEMPLATE_PATH = "../templates/template_p2p-interact.j2"
SCENARIOS = "test2_scenarios.csv"
SYSTEM_PROMPT = "Sei un assistente esperto in comunità energetiche e gestione peer-to-peer dell’energia su blockchain. Rispondi con linguaggio tecnico ma comprensibile, senza ridondanze.  Mantieni la risposta sotto i 250 token."

# === PROMPT CREATION ===
def create_prompt(members, user, utterance):
    env = Environment(loader=FileSystemLoader('../templates'))
    template = env.get_template("template_p2p-interact.j2")
    return template.render(members=members, prosumer_user=user, utterance=utterance)

# === LOGGING ===
def save_log(model, prompt, response, gen_time):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, 'a', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter=";")
        if not file_exists:
            writer.writerow(["timestamp", "modello", "prompt", "risposta", "tempi esecuzione"])
        writer.writerow([datetime.now().isoformat(), model, prompt, response, gen_time])

# === MODEL RUN ===
def run_with_ollama(model, prompt):
    client = OllamaClient()
    response = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        options={"temperature": 0.0}
    )

    return response["message"]["content"]


# === MAIN ===
def main():
    print("\n Caricamento scenari...")
    scenarios, users = parse_energy_data(SCENARIOS)
    utterance = "suggeriscimi a chi vendere e a quanto"
    for (date, members), user in zip(scenarios.items(), users):    
        prompt = create_prompt(members, user, utterance)
        #print(f"\n Prompt generato: {prompt}")
        #"""
        for model in MODEL_CATALOG:
            print(f"\n🔁 Test su {model}")
            start = time.time()
            try:
                result = run_with_ollama(model, prompt)
                print(result)
                tot = time.time() - start
                save_log(model, prompt, result, tot)
            except Exception as e:
                print(f"❌ Errore in {model}: {e}")
                save_log(model, prompt, f"[ERRORE] {e}", tot)
         #"""


if __name__ == "__main__":
    main()
