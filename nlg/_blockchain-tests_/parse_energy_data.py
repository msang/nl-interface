import pandas as pd
import csv, json

def parse_float(value):
    try:
        return round(float(str(value).replace(",", ".")), 2)
    except (ValueError, TypeError):
        return 0.0

def parse_energy_data(file_path):
    df = pd.read_csv(file_path, sep=";")
    scenarios = {}
    users = []

    for _, row in df.iterrows():
        date = row["Date"]
        prosumer_user = row['Prosumer_user']
        users.append(prosumer_user)
        members = []
        
        peers = {
            "Peer1": "prosumer", 
            "Peer2": "prosumer", 
            "Peer3": "prosumer", 
            "Peer4": "consumer", 
            "Peer5": "consumer"
        }

        for peer, role in peers.items():
            production = parse_float(row.get(peer + "_production"))
            consumption = parse_float(row.get(peer + "_consumption"))
            is_user = peer == prosumer_user         

            member = {
                "name": peer,
                "is_user": is_user,
                "role": role,
                "production": production if role == "prosumer" else 0.0,
                "consumption": consumption
            }

            members.append(member)
       
        scenarios[date] = members

    return scenarios, users

if __name__ == "__main__":
    scenarios, users = parse_energy_data("test2_scenarios.csv")
    for date, members in scenarios.items():
        print(members)
    #print(json.dumps(scenarios, indent=4, ensure_ascii=False))
