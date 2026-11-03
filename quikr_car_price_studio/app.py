from pathlib import Path
import os, re, json
import numpy as np
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "quikr_car.csv"
app = Flask(__name__)
raw_df = None
data_df = None
trained = {}

MODEL_NAMES = {
    "Random Forest": "Random Forest",
    "Extra Trees": "Extra Trees",
    "Gradient Boosting": "Gradient Boosting",
    "Ridge Regression": "Ridge Regression",
}

def numeric_from_text(value):
    text = str(value).replace(",", "").strip()
    if not text or "ask" in text.lower():
        return np.nan
    match = re.search(r"\d+(?:\.\d+)?", text)
    return float(match.group()) if match else np.nan

def prepare_data():
    global raw_df, data_df
    raw_df = pd.read_csv(DATA_PATH)
    required = ["name", "company", "year", "Price", "kms_driven", "fuel_type"]
    missing = [c for c in required if c not in raw_df.columns]
    if missing:
        raise ValueError("Dataset is missing columns: " + ", ".join(missing))
    df = raw_df.copy()
    df["price_numeric"] = df["Price"].map(numeric_from_text)
    df["kms_numeric"] = df["kms_driven"].map(numeric_from_text)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    for col in ["name", "company", "fuel_type"]:
        df[col] = df[col].fillna("Unknown").astype(str).str.strip()
        df.loc[df[col].eq(""), col] = "Unknown"
    df = df.replace([np.inf, -np.inf], np.nan)
    usable = df.dropna(subset=["price_numeric", "year", "kms_numeric"]).copy()
    usable = usable[(usable["price_numeric"] > 1000) & (usable["year"].between(1980, 2026)) & (usable["kms_numeric"] >= 0)]
    data_df = usable.reset_index(drop=True)

def make_model(name):
    if name == "Extra Trees":
        estimator = ExtraTreesRegressor(n_estimators=160, min_samples_leaf=2, random_state=42, n_jobs=-1)
    elif name == "Gradient Boosting":
        estimator = GradientBoostingRegressor(n_estimators=100, learning_rate=0.05, max_depth=2, random_state=42)
    elif name == "Ridge Regression":
        estimator = Ridge(alpha=10.0)
    else:
        estimator = RandomForestRegressor(n_estimators=160, min_samples_leaf=2, random_state=42, n_jobs=-1)
    categorical = ["name", "company", "fuel_type"]
    numeric = ["year", "kms_numeric"]
    prep = ColumnTransformer([
        ("categorical", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encode", OneHotEncoder(handle_unknown="ignore"))
        ]), categorical),
        ("numeric", Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scale", StandardScaler())
        ]), numeric)
    ])
    return Pipeline([("preprocess", prep), ("model", estimator)])

def fit_evaluate(name, test_size=0.2, seed=42):
    features = ["name", "company", "year", "kms_numeric", "fuel_type"]
    X = data_df[features]
    y = data_df["price_numeric"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=seed)
    model = make_model(name)
    model.fit(X_train, y_train)
    pred = np.maximum(0, model.predict(X_test))
    metrics = {
        "mae": float(mean_absolute_error(y_test, pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_test, pred))),
        "r2": float(r2_score(y_test, pred)),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "test_size": float(test_size),
        "model": name,
        "seed": int(seed)
    }
    return model, metrics

def model_comparison(test_size=0.2, seed=42):
    rows = []
    for name in MODEL_NAMES:
        try:
            _, m = fit_evaluate(name, test_size, seed)
            rows.append(m)
        except Exception as e:
            rows.append({"model": name, "error": str(e)})
    return rows

def dataset_summary():
    df = data_df
    raw = raw_df
    price = df["price_numeric"]
    year_price = df.groupby(df["year"].astype(int))["price_numeric"].median().sort_index()
    price_bins = pd.cut(price, bins=[0, 50000, 100000, 200000, 350000, 500000, 1000000, np.inf],
                        labels=["≤50k", "50–100k", "100–200k", "200–350k", "350–500k", "500k–10L", "10L+"])
    return {
        "total_rows": int(len(raw)),
        "usable_rows": int(len(df)),
        "excluded_rows": int(len(raw) - len(df)),
        "duplicates": int(raw.duplicated().sum()),
        "columns": list(raw.columns),
        "missing": {str(k): int(v) for k, v in raw.isna().sum().items()},
        "median_price": float(price.median()),
        "mean_price": float(price.mean()),
        "min_price": float(price.min()),
        "max_price": float(price.max()),
        "min_year": int(df["year"].min()),
        "max_year": int(df["year"].max()),
        "companies": sorted(df["company"].unique().tolist()),
        "names": sorted(df["name"].unique().tolist()),
        "fuels": sorted(df["fuel_type"].unique().tolist()),
        "fuel_counts": {str(k): int(v) for k,v in df["fuel_type"].value_counts().items()},
        "company_counts": {str(k): int(v) for k,v in df["company"].value_counts().head(10).items()},
        "price_bins": {str(k): int(v) for k,v in price_bins.value_counts(sort=False).items()},
        "year_medians": [{"year": int(k), "price": float(v)} for k,v in year_price.items()],
        "scatter": [{"kms": float(r.kms_numeric), "price": float(r.price_numeric)} for r in df.sample(min(180, len(df)), random_state=42).itertuples()],
        "price_quantiles": {
            "p25": float(price.quantile(.25)), "p50": float(price.quantile(.5)),
            "p75": float(price.quantile(.75))
        }
    }

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/summary")
def summary():
    return jsonify(dataset_summary())

@app.post("/api/evaluate")
def evaluate():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Please submit valid model settings."}), 400

    model_name = body.get("model", "Random Forest")
    if model_name not in MODEL_NAMES:
        return jsonify({"error": "Choose a supported regression model."}), 400

    try:
        test_size = float(body.get("test_size", 0.2))
        seed = int(body.get("seed", 42))
    except (TypeError, ValueError, OverflowError):
        return jsonify({"error": "Test split and random seed must be valid numbers."}), 400

    if not 0.1 <= test_size <= 0.4:
        return jsonify({"error": "Test split must be between 10% and 40%."}), 400
    if not 0 <= seed <= 99999:
        return jsonify({"error": "Random seed must be between 0 and 99,999."}), 400

    try:
        model, metrics = fit_evaluate(model_name, test_size, seed)
        trained["active"] = {
            "model": model,
            "features": ["name", "company", "year", "kms_numeric", "fuel_type"],
            "metrics": metrics,
        }
        return jsonify({"selected": metrics, "comparison": model_comparison(test_size, seed)})
    except Exception:
        app.logger.exception("Model evaluation failed")
        return jsonify({"error": "Model training failed. Check the dataset and try again."}), 500

@app.post("/api/predict")
def predict():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Please submit valid vehicle details."}), 400

    active = trained.get("active")
    if not active:
        return jsonify({"error": "The model is not ready yet. Please try again shortly."}), 400

    try:
        year = int(body.get("year", 2016))
        kms = float(body.get("kms", 50000))
        if not 1980 <= year <= 2026:
            return jsonify({"error": "Manufacturing year must be between 1980 and 2026."}), 400
        if not np.isfinite(kms) or not 0 <= kms <= 5_000_000:
            return jsonify({"error": "Kilometres driven must be between 0 and 5,000,000."}), 400

        def clean_category(value, fallback):
            text = str(value if value is not None else fallback).strip()
            return text[:160] if text else fallback

        row = pd.DataFrame([{
            "name": clean_category(body.get("name"), "Unknown"),
            "company": clean_category(body.get("company"), "Unknown"),
            "year": year,
            "kms_numeric": kms,
            "fuel_type": clean_category(body.get("fuel_type"), "Unknown"),
        }])
        prediction = max(0, float(active["model"].predict(row[active["features"]])[0]))
        return jsonify({
            "price": prediction,
            "low": max(0, prediction * .82),
            "high": prediction * 1.18,
            "model": active["metrics"]["model"],
        })
    except (TypeError, ValueError, OverflowError):
        return jsonify({"error": "Please enter a valid year and kilometre value."}), 400
    except Exception:
        app.logger.exception("Price prediction failed")
        return jsonify({"error": "Could not calculate a price. Please try again."}), 500

@app.get("/api/dataset.csv")
def download():
    return send_file(DATA_PATH, as_attachment=True, download_name="quikr_car.csv")

if __name__ == "__main__":
    prepare_data()
    # Load an initial trained model so prediction works immediately.
    model, metrics = fit_evaluate("Random Forest", .2, 42)
    trained["active"] = {"model": model, "features": ["name", "company", "year", "kms_numeric", "fuel_type"], "metrics": metrics}
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5050)), debug=False)
