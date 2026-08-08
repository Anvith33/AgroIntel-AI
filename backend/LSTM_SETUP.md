# AgroIntel v4.0 — Isolated LSTM Training Environment Setup Guide

## Overview

In AgroIntel v4.0, the main FastAPI backend is kept lightweight and runs in Python 3.13 without heavy C-level deep learning dependencies.

Because TensorFlow C-libraries experience binary compatibility issues on Python 3.13 under macOS, **LSTM model training is completely isolated into a dedicated Python 3.11 environment**.

---

## Architecture Principle

1. **Backend Separation**: The FastAPI backend (`app/main.py`) **NEVER** trains LSTM models. It only loads pre-saved `.keras` models or `.pkl` XGBoost/Prophet models during inference.
2. **Lightweight Deployment**: Production deployment does not require TensorFlow in the primary API runtime if XGBoost/Prophet are selected as production models. If an LSTM `.keras` file is present, it can be loaded cleanly.

---

## Step-by-Step Setup Guide for LSTM Training

### Step 1: Create a Python 3.11 Virtual Environment

```bash
# Using conda / mamba
conda create -n agrointel-lstm python=3.11 -y
conda activate agrointel-lstm

# OR using pyenv + venv
pyenv install 3.11.8
pyenv local 3.11.8
python -m venv venv-lstm
source venv-lstm/bin/activate
```

### Step 2: Install LSTM Dependencies

```bash
pip install -r requirements-lstm.txt
```

### Step 3: Run the Isolated LSTM Trainer

From the backend root directory (`/Users/kaushikpoojary/Downloads/projectphase2/backend`):

```bash
python -m app.ml.train_lstm
```

---

## Output Artifacts

The standalone trainer generates and saves the following artifacts into the `models/` directory:

| Artifact File | Description |
| :--- | :--- |
| `models/lstm_wheat.keras` | Trained Keras LSTM model for Wheat |
| `models/lstm_scaler_wheat.pkl` | Fitted StandardScaler for Wheat features |
| `models/lstm_rice.keras` | Trained Keras LSTM model for Rice |
| `models/lstm_scaler_rice.pkl` | Fitted StandardScaler for Rice features |
| `models/lstm_maize.keras` | Trained Keras LSTM model for Maize |
| `models/lstm_scaler_maize.pkl` | Fitted StandardScaler for Maize features |
| `models/lstm_potato.keras` | Trained Keras LSTM model for Potato |
| `models/lstm_scaler_potato.pkl` | Fitted StandardScaler for Potato features |
| `models/lstm_onion.keras` | Trained Keras LSTM model for Onion |
| `models/lstm_scaler_onion.pkl` | Fitted StandardScaler for Onion features |

---

## Runtime Loading Logic in Backend

When the backend starts or predicts:
```python
if os.path.exists("models/lstm_wheat.keras"):
    # Load model for prediction
    model = tf.keras.models.load_model("models/lstm_wheat.keras")
else:
    # Use fallback production model (XGBoost / Prophet)
    model = load_xgboost_or_prophet()
```

---
*AgroIntel v4.0 Technical Guide — LSTM Environment Isolation*
