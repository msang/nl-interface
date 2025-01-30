import os, requests, subprocess, time, yaml
from dotenv import load_dotenv, find_dotenv
from pathlib import Path



def start_ngrok():

    #ngrok = subprocess.Popen(['ngrok', 'http', '5005']) # <- uncomment this if you're running the script locally, instead of docker
    ngrok = subprocess.Popen(['ngrok', 'http', 'rasa-server:5005']) 
    time.sleep(5)

    return ngrok


def retrieve_url():
    try:
        #response = requests.get("http://127.0.0.1:4040/api/tunnels")
        response = requests.get("http://localhost:4040/api/tunnels")
        tunnels = response.json()['tunnels']
        for tunnel in tunnels:
            if tunnel['proto'] == 'https':
                return tunnel['public_url']
    except Exception as e:
        print(f"Impossibile recuperare l'URL: {e}")
        return None
    

def find_file():
    possible_paths = [
        '/app/credentials.yml',  # path in the Docker container
        os.path.join(os.getcwd(), 'credentials.yml')  # local path
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    raise FileNotFoundError("File 'credentials.yml' not found")


def update_credentials_file(ngrok_url, APIKEY, BOT_NAME):

    credentials_file = find_file()

    with open(credentials_file, 'r') as file:
        credentials_data = yaml.safe_load(file)
   
    # update telegram data 
    credentials_data['telegram'] = {
        'access_token': APIKEY,
        'verify': BOT_NAME,
        'webhook_url': f"{ngrok_url}/webhooks/telegram/webhook"
     }
    """
    if 'telegram' in credentials_data:
        credentials_data['telegram']['access_token'] = APIKEY
        credentials_data['telegram']['verify'] = BOT_NAME
        credentials_data['telegram']['webhook_url'] = f"{ngrok_url}/webhooks/telegram/webhook"
    else:
        credentials_data['telegram'] = {'access_token': APIKEY}
        credentials_data['telegram'] = {'verify': , BOT_NAME}
        credentials_data['telegram'] = {'webhook_url': f"{ngrok_url}/webhooks/telegram/webhook"}
    """

    # overwrite yaml file 
    with open(credentials_file, 'w') as file:
        yaml.safe_dump(credentials_data, file)

    print(f"Il file {credentials_file} è stato aggiornato con l'URL: {ngrok_url}/webhooks/telegram/webhook")


def update_telegram_webhook(ngrok_url, APIKEY):

    telegram_api = f"https://api.telegram.org/bot{APIKEY}/setWebhook"
    webhook_url = f"{ngrok_url}/webhooks/telegram/webhook"
    
    try:
        # POST request to update the webhook
        response = requests.post(telegram_api, params={"url": webhook_url})

        if response.status_code == 200:
            print(f"Webhook aggiornato con successo a: {webhook_url}")
        else:
            print(f"Errore nell'aggiornamento del webhook: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Errore durante la connessione all'API di Telegram: {e}")


def main():
    load_dotenv(find_dotenv())
    APIKEY = os.environ.get("TELEGRAM_TOKEN")
    BOT_NAME = os.environ.get("TELEGRAM_BOT_NAME")

    print("Avvio di ngrok...")
    ngrok_process = start_ngrok()

    print("Recupero dell'URL...")
    ngrok_url = retrieve_url()

    if ngrok_url:
        print(f"Ngrok è attivo su: {ngrok_url}")
        print("Aggiornamento del file credentials.yml...")
        update_credentials_file(ngrok_url, APIKEY, BOT_NAME)
        update_telegram_webhook(ngrok_url, APIKEY)
    else:
        print("Impossibile ottenere l'URL da ngrok.")

    ngrok_process.wait()


if __name__ == "__main__":
    main()
