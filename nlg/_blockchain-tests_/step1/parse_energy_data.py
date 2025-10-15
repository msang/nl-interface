import pandas as pd

def parse_energy_excel(file_path):

    xl = pd.ExcelFile(file_path)
    members = []

    for idx, sheet_name in enumerate(xl.sheet_names):
        df = xl.parse(sheet_name)

        # normalizzazione header
        df.columns = [str(c).strip() for c in df.columns]
        first_row = df.iloc[20] #riga scelta pseudo-casualmente: 2024-01-21 00:00:00+01:00	Consumi: 10,033	- Produzione: 20,735

        role = "prosumer" if idx < 3 else "consumer"
        member = {
            "name": sheet_name,
            "is_user": (idx == 0),  # primo prosumer è l'utente
            "role": role,
        }
        if role == "prosumer":
            member["production"] = round(float(str(first_row["Production"]).replace(",", ".")), 2)
            member["consumption"] = round(float(str(first_row["Consumption"]).replace(",", ".")), 2)
        else:
            member["production"] = 0.0
            member["consumption"] = round(float(str(first_row["Consumption"]).replace(",", ".")), 2)
        members.append(member)
    #print(members)
    prosumer_user = next((m["name"] for m in members if m["is_user"] and m["role"] == "prosumer"), None)

    return members, prosumer_user


if __name__ == "__main__":
    parse_energy_excel("energy_details.xlsx")
