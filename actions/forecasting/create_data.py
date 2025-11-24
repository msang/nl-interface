import os, pytz
import pandas as pd
from datetime import datetime, timedelta
from .LSTMRegressor import SolarLSTMModel
from .MLPRegressor import SolarMLPModel
from ..monitoring import EnergyMonitoring as EM


def get_predictions(f_model, f,dim, start_time, end_time, forecasting_horizon=1, n_lags=30, extra_features=None):
    
    #now = datetime.now() #NB: il tempo di avvio delle predizioni è il punto finale della sequenza temporale passata come dato storico
    #local_timezone = pytz.timezone("Europe/Rome")
    #start_time = now.astimezone(local_timezone).replace(second=0, microsecond=0).replace(tzinfo=None) 
    
    em = EM()
    if dim in ('Production(W)','Consumption(W)'):
        last_values = em.get_historic_production_and_consumption_data(start_time, f)[dim].to_list()[-n_lags:] 
    else:
        last_values = em.get_historic_bess_data(start_time)[dim].to_list()[-n_lags:]  
    #"""
    #print(f"LAST VALUES for {dim.upper()}: {last_values}")
    if f_model == 'LSTM':
        model = SolarLSTMModel(upload_folder=f, forecast_dim=dim, mode='autoregressive')
    else:
        model= SolarMLPModel(upload_folder=f, forecast_dim=dim, mode='autoregressive')
    #print(lstm)
    #end_time = start_time + timedelta(hours=forecasting_horizon) 
    preds = model.run_pipeline(start_time, end_time, last_values=last_values, extra_features=extra_features)

    #print(preds)
    return preds


def tarifs(dt):
    h = dt.hour
    if 0 <= h <= 6: #00:00-06:59
        return 0.17
    elif h == 7 or 19 <= h <= 23: # 07:00-07:59 e 19:00-23:59
        return 0.19
    else:  # 08:00–18:59
        return 0.21


def run_model(f_model='LSTM',now=None):
    """
    Esegue run_pipeline()
    prende le predizioni e le salva in un dataframe impostando l'intestazione della colonna in base alla dimensione desiderata
    NB: il dataframe è sempre lo stesso, viene popolato in modo incrementale
    al dataframe completo di tutte le predizioni va poi aggiunta la colonna del prezzo
    """
    folders = ['Production','Consumption','SoC','Charge','Discharge']
    forecast_dims=['Production(W)','Consumption(W)','State of Charge(%)','Charge(W)','Discharge(W)']
    extra_features={}
    path = os.getcwd()
    df_final = pd.DataFrame()

    #intervallo di previsione:
    if now is None:
        now = datetime.now().astimezone(pytz.timezone("Europe/Rome")).replace(second=0, microsecond=0).replace(tzinfo=None)
    forecasting_horizon = 24  # ore
    n_lags = 30
    end_time = now + timedelta(hours=forecasting_horizon)
    
    for f,dim in zip(folders,forecast_dims):
        #dim_path = os.listdir(os.path.join(path,f))
        print(f" ------ {f} ------- ")
                  
        preds = get_predictions(f_model,f,dim, now, end_time, forecasting_horizon,n_lags, extra_features)
        preds.rename(columns={'timestamp': 'date'}, inplace=True)
        preds['date'] = pd.to_datetime(preds['date'])
        preds.set_index('date', inplace=True)
        #preds['timestamp'] = pd.to_datetime(preds['timestamp'])
        #preds.set_index('timestamp', inplace=True)

        if 'predicted' in preds.columns:
            preds.rename(columns={'predicted': dim}, inplace=True)

        # tronca a 0 tutti i valori negativi (per non far crashare l'ottimizzatore)
        preds[dim] = preds[dim].clip(lower=0.0).astype(float)

        if df_final.empty:
            df_final = preds.copy() ##se è il primo giro di predizioni, copio sia indice che predizioni, per gli altri prendo solo le predizioni
        else:
            df_final[dim] = preds[dim].values        
    #aggiungo la colonna del prezzo con tariffa oraria
    df_final['Price(eur/kWh)'] = df_final.index.map(tarifs)

    print(df_final.head())
    return df_final
            


if __name__ == "__main__":
    m='MLP'
    run_model(m)
        
        






