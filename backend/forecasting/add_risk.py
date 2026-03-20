import os
import joblib
import pandas as pd
import numpy as np

# =============================
# PATHS (adjust if needed)
# =============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INPUT_FILE = os.path.join(BASE_DIR, "Analysis", "Synthetic_dataset2000_moderate_realism.csv")
MODEL_PATH = os.path.join(BASE_DIR, "Analysis", "xgb_model.joblib")
FEATURE_COLS_PATH = os.path.join(BASE_DIR, "Analysis", "feature_cols.joblib")

OUTPUT_FILE = os.path.join(BASE_DIR, "forecasting", "synthetic_with_risk.csv")


# =============================
# LOAD MODEL
# =============================
print("Loading model...")
model = joblib.load(MODEL_PATH)
feature_cols = joblib.load(FEATURE_COLS_PATH)

print("Model loaded.")
print("Feature cols:", len(feature_cols))


#============================
# EMOTION LABELS AND GROUPS
#============================
EMOTION_LABELS = [
    "Admiration", "Amusement", "Anger", "Annoyance", "Approval", "Caring", "Confusion",
    "Curiosity", "Desire", "Disappointment", "Disapproval", "Disgust", "Embarrassment",
    "Excitement", "Fear", "Gratitude", "Grief", "Joy", "Love", "Nervousness", "Optimism",
    "Pride", "Realization", "Relief", "Remorse", "Sadness", "Surprise", "Neutral"
]

NEL = [
    "Sadness", "Grief", "Anger", "Fear", "Nervousness",
    "Remorse", "Disappointment", "Disgust", "Annoyance"
]

PEL = [
    "Joy", "Excitement", "Gratitude", "Optimism",
    "Admiration", "Relief", "Pride", "Love"
]

Neutral_Emotions = set(EMOTION_LABELS) - set(NEL) - set(PEL)


# =============================
# PREPROCESS FUNCTION
# =============================
def build_feature_row(row_dict):
    rf = row_dict.copy()

    # -------- Emotion score adjustment --------
    emo = rf.get("dominant_emotion")
    score = rf.get("emotion_score")

    if emo is not None and score is not None:
        score = float(score)

        if emo in PEL:
            # Positive → make negative
            rf["emotion_score"] = -abs(score)

        elif emo in Neutral_Emotions:
            # Neutral → zero
            rf["emotion_score"] = 0.0

        else:
            # Negative → keep as is
            rf["emotion_score"] = score

    # -------- One-hot encoding --------
    emo_cols = [c for c in feature_cols if c.startswith("dominant_emotion_")]
    ent_cols = [c for c in feature_cols if c.startswith("dominant_entity_")]

    # zero initialize
    for c in emo_cols:
        rf[c] = 0
    for c in ent_cols:
        rf[c] = 0

    # set emotion
    emo = rf.get("dominant_emotion")
    if emo:
        col = f"dominant_emotion_{emo}"
        if col in emo_cols:
            rf[col] = 1

    # set entity
    ent = rf.get("dominant_entity")
    if ent:
        col = f"dominant_entity_{ent}"
        if col in ent_cols:
            rf[col] = 1

    # -------- Build DF --------
    df_row = pd.DataFrame([rf])

    # ensure all required columns exist
    for col in feature_cols:
        if col not in df_row.columns:
            df_row[col] = 0

    df_row = df_row[feature_cols]

    # cast
    df_row = df_row.astype(float)

    return df_row


# =============================
# MAIN FUNCTION
# =============================
def add_risk_scores():
    df = pd.read_csv(INPUT_FILE)

    risks = []

    print("Processing rows...")

    for i, row in df.iterrows():
        try:
            row_dict = row.to_dict()
            df_row = build_feature_row(row_dict)

            prob = model.predict_proba(df_row)[0][1]  # class 1
            risks.append(prob)

        except Exception as e:
            print(f"Error at row {i}: {e}")
            risks.append(0.0)

    df["risk_score"] = risks

    df.to_csv(OUTPUT_FILE, index=False)

    print("✅ Done.")
    print("Saved to:", OUTPUT_FILE)
    print(df.head())


# =============================
# RUN
# =============================
if __name__ == "__main__":
    add_risk_scores()