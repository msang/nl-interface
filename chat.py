import os, requests, signal, subprocess, sys, threading, time
sys.path.insert(0, os.path.abspath("."))
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

RASA_COMMAND = ["rasa", "run", "--enable-api", "--cors", "*", "--endpoints", "endpoints.yml"]
ACTIONS_COMMAND = ["rasa", "run", "actions"]
NLG_COMMAND = ["uvicorn", "nlg.nlg_server:app", "--host", "0.0.0.0", "--port", "5056", "--reload", "--log-level", "debug"]

RASA_URL = "http://localhost:5005/status"
ACTIONS_URL = "http://localhost:5055/health"
NLG_URL = "http://localhost:5056/health"  # endpoint aggiunto appositamente per questo check

#aggiungo prima come variabile globale
actions_server = None 

# funzione di sanity check dei server
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

# funzione del "watchdog", che verifica se ci sono state modifiche recenti alla cartella /actions
def watch_actions_folder(folder_path="actions", interval=1.5):
    global actions_server
    def get_py_files_mtime():
        mtimes = {}
        for root, _, files in os.walk(folder_path):
            for f in files:
                if f.endswith(".py"): #---> per ora controllo solo gli script
                    full_path = os.path.join(root, f)
                    try:
                        mtimes[full_path] = os.path.getmtime(full_path) # registra il timestamp dell'ultima modifica del file
                    except FileNotFoundError:
                        pass
        return mtimes

    previous_mtimes = get_py_files_mtime() #ultimi timestamp di tutti i file

    while True:
        time.sleep(interval)
        current_mtimes = get_py_files_mtime()
        if current_mtimes != previous_mtimes:
            print("Modifica rilevata, riavvio del server delle azioni...")
            if actions_server and actions_server.poll() is None:
                actions_server.terminate()
                try:
                    actions_server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    actions_server.kill()
            # e poi riavvio con subprocess
            actions_server = subprocess.Popen(
                ACTIONS_COMMAND,
                stderr=subprocess.STDOUT,
                stdout=open(os.path.join(log_dir, "actions.log"), "w")
            )
            previous_mtimes = current_mtimes

###########################################################################################

print("Avvio dei server...")

rasa_server = subprocess.Popen(RASA_COMMAND, stderr=subprocess.STDOUT, stdout=open(os.path.join(log_dir, "rasa.log"), "w") )#stdout=subprocess.PIPE,)
actions_server = subprocess.Popen(ACTIONS_COMMAND, stderr=subprocess.STDOUT, stdout=open(os.path.join(log_dir, "actions.log"), "w") )
nlg_server = subprocess.Popen(NLG_COMMAND, stderr=subprocess.STDOUT, universal_newlines=True, stdout=open(os.path.join(log_dir, "nlg.log"), "w") )

## avvio del controllo su cartella delle azioni
watcher_thread = threading.Thread(target=watch_actions_folder, daemon=True) #crea un nuovo thread che fa il controllo separatamente rispetto allo script - il thread però si interrompe quando lo script viene interrotto
watcher_thread.start()

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
                proc.wait(timeout=5)  #aspetto 5sec. per la chiusura del server, altrimenti forzo con kill()
            except subprocess.TimeoutExpired:
                proc.kill()
    sys.exit(1)


###########################################################################################
# Loop di input, per l'interazione da terminale
try:
    while True:
        msg = input("Input: ")
        if not msg.strip():
            break
        try:
            res = requests.post(
                "http://localhost:5005/webhooks/rest/webhook",
                json={"sender": "utente_ubuntu", "message": msg}
            )
            for r in res.json():
                print("Risposta:", r.get("text", "[nessuna risposta]"))
        except requests.exceptions.ConnectionError:
            print("Errore: il server Rasa non risponde.")
            break
except KeyboardInterrupt:
    print("\n Interruzione manuale.")
finally:
    print("Terminazione dei processi...")
    for proc in [rasa_server, actions_server, nlg_server]:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    print("Tutti i server sono stati chiusi.")

