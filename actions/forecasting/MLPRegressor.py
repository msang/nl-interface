import joblib, os, pytz, torch
import numpy as np
import torch.nn as nn
import torch.optim as optim
from datetime import datetime, timedelta
import pandas as pd
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.preprocessing import MinMaxScaler
from torch.utils.data import TensorDataset, DataLoader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Source - https://stackoverflow.com/a
# Posted by Mike, modified by community. See post 'Timeline' for change history
# Retrieved 2025-11-07, License - CC BY-SA 4.0

import warnings
warnings.filterwarnings("ignore")


# ============================================================
# Classe base
# ============================================================
class MLPRegressor(nn.Module):
    def __init__(self, input_size, n_lags=30, hidden_sizes=[128,64,32], dropout=0.2, output_size=1):
        super(MLPRegressor, self).__init__()
        self.n_lags=n_lags       
        self.input_size = input_size
        in_dim = input_size * n_lags

        layers = []
        last_dim = in_dim
        for h in hidden_sizes:
            layers += [
                nn.Linear(last_dim, h),
                nn.ReLU(),
                nn.Dropout(dropout)
            ]
            last_dim = h
        layers.append(nn.Linear(last_dim, output_size))
        self.model = nn.Sequential(*layers)
        

    def forward(self, x):
        # x shape: (batch, n_lags, input_size)
        x = x.reshape(x.size(0), -1)  # Flatten sequence
        return self.model(x)


# ============================================================
#  Classe principale
# ============================================================
class SolarMLPModel:
    def __init__(self, n_lags=30, upload_folder="forecasting", device=None,
                 data_filename="resampled_and_merged.csv",
                 forecast_dim="Production(W)", mode="autoregressive"):
        self.n_lags = n_lags
        self.upload_folder = os.path.join(BASE_DIR, upload_folder)
        #self.data_path = data_filename #os.path.join(upload_folder, data_filename)
        self.data_path = os.path.join(BASE_DIR, data_filename)
        self.forecast_dim = forecast_dim
        self.mode = mode
        self.model = None
        self.base_features = ['hour_sin', 'hour_cos', 'day_sin', 'day_cos']
        self.scaler_X = MinMaxScaler(feature_range=(0, 1))
        self.scaler_y = MinMaxScaler(feature_range=(0, 1))
        self.scaler_X_path = os.path.join(self.upload_folder, f"scaler_X_{self.forecast_dim.replace(' ', '_')}.joblib")
        self.scaler_y_path = os.path.join(self.upload_folder, f"scaler_y_{self.forecast_dim.replace(' ', '_')}.joblib")
        os.makedirs(os.path.join(BASE_DIR, upload_folder), exist_ok=True)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")


    def __repr__(self):
        return f"Initialized LSTM regressor for the forecasting of {self.forecast_dim} in {self.mode} mode. Model and scalers can be found at '{self.upload_folder}' folder. Available device: {self.device}."

    # ============================================================
    # Selezione dinamica delle feature in base alla variabile target --- metodo scartato: non uso le feature aggiuntive, ma solo quelle temporali
    # ============================================================
    def get_feature_columns(self):
        """ Restituisce la lista completa di feature """
        #"""Definisce quali feature usare in base alla variabile target"""
        #base_features = ['hour_sin', 'hour_cos', 'day_sin', 'day_cos']
        #if self.forecast_dim == "State of Charge(%)":
        #    return [self.forecast_dim, 'Production(W)', 'Consumption(W)'] + base_features
       # elif self.forecast_dim in ["Charge(W)", "Discharge(W)"]:
       #     return [self.forecast_dim, 'Production(W)', 'Consumption(W)', 'State of Charge(%)'] + base_features
        #else:
        return [self.forecast_dim] + self.base_features


    # ============================================================
    def load_data(self, df_data=None):
        if df_data is None:
            df = pd.read_csv(self.data_path)
        else:
            df = df_data.copy()

        df.columns = df.columns.str.strip()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)

        if "NetLoad(kW)" in df.columns:
            df['Consumption(W)'] = df["NetLoad(kW)"] * 1000
            df.drop('NetLoad(kW)', axis=1, inplace=True)
        if "Production(kW)" in df.columns:
            df['Production(W)'] = df["Production(kW)"] * 1000
            df.drop('Production(kW)', axis=1, inplace=True)

        # Aggiunta delle feature temporali
        df['hour'] = df['date'].dt.hour + df['date'].dt.minute / 60.0
        df['dayofyear'] = df['date'].dt.dayofyear
        df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
        df['day_sin'] = np.sin(2 * np.pi * df['dayofyear'] / 365)
        df['day_cos'] = np.cos(2 * np.pi * df['dayofyear'] / 365)
        
        return df

    # ============================================================
    def create_lagged_dataset(self, df, n_lags):
        data = df.values
        X, y = [], []
        for i in range(len(data) - n_lags):
            X.append(data[i:i + n_lags, :])
            y.append(data[i + n_lags, 0])  # prima colonna = target
        return np.array(X), np.array(y)

    # ============================================================
    def prepare_monthly_data(self, df, year, month):
        month_start = pd.Timestamp(f'{year}-{month:02d}-01 00:00:00')
        month_end = month_start + pd.DateOffset(months=1) - pd.Timedelta(minutes=1)

        df_month = df[(df['date'] >= month_start) & (df['date'] <= month_end)].copy()
        df_month = df_month.sort_values('date').reset_index(drop=True)
        if df_month.empty:
            print(f"No data for {month}/{year}. Skipping.")
            return None, None, None, None, None

        train_end = month_start + pd.DateOffset(days=21) - pd.Timedelta(minutes=1)
        test_start = month_start + pd.DateOffset(days=21)

        feature_cols = self.get_feature_columns()

        train_data = df_month[df_month['date'] <= train_end][feature_cols].copy()
        test_data = df_month[df_month['date'] >= test_start][feature_cols].copy()
        timestamps_test = df_month[df_month['date'] >= test_start]['date'].values

        if len(train_data) < self.n_lags or len(test_data) == 0:
            print(f"Insufficient data for {month}/{year}. Skipping.")
            return None, None, None, None, None

        full_data = pd.concat([train_data, test_data]).reset_index(drop=True)
        X_full, y_full = self.create_lagged_dataset(full_data, self.n_lags)
        n_train_samples = len(train_data) - self.n_lags

        X_train = X_full[:n_train_samples]
        y_train = y_full[:n_train_samples]
        X_test = X_full[n_train_samples:]
        y_test = y_full[n_train_samples:]

        #prove autocorrelazione:
        df = pd.DataFrame({'X_t': y_train, 'X_t-1': X_train})
        print(df['X_t'].corr(df['X_t-1']))

        print(f"Train shape: {X_train.shape}, Test shape: {X_test.shape}")
        return X_train, y_train, X_test, y_test, timestamps_test

    # ============================================================
    def train_or_load_model(self, df_data, month, year, epochs=50, batch_size=64):
        year = year - 1
        model_path = os.path.join(self.upload_folder, f"mlp_model_{month}-{year}_{self.forecast_dim.replace(' ', '_')}.pt")

        input_size = len(self.get_feature_columns())#feature temporali + colonna del dato da predire

        #CONTROLLO SUL MODELLO
        if os.path.exists(model_path):
            print(f"Loading pretrained model for {month}/{year}")
            self.model = MLPRegressor(input_size=input_size).to(self.device)
            self.model.load_state_dict(torch.load(model_path, map_location=self.device))

            # CONTROLLO SUGLI SCALER
            for s_path, attr in [(self.scaler_X_path, 'X'), (self.scaler_y_path, 'y')]:
                if os.path.exists(s_path):
                    scaler = joblib.load(s_path)
                    if hasattr(scaler, "scale_") and hasattr(scaler, "min_"):
                        setattr(self, f'scaler_{attr}', scaler)
                        #print(f"Loaded fitted scaler_{attr} from {s_path}")
                    else:
                        print(f"Warning: scaler_{attr} at {s_path} is not fitted. Will be re-fitted.")
                        setattr(self, f'scaler_{attr}', None)
                else:
                    print(f"Scaler file not found: {s_path}")
                    setattr(self, f'scaler_{attr}', None)

        else:
            print(f"No model found for {month}/{year}, training...")
            df = self.load_data(df_data)
            X_train, y_train, _, _, _ = self.prepare_monthly_data(df, year=year, month=month)
            #if X_train is None: return

            self.scaler_X.fit(X_train.reshape(-1, X_train.shape[-1]))
            self.scaler_y.fit(y_train.reshape(-1, 1))
            X_train_scaled = self.scaler_X.transform(X_train.reshape(-1, X_train.shape[-1])).reshape(X_train.shape)
            y_train_scaled = self.scaler_y.transform(y_train.reshape(-1, 1))

            train_loader = DataLoader(TensorDataset(torch.tensor(X_train_scaled, dtype=torch.float32),
                                                    torch.tensor(y_train_scaled, dtype=torch.float32)),
                                      batch_size=batch_size, shuffle=True)

            self.model = MLPRegressor(input_size=input_size).to(self.device)
            criterion = nn.MSELoss()
            optimizer = optim.Adam(self.model.parameters(), lr=1e-3)

            for epoch in range(epochs):
                self.model.train()
                epoch_loss = 0
                for xb, yb in train_loader:
                    xb, yb = xb.to(self.device), yb.to(self.device)
                    optimizer.zero_grad()
                    preds = self.model(xb)
                    loss = criterion(preds, yb)
                    loss.backward()
                    optimizer.step()
                    epoch_loss += loss.item() * len(xb)
                epoch_loss /= len(train_loader.dataset)
                if (epoch + 1) % 10 == 0:
                    print(f"Epoch {epoch + 1}/{epochs} - Loss: {epoch_loss:.5f}")

            torch.save(self.model.state_dict(), model_path)
            joblib.dump(self.scaler_X, self.scaler_X_path)
            joblib.dump(self.scaler_y, self.scaler_y_path)
            print(f"Model saved at {model_path}")

    # ============================================================
    def autoregressive_predict(self, start_date, end_date, last_values, extra_features=None, steps_min=1):
        if len(last_values) != self.n_lags:
            raise ValueError(f"last_values deve avere lunghezza {self.n_lags}")
        if self.model is None:
            raise ValueError("Modello non caricato o addestrato.")

        self.model.eval()
        preds, timestamps = [], []
        seq = np.array(last_values).reshape(-1, 1)
        #feature_cols = self.get_feature_columns() --> provo a togliere le feature aggiuntive

        current_time = start_date
        while current_time < end_date:
            seq_with_features = []
            for i in range(self.n_lags):
                time_i = current_time - timedelta(minutes=(self.n_lags - i) * steps_min)
                hour = time_i.hour + time_i.minute / 60.0
                dayofyear = time_i.timetuple().tm_yday
                hour_sin = np.sin(2 * np.pi * hour / 24)
                hour_cos = np.cos(2 * np.pi * hour / 24)
                day_sin = np.sin(2 * np.pi * dayofyear / 365)
                day_cos = np.cos(2 * np.pi * dayofyear / 365)
                row = [seq[i, 0]]

                """
                if "Production(W)" in feature_cols and not self.forecast_dim == "Production(W)":
                    if extra_features and "Production(W)" in extra_features:
                        row.append(extra_features["Production(W)"][i])
                    else:
                        row.append(0.0)  # placeholder se non ho previsioni

                if "Consumption(W)" in feature_cols and not self.forecast_dim == "Consumption(W)":
                    if extra_features and "Consumption(W)" in extra_features:
                        row.append(extra_features["Consumption(W)"][i])
                    else:
                        row.append(100.0) #se non ho i dati metto di default un valore minimo di consumi pari a 0.10 kW

                if "State of Charge(%)" in feature_cols and not self.forecast_dim == "State of Charge(%)":
                    if extra_features and "State of Charge(%)" in extra_features:
                        row.append(extra_features["State of Charge(%)"][i])
                    else:
                        row.append(10.0) #di default il valore minimo di carica
                """


                #row = [seq[i, 0]] + [hour_sin, hour_cos, day_sin, day_cos]
                row+=[hour_sin, hour_cos, day_sin, day_cos]
                seq_with_features.append(row)

            seq_with_features = np.array(seq_with_features)
            seq_scaled = self.scaler_X.transform(seq_with_features)
            x_input = torch.tensor(seq_scaled[np.newaxis, :, :], dtype=torch.float32).to(self.device)

            with torch.no_grad():
                y_scaled = self.model(x_input).cpu().numpy()[0, 0]
                y_next = self.scaler_y.inverse_transform([[y_scaled]])[0, 0]

            preds.append(y_next)
            timestamps.append(current_time)
            seq = np.vstack([seq[1:], [y_next]])
            current_time += timedelta(minutes=steps_min)

        return pd.DataFrame({'timestamp': timestamps, 'predicted': preds})


    def test_model(self, X_test, y_test, timestamps):
        """ Fa solo test statico su test set predefinito"""      
        self.scaler_X = joblib.load(self.scaler_X_path)
        self.scaler_y = joblib.load(self.scaler_y_path)

        X_test_scaled = self.scaler_X.transform(X_test.reshape(-1, X_test.shape[-1])).reshape(X_test.shape)
        y_test_scaled = self.scaler_y.transform(y_test.reshape(-1, 1)).ravel()
        
        self.model.eval()
        X_test_tensor = torch.tensor(X_test_scaled, dtype=torch.float32).to(self.device)
        with torch.no_grad():
            y_pred_scaled = self.model(X_test_tensor).cpu().numpy()#.ravel()
            y_pred = self.scaler_y.inverse_transform(y_pred_scaled.reshape(-1, 1)).ravel()
                
        r2 = r2_score(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)
        mse = mean_squared_error(y_test, y_pred)
        rmse = np.sqrt(mse)

        print(f"R2={r2:.4f}, MAE={mae:.4f}, RMSE={rmse:.4f}")

        # salva csv predizioni:
        results_df = pd.DataFrame({
            'timestamp': timestamps,
            'actual': y_test,
            'predicted': y_pred,
            'residuals': y_test - y_pred
        })

        #TOLGO IL SALVATAGGIO SU FILE
        #results_path = os.path.join(self.upload_folder, f"predictions_{timestamps[0].astype('datetime64[M]').item().strftime('%Y_%m')}.csv")
        #results_df.to_csv(results_path, index=False)
        #print(f"Saved predictions to {results_path}")

        return pd.DataFrame({'timestamp': results_df['timestamp'], 'predicted': results_df['predicted']})


    def run_pipeline(self, start_date, end_date, last_values=[], extra_features=None):
        """ Esegue la pipeline completa di addestramento e predizione/test """
        # carico il modello pre-addestrato o lo ri-addestro, se assente
        year = start_date.year
        month = start_date.month
        df_data = self.load_data()
        self.train_or_load_model(df_data, month, year)

        # faccio test statico o predizioni autoregressive 
        if self.mode == 'autoregressive':
            try:
                y_pred = self.autoregressive_predict(start_date, end_date, last_values, extra_features)
                return y_pred
            except ValueError as e:
                print(e)
                return
        else:
            _, _, X_test, y_test, timestamps = self.prepare_monthly_data(df_data, year=year-1, month=month)
            return self.test_model(X_test, y_test, timestamps)


if __name__ == "__main__":
    mlp = SolarMLPModel(upload_folder="Production", data_filename="resampled_and_merged.csv", forecast_dim="Production(W)", mode="autoregressive")
    now = datetime.now()
    local_timezone = pytz.timezone("Europe/Rome")
    start_date = now.astimezone(local_timezone).replace(second=0, microsecond=0).replace(tzinfo=None)
    #start_date = datetime(2021,1,1,0,0,0)
    end_date = start_date + timedelta(hours=12)
    last_values_production=[190.50446013333334, 179.18538586666665, 167.86631160000002,156.54723733333333, 145.22816306666667, \
                            133.9090888, 122.59001453333335, 111.27094026666666, 99.951866, 99.7467736,99.5416812, 99.3365888, \
                            99.13149639999999, 98.92640399999999, 98.72131159999999, 98.5162192, 98.3111, 98.1060344,97.90094, \
                            97.6958496, 97.49075719999999, 97.28566479999999, 97.0805724, 96.87548, 97.98073566666666, \
                            99.08599133333333, 100.19124699999999, 101.29650266666667, 102.40175833333333, 103.507014]
    last_values_soc = [72.98,72.49,71.99,71.49,70.99,70.58,70.19,69.78,69.39,68.99,\
                       68.592,68.194,67.79,67.398,67.0,66.9,66.8,66.7,66.6,66.5,66.4,\
                       66.3,66.2,66.1,66,65.9,65.8,65.7,65.6,65.5]
    last_values_charge = [2282.014,2288.588,2295.162,2301.736,2308.31,2315.31,2322.31,2329.31,2336.31,2343.31,2351.324, \
                         2359.338,2367.352,2375.366,2383.38,2385.166,2386.952,2388.738,\
                         2390.524,2392.31,2394.748,2397.186,2399.624,2402.062,2404.5,\
                         2415.388,2426.276,2437.164,2448.052,2458.94]
    last_values_discharge=[0.0]*30
    pred = mlp.run_pipeline(start_date, end_date, last_values=last_values_production)
    #pred = mlp.run_pipeline(start_date, end_date)
    print(pred)
