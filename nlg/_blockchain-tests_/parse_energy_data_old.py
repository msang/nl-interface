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

    #itero sulle singole date
    for _, row in df.iterrows():
        date = row["Date"]
        prosumer_user = row['Prosumer_user']
        members = []

        peers = {"Peer1":"prosumer", "Peer2":"prosumer", "Peer3":"prosumer", "Peer4":"consumer", "Peer5":"consumer" }
        #itero sui peer
        for peer, role in peers.items():
            production = parse_float(row.get(peer + "_production"))
            consumption = parse_float(row.get(peer + "_consumption"))
            is_user = peer == prosumer_user         

            member = {
                "name": peer,
                "is_user": is_user,
                "role": role,
                "consumption": consumption 
            }
            
            if role == "prosumer":
                member["production"] = production
            else:
                member["production"] = 0.0

            members.append(member)

        scenarios[date] = members

    return scenarios
   

if __name__ == "__main__":
    scenarios = parse_energy_data("test2_scenarios.csv")
    print(scenarios)
