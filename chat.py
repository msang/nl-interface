"""
import requests

while True:
    msg = input("Input: ")
    if not msg.strip():
        break
    res = requests.post(
        "http://localhost:5005/webhooks/rest/webhook",
        json={"sender": "utente_shell", "message": msg}
    )
    for r in res.json():
        print("Risposta:", r.get("text", "[nessuna risposta]"))
"""
import os, requests, signal, subprocess, sys, time
sys.path.insert(0, os.path.abspath("."))
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

RASA_COMMAND = ["rasa", "run", "--enable-api", "--cors", "*", "--endpoints", "endpoints.yml"]
ACTIONS_COMMAND = ["rasa", "run", "actions"]
NLG_COMMAND = ["uvicorn", "nlg.nlg_server:app", "--host", "0.0.0.0", "--port", "5056", "--reload", "--log-level", "debug"]

RASA_URL = "http://localhost:5005/status"
ACTIONS_URL = "http://localhost:5055/health"
NLG_URL = "http://localhost:5056/health"  # endpoint aggiunto

# controllo se il server è attivo
def check_server(url, name, retries=3, delay=60):
    for attempt in range(retries):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                print(f"{name} server è attivo su {url}")
                return True
        except requests.exceptions.ConnectionError:
            pass
        print(f"[{attempt+1}/{retries}] Attesa per {name} server...")
        time.sleep(delay)
    print(f"{name} server NON ha risposto su {url}")
    return False


print("🟢 Avvio dei server...")

rasa_server = subprocess.Popen(RASA_COMMAND, stderr=subprocess.STDOUT, stdout=open(os.path.join(log_dir, "rasa.log"), "w") )#stdout=subprocess.PIPE,)
actions_server = subprocess.Popen(ACTIONS_COMMAND, stderr=subprocess.STDOUT, stdout=open(os.path.join(log_dir, "actions.log"), "w") )
nlg_server = subprocess.Popen(NLG_COMMAND, stderr=subprocess.STDOUT, universal_newlines=True, stdout=open(os.path.join(log_dir, "nlg.log"), "w") )

#for line in iter(nlg_server.stdout.readline, ''):
#    print("[NLG]", line.strip())
#    if "Application startup complete" in line:
#        break  # server pronto

# Controllo che tutti i server siano attivi
if not all([
    check_server(RASA_URL, "Rasa"),
    check_server(ACTIONS_URL, "Actions"),
    check_server(NLG_URL, "NLG")
]):
    print("Uno o più server non hanno risposto. Terminazione...")
    for proc in [rasa_server, actions_server, nlg_server]:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    sys.exit(1)

# Loop di input
try:
    while True:
        msg = input("Input: ")
        if not msg.strip():
            break
        try:
            res = requests.post(
                "http://localhost:5005/webhooks/rest/webhook",
                json={"sender": "utente_shell", "message": msg}
            )
            for r in res.json():
                print("Risposta:", r.get("text", "[nessuna risposta]"))
        except requests.exceptions.ConnectionError:
            print("Errore: il server Rasa non risponde.")
            break
except KeyboardInterrupt:
    print("\n🛑 Interruzione manuale.")
finally:
    print("⏹️ Terminazione dei processi...")
    for proc in [rasa_server, actions_server, nlg_server]:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    print("✅ Tutti i server sono stati chiusi.")

