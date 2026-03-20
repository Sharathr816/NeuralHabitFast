import os
import joblib
import numpy as np

from forecasting.feature_builder import compute_sbii_features

MODEL_PATH = os.path.abspath( #X://projects/nhfast/backend/forecasting/sbii_model.pkl
    os.path.join( #X://projects/nhfast/backend/service/../forecasting/sbii_model.pkl
        os.path.dirname(__file__), "..", "forecasting", "sbii_model.pkl" 
        ) 
        )

# Load once
model = None


def load_sbii_model():
    global model
    if model is None:
        print("Loading SBII model...")
        model = joblib.load(MODEL_PATH)
        print("SBII model loaded")


def predict_sbii(user_id: int) -> float:
    """
    Returns probability of relapse (sbii_score)
    """

    if model is None:
        load_sbii_model()

    # 1. Get features
    features = compute_sbii_features(user_id)
    if features is None:
        print(f"[SBII] Skipping prediction for user {user_id} (insufficient data)")
        return None

    # 2. Convert to correct order
    feature_order = [
        "avg_risk_3d",
        "risk_slope",
        "sleep_avg_3d",
        "sleep_variance_3d",
        "screen_avg_3d",
        "screen_spike",
        "negative_emotion_count_3d"
    ]

    X = np.array([[features[f] for f in feature_order]])

    # 3. Predict probability
    prob = model.predict_proba(X)[0][1]

    return float(prob)