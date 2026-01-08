import datetime, os, pytz
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


from .data import summarize_data
from .solve_opt_prob import solve_opt_prob
from .forecasting.create_data import run_model
from .forecasting.LSTMRegressor import SolarLSTMModel
from .forecasting.MLPRegressor import SolarMLPModel
from .utils import map_consumption

pd.options.mode.chained_assignment = None
BASE_DIR = os.path.dirname(__file__)


## ====== OPTIMIZER CLASS =======
class Optimizer:
    def __init__(self, n=5, Delta=5, Ups=3, h=96, hh=96, prosumer_no=1, start=datetime.datetime(2020, 6, 20, 1, 0, 0), data_folder = 'data_fix_withprice', forecast_model='MLP'):
        self.n = n                  # Numero di prosumer
        self.Delta = Delta          # Tempo di campionamento [min]
        self.Ups = Ups              # Numero di campioni per finestra di prezzo
        self.h = h                  # Numero finestre nell'orizzonte di ottimizzazione
        self.hh = hh                # Numero finestre nell'orizzonte di simulazione
        self.prosumer = prosumer_no
        self.start = start          # t0 -->NB: il valore di default poi andrà cambiato!!!
        self.data_folder = data_folder
        self.model=forecast_model

    @property
    def data_path(self):
        return os.path.join(BASE_DIR, self.data_folder)

    @property
    def mode(self):
        return 'static' if self.data_folder == 'data_fix_withprice' else 'autoregressive' # modalità di ottimizzazione: static - su dati statici (dataset REC irlandese); autoregressive - su dati predetti dinamicamente da LSTM/MLP


    def __repr__(self):
        return f"""
        Initialized Optimizer object based on solar and consumption data available at '{self.data_path}'.
        OPTIMIZATION PARAMETERS:
        - Number of prosumers: {self.n}
        - Output prosumer: no. {self.prosumer}
        - Optimization start time: {self.start}
        - Sampling time (Delta): {self.Delta} min.
        - Optimization mode: {self.mode}
        """

        
    def ec_optimizer(self, app_str=None, user_preference=None,  output_csv="optim_results.csv"):
        n, Delta, Ups, h, hh, t0 = self.n, self.Delta, self.Ups, self.h, self.hh, self.start
        #print(n, self.prosumer)

        # Derivati temporali
        T = h * Ups
        Y = hh * Ups
        S = Y * Delta

        # Vincoli fisici
        emax = 10 * np.ones((n, 1))
        rmax, dmax = (3.5 * 1.05) * np.ones((n, 1)), (3.5 * 1.05) * np.ones((n, 1))
        pmax, smax = (6 * 1.05) * np.ones((n, 1)), (6 * 1.05) * np.ones((n, 1))
        vemax, vemin = np.ones((T, 1)), np.zeros((T, 1)) #se modifico il valore minimo di SoC a 0.1, l'ottimzzatore va in crash
        eta_da = 0.98 * np.ones((n, 1))
        eta_r = 0.90 * np.ones((n, 1))
        eta_d = 0.95 * np.ones((n, 1))

        # serve per il salvataggio su csv
        output_records = []

        tf = t0 + datetime.timedelta(minutes=S)
        c_fut, g_fut = np.zeros((Y, n)), np.zeros((Y, n))

        # Matrice di media
        Mtemp = np.kron(np.eye(Y), np.ones((1, Delta)))
        Mwsum = np.where(Mtemp.sum(axis=1) == 0, 1, Mtemp.sum(axis=1))
        Mw = Mtemp / Mwsum[:, np.newaxis]

        # Caricamento dati per ogni prosumer
        for i in range(n):
            if self.mode == 'static':
                file_name = f"fix_H{i + 1}_W_withprice.csv"
                #filename = os.path.join(BASE_DIR, rf"data_fix_withprice/{file_name}")
                #df = pd.read_csv(rf"data_fix_withprice/{file_name}")
                filename = os.path.join(self.data_path, file_name)
                df = pd.read_csv(filename)
            else:
                print(f"==== Running predictions for PROSUMER No. {i+1} using {self.model} model ====")
                df = run_model(self.model) 
                # adatto le previsioni alle preferenze di tempo dell'utente (se espresse)
                if app_str is not None:
                    df['Consumption(W)'] = map_consumption(app_str, user_preference, df['Consumption(W)'].to_list())
                #print(df)
                df = df.reset_index()
            
            mask = pd.to_datetime(df['date']).between(t0, tf, inclusive="left")
            #print(f"df columns: {df.columns}")
            #print(f"df index: {df.index}")
            #print(f"mask sum: {mask.sum()}")
            print(f"mask range: {t0} -> {tf}")
            print(f"df date min: {df['date'].min() if 'date' in df else df.index.min()}")
            print(f"df date max: {df['date'].max() if 'date' in df else df.index.max()}")

            c_fut[:, i] = Mw @ df.loc[mask, 'Consumption(W)'].interpolate().astype(int).to_numpy() / 1000
            g_fut[:, i] = Mw @ df.loc[mask, 'Production(W)'].interpolate().astype(int).to_numpy() / 1000

            if i == 0:
                rho_p_all = Mw @ df.loc[mask, 'Price(eur/kWh)'].interpolate().astype(float).to_numpy()
                rho_s_all = 0.5 * rho_p_all
                rho_sh_all = 0.3 * rho_s_all

        ve0 = 0 * np.ones((n, 1))

        theta = np.zeros((hh + 1, 1))
        r = np.zeros((Y, n))
        d = np.zeros((Y, n))
        p = np.zeros((Y, n))
        s = np.zeros((Y, n))
        ve = np.zeros((Y, n))
        sh_en = np.zeros((hh + 1, 1))

        # passo di ottimizzazione 
        for k in range(Y - T + 1):
            print(f"Step k = {k} of {Y - T}")
            c = c_fut[k:k + T, :n]
            g = g_fut[k:k + T, :n]
            rho_p = rho_p_all[k:k + T].reshape(-1, 1)
            rho_s = rho_s_all[k:k + T].reshape(-1, 1)
            rho_sh = rho_sh_all[k:k + T].reshape(-1, 1)

            r_p, d_p, p_p, s_p, ve_p, theta_p = solve_opt_prob(
                k, n, c, g, Delta, Ups, h, T,
                rmax, dmax, pmax, smax, emax, vemax, vemin,
                rho_p, rho_s, rho_sh,
                eta_da, eta_r, eta_d, ve0
            )

            ve0 = ve_p[[0], :].T
            r[k:k + T, :n] = r_p
            d[k:k + T, :n] = d_p
            p[k:k + T, :n] = p_p
            s[k:k + T, :n] = s_p
            ve[k:k + T, :n] = ve_p
            sh_en[k // Ups] = sh_en[k // Ups] + theta_p.reshape(h + 1, 1)[0]
            sh_en[k // Ups + 1:k // Ups + h + 1] = theta_p.reshape(h + 1, 1)[1:]

        # df e sintesi
        time_index = pd.date_range(start=t0, periods=Y, freq=f"{Delta}min")
        df_production = pd.DataFrame(
            data=np.hstack([p, s, ve]),
            index=time_index,
            columns=[f"Potenza presa p{i + 1}" for i in range(n)] +
                    [f"Potenza immessa p{i + 1}" for i in range(n)] +
                    [f"% Carica batteria  p{i + 1}" for i in range(n)]
        )

        time_index_sh_en = pd.date_range(start=t0, periods=len(sh_en)-1, freq=f"{Delta*Ups}min")
        df_shared_energy = pd.DataFrame(data=sh_en[:-1], index=time_index_sh_en, columns=["Energia condivisa"])

        soc_cols = [c for c in df_production.columns if c.startswith('% Carica batteria')] #cambio da unita' frazionaria a percentuale
        other_cols = [c for c in df_production.columns if c not in soc_cols]

        df_resampled = df_production.resample('1H').agg(
            {**{col: (lambda x: x.iloc[-1]*100) for col in soc_cols}, #aggrego prendendo solo l'ultimo valore dell'ora
             **{col: (lambda x: (x.sum() * (Delta/60))) for col in other_cols}} #qui sommo tutte le potenze istantanee e poi converto in kWh, per avere energia oraria totale
        ).round(2)
        # **{col: 'last' for col in soc_cols} --> alternativa di aggrezazione senza %

        df_resampled_sh = df_shared_energy.resample('1H').sum().round(2) # qui sommo perché sh_en contiene già i dati parziali sull'energia condivisa in una data finestra Delta*Ups

        # Analisi per singolo prosumer
        for prosumer_idx in range(n):
            df_prosumer = df_resampled[
                [f"Potenza presa p{prosumer_idx + 1}",
                 f"Potenza immessa p{prosumer_idx + 1}",
                 f"% Carica batteria  p{prosumer_idx + 1}"]
            ].copy()
            df_prosumer.columns = ["Potenza acquistata", "Potenza immessa in rete", "% Carica batteria"]

            df_final = pd.concat([df_prosumer, df_resampled_sh], axis=1).dropna()
            optim_data = summarize_data(df_final)

            output_records.append({
                "day": t0.strftime("%Y-%m-%d"),
                "prosumer_number": prosumer_idx + 1,
                "energy_data": optim_data
            })

        df_output = pd.DataFrame(output_records)

        #salvo su file l'ottimizzazione completa
        out_path = os.path.join(BASE_DIR, output_csv)
        df_final.to_csv(out_path, index=False)

        #restituisci il dato di un singolo prosumer (convenzionalmente il primo - per parametrizzare la selezione uso attributo self.prosumer-decrementato di 1 per poter essere usato come indice)
        return df_output.iloc[self.prosumer-1]['energy_data']
        

if __name__ == "__main__":
    opt = Optimizer()
    opt.prosumer=1 ##riferimento al prosumer di cui voglioevere i dati
    opt.n=1 #n. di prosumer della rec
    opt.data_folder = 'forecasting'
    opt.start = datetime.datetime.now().astimezone(pytz.timezone("Europe/Rome")).replace(second=0, microsecond=0).replace(tzinfo=None)
    print(opt)
    print(opt.ec_optimizer(app_str="hvac", user_preference="dalle 15"))
