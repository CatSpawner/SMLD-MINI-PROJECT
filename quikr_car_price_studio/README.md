# MotorMetric — Quikr Used-Car Price Studio

A local dashboard for exploring the supplied Quikr used-car listings, comparing regression models, and estimating an indicative resale price.

## What's included

- **Overview:** listing counts, median price, price bands, fuel mix, and median prices by model year.
- **Price estimator:** choose a car, manufacturer, fuel type, year, and kilometres driven to get an estimate.
- **Data explorer:** inspect missing values, duplicate rows, manufacturer coverage, and feature preparation.
- **Model lab:** train and compare Random Forest, Extra Trees, Gradient Boosting, and Ridge Regression using a shared train/test split.
- **Export:** download the original CSV.

The interface is responsive, keyboard-focus friendly, and uses local assets. The app binds to `127.0.0.1`, so it is intended for use on your own computer.

## Requirements

- Python 3.10 or newer
- Internet access only if you need to install the Python packages for the first time

## Run on Windows

1. Extract this ZIP file.
2. Open Command Prompt in the extracted `quikr_car_price_studio` folder.
3. Run:

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

4. Open <http://127.0.0.1:5050> in your browser.

## Run on macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Then open <http://127.0.0.1:5050>.

To stop the server, focus the terminal and press `Ctrl+C`.

## Dataset and modelling notes

The app expects `data/quikr_car.csv` to contain `name`, `company`, `year`, `Price`, `kms_driven`, and `fuel_type`. Prices and kilometres are converted from text to numeric values. Rows without usable price, year, or kilometres are excluded from model training; “Ask For Price” is not a numeric target. Categorical features are one-hot encoded, while numeric features are imputed and scaled.

Model metrics are calculated on a held-out test set. MAE and RMSE are in the dataset's price units (assumed to be INR); lower is generally better. An R² score closer to 1 is generally better, but can be negative on a weak model.

**Important:** this is an educational project, not a professional vehicle valuation service. Listings can be noisy, outdated, or inconsistent. The displayed price band is a simple ±18% around the estimate; it is not a calibrated confidence interval. The model can perform poorly for rare models or vehicles unlike those in the dataset.

## Troubleshooting

- If package installation fails, check your Python version and internet connection.
- If the app says the dataset cannot be loaded, make sure `data/quikr_car.csv` is still inside the project folder.
- If port `5050` is already in use, close the other process or start the app with a different `PORT` environment variable.
