import json, psycopg2, pprint
import pandas as pd
from collections import defaultdict as ddict
from psycopg2 import Error
import datetime



def save_chat_hist(cursor): 
    cursor.execute("SELECT data, sender_id, action_name FROM events;")
    record = cursor.fetchall()
    relevant_info = ddict(list)
    for rec in record:
        relevant_info["chat_id"].append(rec[1])
        event = json.loads(rec[0])
        relevant_info["event"].append(event["event"])
        relevant_info["action_name"].append(rec[2])
        ts = datetime.datetime.fromtimestamp(event["timestamp"]).isoformat()
        relevant_info["timestamp"].append(ts)
        if event["event"] in ("bot", "user"):
            relevant_info["text"].append(event["text"])
        else:
            relevant_info["text"].append("")
        if "parse_data" in event.keys(): ## dati utente sono in event["parse_data"]["intent"]["name"] e event["parse_data"]["entities"] --> quest'ultima è una lista, bisogna iterare per leggere tutte le entità
            relevant_info["input_channel"].append(event["input_channel"])
            relevant_info["intent"].append(event["parse_data"]["intent"]["name"])
            relevant_info["entity_types"].append([e["entity"] for e in event["parse_data"]["entities"]])
            relevant_info["entity_values"].append([e["value"] for e in event["parse_data"]["entities"]])
        else:
            relevant_info["intent"].append("")
            relevant_info["entity_types"].append("")
            relevant_info["entity_values"].append("")
            relevant_info["input_channel"].append("")

    df = pd.DataFrame(relevant_info)
    df.to_csv("rasa_chat_hist.csv",sep="\t", encoding="utf-8")


    try:
        # Connect to an existing database
        connection = psycopg2.connect(user="...", #postgres username
                                    password="...", #
                                    host="...",
                                    port="...",
                                    database="...")

        cursor = connection.cursor()
        save_chat_hist(cursor)


    except (Exception, Error) as error:
        print("Error while connecting to PostgreSQL", error)
    finally:
        if (connection):
            cursor.close()
            connection.close()
            #print("PostgreSQL connection is closed")