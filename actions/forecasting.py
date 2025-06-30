import numpy as np
import pandas as pd
import joblib, os, requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import date, datetime, timedelta
from matplotlib.ticker import MaxNLocator
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from sklearn.neural_network import MLPRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV
import pytz
from tqdm import tqdm
from .data import PV


class MLPModel:
    def __init__(self, upload_folder='forecasting', model_filename='best_model.joblib', data_filename='resampled_and_merged.csv', scaler_filename="scaler.joblib"):
        self.upload_folder = upload_folder
        self.model_path = os.path.join(upload_folder, model_filename)
        self.data_path =  os.path.join(upload_folder, data_filename)
        os.makedirs(self.upload_folder, exist_ok=True)
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.scaler_path =  os.path.join(upload_folder, scaler_filename)
        self.model = None
        self.param_grid = {'hidden_layer_sizes': [(50, 50), (50, 100), (100, 100)],\
                            'activation': ['relu', 'tanh'], \
                            'learning_rate_init': [0.0001, 0.001, 0.01],
                            'alpha': [0.0001, 0.001],
                           }

    def fetch_weather_data(self, latitude, longitude, start_date, end_date):

        # The order of variables in hourly or daily is important to assign them correctly below
        base_url = "https://api.open-meteo.com/v1/forecast"
        #base_url = "https://historical-forecast-api.open-meteo.com/v1/forecast"
        
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "forecast_days": 1,
            "hourly": "temperature_2m,relative_humidity_2m,cloud_cover,wind_speed_10m"
        }
   
        # Debug dell'URL
        print(f"DEBUG - URL: {base_url}?{requests.compat.urlencode(params)}")
    
        try:
            response = requests.get(base_url, params=params, timeout=300)  # timeout in secondi
    
            print(f"DEBUG - Response Code: {response.status_code}")
            print(f"DEBUG - Response Message: {response.reason}")
    
            if response.ok:
                #print(f"DEBUG - Response Body: {response.text}")
                data = response.json()
                df_weather = pd.DataFrame(data["hourly"])
                #print(df_weather)
                return df_weather
                #return response.text
            else:
                return f"Errore nella richiesta dei dati meteo: {response.reason}"
    
        except requests.exceptions.RequestException as e:
            return f"Errore durante la richiesta HTTP: {str(e)}"


    def preprocess_test_data(self, df_weather, pv):
        #formatto dati meteo (orig.: {"time": [2025-06-21T00:00 ], "temperature_2m": [float], "relative_humidity_2m": [int], "cloud_cover":[int], "wind_speed_10m": [float]})
        #print(df_weather.columns.tolist())
        df_weather.columns = df_weather.columns.str.strip()
        df_weather.rename(columns={"cloud_cover":"Cloudiness(%)","time":"Datetime","temperature_2m": "Temperature(°C)", "relative_humidity_2m": "Humidity(%)","wind_speed_10m": "Wind_speed(m/s)"}, inplace = True)
        #print(df_weather.columns.tolist())
        df_weather["Datetime"] = pd.to_datetime(df_weather["Datetime"], utc=True).dt.tz_convert('Europe/Rome')
        df_weather = df_weather.set_index("Datetime")
        #print(df_weather.head(5))

        #formatto dati solcast (orig: {"intervals": ["2025-06-21T11:00:00.0000000Z"], "values": []})
        df_pv = pd.DataFrame(pv)
        df_pv.rename(columns={"intervals":"Datetime", "values":"Production(kW)"}, inplace=True)
        df_pv["Datetime"] = pd.to_datetime(df_pv["Datetime"], format="%Y-%m-%dT%H:%M:%S", utc=True).dt.tz_convert('Europe/Rome')
        df_pv = df_pv.set_index("Datetime")
        #print(df_pv.head(5))
        
        #dt = datetime.strptime(dt_str[:26], "%Y-%m-%dT%H:%M:%S.%f")
         

        # re-sample using interpolation to propagate the last known values 
        # NOTE: Change interval HERE in case of different time resolution
        df_weather_resampled = df_weather.resample('30T').interpolate()#.reset_index()
        df_weather_resampled
        
        # full join on the "Datetime" column + sort data again
        df_merged = pd.merge(df_pv, df_weather_resampled, on='Datetime', how='outer')
        df_merged.sort_values(by='Datetime', inplace=True)
        # drop rows with NaN values:
        df_merged.dropna(axis=0, inplace=True)
        print(df_merged.head(5))

        return df_merged

       
    def load_data(self, df_data):       
        if 'Datetime' in df_data.columns:
            df_data.drop(columns=['Datetime'], inplace=True)
        X = df_data.drop(columns=["NetLoad(kW)"])
        y = df_data["NetLoad(kW)"]
        #print(X, y)

        return X, y
        

    def train_or_load_model(self):
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
        else: 
            df_data = pd.read_csv(self.data_path)
            X_train, y_train = self.load_data(df_data)
            X_train_scaled = self.scaler.fit_transform(X_train)
            self.model = MLPRegressor(random_state=42, max_iter=1000)
            grid_search = GridSearchCV(
                            self.model,
                            self.param_grid,
                            cv=5,
                            scoring='r2',
                            verbose=2,
                            n_jobs=-1
                        )
            grid_search.fit(X_train_scaled, y_train) 
            self.model = grid_search.best_estimator_
            joblib.dump(self.model, self.model_path)
            joblib.dump(self.scaler, self.scaler_path)
        
        print("Parametri modello: ",self.model.get_params())


    def test_model(self, df_test):

        time = list(df_test.index)
        print(time)
        model = joblib.load(self.model_path)
        scaler = joblib.load(self.scaler_path)
        X_test_scaled = scaler.transform(df_test)        
        y_pred = model.predict(X_test_scaled)

        return y_pred, time


    def plot_predictions(self, time, y_pred, save_path='results_plot.png'):

        plt.figure(figsize=(10, 6))
        plt.plot(time, y_pred, color='blue', linewidth=2)
        plt.xlabel('Data e ora', fontsize=12)
        plt.ylabel('Consumi (kW)', fontsize=12)
        plt.title('Previsioni consumi', fontsize=16)

        plt.xticks(rotation=45, ha='right')
        plt.legend()
        plt.tight_layout()
        plt.savefig(save_path)
        plt.close()

    
    def run_pipeline(self, latitude, longitude, start_date, end_date):
        print(start_date, end_date)
        # carico il modello pre-addestrato o lo ri-addestro, se assente
        self.train_or_load_model()
        
        # carico e preparo i dati nuovi
        #meteo:
        df_weather = self.fetch_weather_data(latitude, longitude, start_date, end_date)
        # previsioni PV:
        pv = PV()
        pv_data = pd.DataFrame(pv.get_pv_forecast())

        #uso il modello per le predizioni:
        X_test = self.preprocess_test_data(df_weather, pv_data)
        results, time = self.test_model(X_test)
        self.plot_predictions(time, results)

        final = {'Ora':time, 'Previsione consumi (kW)': results}
        df = pd.DataFrame(final)

        return df.to_string(index=False)


if __name__ == "__main__":
    mlp=MLPModel()
    latitude = 39.2305400
    longitude = 9.1191700
    #start_date = datetime.now() + timedelta(hours=2) #aggiungo manualmente, ma va sistemato!!!
    now = datetime.now()
    local_timezone = pytz.timezone("Europe/Berlin")
    start_date = now.astimezone(local_timezone).replace(second=0, microsecond=0).replace(tzinfo=None)
    end_date = start_date + timedelta(hours=24) 
    #mlp.fetch_weather_data(latitude, longitude, start_date, end_date)
    #mlp.load_and_prepare_data()
    print(mlp.run_pipeline(latitude, longitude, start_date, end_date))
    """
{'activation': 'relu', 'alpha': 0.0001, 'batch_size': 'auto', 'beta_1': 0.9, 'beta_2': 0.999, 'early_stopping': False, 'epsilon': 1e-08, 'hidden_layer_sizes': (100,), 'learning_rate': 'constant', 'learning_rate_init': 0.001, 'max_fun': 15000, 'max_iter': 200, 'momentum': 0.9, 'n_iter_no_change': 10, 'nesterovs_momentum': True, 'power_t': 0.5, 'random_state': 42, 'shuffle': True, 'solver': 'adam', 'tol': 0.0001, 'validation_fraction': 0.1, 'verbose': False, 'warm_start': False}
    """

