import torch
import os
import joblib
import shap
import pandas as pd
import numpy as np
import datetime
import secrets
import hashlib
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
from db import SessionLocal, engine
from models import Base, Journal, User, HabitAnalysis, HabitInteraction
from schema import JournalIn
from config_main import emotion_labels, entity_labels, emotion_model, entity_model, bert_tokenizer
from config_main import  MODELS_DIR, MODEL_FILENAME, FEATURE_COLS_FILENAME, MODEL_DIR_REC    
from Analysis.utils import NEL, PEL, Neutral_Emotions
from typing import List, Dict, Any
from schema import FeaturesPayload, SignupPayload, LoginPayload, AuthResponse
from pydantic import EmailStr, Field
import tensorflow as tf
from tensorflow.keras import layers, Model, Input
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
import keras.ops as K
from tensorflow.keras.layers import Layer
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

# DEV: allow your frontend origin. For quick testing you can use ["*"], but DON'T use that in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["*"] for quick dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


#only creates tables IF they don’t already exist.
Base.metadata.create_all(bind=engine)

# user authentication utilities
# ---------- Password helpers ----------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
    return f"{salt.hex()}${hashed.hex()}"

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, hash_hex = stored_hash.split("$")
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
        return secrets.compare_digest(candidate, expected)
    except Exception:
        return False

def user_to_response(user: User) -> AuthResponse:
    return AuthResponse(
        user_id=user.user_id,
        name=user.username,
        email=user.email,
        signup_date=user.signup_at,
    )

#Analysis artifacts and utilities
model = None
feature_cols: List[str] = None
explainer = None

@app.on_event("startup")
def load_artifacts():
    global model, feature_cols, explainer
    analysis_model_path = os.path.join(MODELS_DIR, MODEL_FILENAME)
    cols_path = os.path.join(MODELS_DIR, FEATURE_COLS_FILENAME)

    if not os.path.exists(analysis_model_path) or not os.path.exists(cols_path):
        raise RuntimeError(f"Model or feature_cols not found in {MODELS_DIR}/. Expect files: {MODEL_FILENAME}, {FEATURE_COLS_FILENAME}")

    model = joblib.load(analysis_model_path)
    feature_cols = joblib.load(cols_path)  # MUST be list of column names in training order
    # build SHAP explainer once (fast-ish for trees)
    explainer = shap.TreeExplainer(model)
    print(f"Loaded model and feature_cols ({len(feature_cols)} cols). SHAP explainer ready.")



# ========== Analysis utilities ==========
# ---------- SHAP extraction helper ----------
def get_shap_vector_for_positive_class(explainer, df_row: pd.DataFrame) -> np.ndarray:
    """
    Returns a 1-D numpy array of SHAP values aligned to feature_cols for the positive class.
    Works across SHAP versions / return shapes.
    """
    try:
        # Try new API first
        out = explainer(df_row)
        vals = getattr(out, "values", None)
        if vals is not None:
            vals = np.array(vals)
            # (1, n_features)
            if vals.ndim == 2 and vals.shape[0] == 1:
                return vals[0]
            # (n_classes, 1, n_features) or (1, n_classes, n_features)
            if vals.ndim == 3:
                # prefer class index 1 if present
                if vals.shape[0] >= 2 and vals.shape[1] == 1:
                    return vals[1, 0]
                if vals.shape[0] == 1 and vals.shape[1] >= 2:
                    return vals[0, 1]
    except Exception:
        pass

    # Fallback to older API
    raw = explainer.shap_values(df_row)
    raw = np.array(raw)
    if raw.ndim == 2:          # (n_samples, n_features)
        return raw[0]
    if raw.ndim == 3:          # (n_classes, n_samples, n_features)
        if raw.shape[0] > 1:
            return raw[1][0]
        return raw[0][0]

    raise RuntimeError("Unexpected SHAP output shape: " + str(raw.shape))

# ---------- One-hot builder for payload (handles drop_first=True) ----------
def build_feature_row_from_payload(payload_features: Dict[str, Any]) -> pd.DataFrame:
    """
    Builds a single-row DataFrame ready for model.predict, matching feature_cols order.
    - Expands one-hot groups for dominant_emotion and dominant_entity (drop_first used in training).
    - Unknown categories are treated as base (all zeros).
    - Raises HTTPException if required numeric columns are missing or casting fails.
    """
    if feature_cols is None:
        raise HTTPException(status_code=503, detail="Server model not loaded")

    rf = payload_features.copy()  # working dict
    emo = None; score =  None
    if "dominant_emotion" in rf and "emotion_score" in rf:
        emo = str(rf["dominant_emotion"])
        score = float(rf["emotion_score"])


    # Positive emotion → make score negative (if not already)
    if emo in PEL:
        # If the user already gives a negative score, keep as-is
        # Else flip it to negative
        if score >= 0:
            rf["emotion_score"] = -abs(score)
        else:
            rf["emotion_score"] = score

    # Neutral emotion → force score to 0
    elif emo in Neutral_Emotions:
        rf["emotion_score"] = 0.0

    # find one-hot cols produced by pd.get_dummies(prefix='dominant_emotion'/'dominant_entity')
    emo_onehot_cols = [c for c in feature_cols if c.startswith("dominant_emotion_")]
    ent_onehot_cols = [c for c in feature_cols if c.startswith("dominant_entity_")]

    # zero all known one-hot columns (base will be all zeros)
    for c in emo_onehot_cols:
        rf.setdefault(c, 0)
    for c in ent_onehot_cols:
        rf.setdefault(c, 0)

    # set one-hot for emotion if provided and known
    if "dominant_emotion" in payload_features:
        cat = payload_features["dominant_emotion"]
        # ensure string and no weird chars
        if cat is not None:
            colname = f"dominant_emotion_{cat}"
            if colname in emo_onehot_cols:
                rf[colname] = 1
            else:
                # unseen or dropped/base category -> treat as base (all zeros)
                print(f"dominant_emotion '{cat}' not in one-hot cols; treating as base/unknown (all zeros).")

    # set one-hot for entity if provided and known
    if "dominant_entity" in payload_features:
        cat = payload_features["dominant_entity"]
        if cat is not None:
            colname = f"dominant_entity_{cat}"
            if colname in ent_onehot_cols:
                rf[colname] = 1
            else:
                print(f"dominant_entity '{cat}' not in one-hot cols; treating as base/unknown (all zeros).")

    # Verify all columns required by model are present in rf
    missing_after = [c for c in feature_cols if c not in rf]
    if missing_after:
        raise HTTPException(status_code=400, detail=f"Missing required features after preprocessing: {missing_after}")

    # Build DF in correct training order
    df_row = pd.DataFrame([rf])[feature_cols]

    # Cast to float (model expects numeric inputs). If any column is non-convertible, error out.
    try:
        df_row = df_row.astype(float)
    except Exception as e:
        # surface helpful error (which column likely failed)
        raise HTTPException(status_code=400, detail=f"Type error casting features to float: {str(e)}")

    return df_row

# ---------- Helper to construct response (SHAP + heuristics) ----------
def analyse_row(df_row: pd.DataFrame, raw_input: Dict[str, Any]) -> Dict[str, Any]:
    # Prediction & risk
    pred_label = int(model.predict(df_row)[0])
    prob = float(model.predict_proba(df_row)[0][1])  # P(class=1)

    # SHAP values (safe)
    vals = get_shap_vector_for_positive_class(explainer, df_row)
    pairs = list(zip(feature_cols, vals))
    pairs_sorted = sorted(pairs, key=lambda x: abs(x[1]), reverse=True)
    top_k = pairs_sorted[:5]

    top_features = []
    for feat, sv in top_k:
        val = float(df_row.iloc[0][feat])
        top_features.append({
            "feature": feat,
            "shap": float(np.round(sv, 6)),
            "reason": f"{feat} = {val}"
        })

    return {
        "date": str(datetime.date.today()),
        "risk_score": round(prob, 4),
        "prediction_label": pred_label,
        "top_features": top_features,
    }





#================ Recommendation utilities =================
#  Custom FM Layer (no KerasTensor errors)
class FMLayer(Layer):
    def call(self, inputs):
        """
        inputs shape: (batch, num_fields, emb_dim)
        """
        summed = K.sum(inputs, axis=1)             # (batch, emb_dim)
        summed_square = K.square(summed)

        squared = K.square(inputs)
        squared_sum = K.sum(squared, axis=1)

        fm_output = 0.5 * K.sum(summed_square - squared_sum, axis=1, keepdims=True)
        return fm_output

PREPROC_PATH = os.path.join(MODEL_DIR_REC, "preproc.joblib")
MODEL_PATH = os.path.join(MODEL_DIR_REC, "saved_model.keras")
def load_model_and_preproc():
    pre = joblib.load(PREPROC_PATH)
    mdl = tf.keras.models.load_model(MODEL_PATH, custom_objects={"FMLayer": FMLayer})
    return pre, mdl

def normalize_recommended_state(val):
    # training likely stored scalar strings. Handle lists robustly.
    # if pd.isna(val):
    #     return "unknown"
    if isinstance(val, list):
        return val[0] if len(val) > 0 else "unknown"   # PICK-FIRST heuristic
    if isinstance(val, (set, tuple)):
        return list(val)[0] if len(val) > 0 else "unknown"
    if isinstance(val, dict):
        return "unknown"
    # if it's already a string like "stress|anxious", keep it
    return str(val)

def build_candidate_table_from_user(user_row: dict, habit_catalog: pd.DataFrame):
    """
    user_row: dict or single-row DataFrame containing user features:
      risk_score,prediction,dominant_emotion,emotion_score,screen_time,unlocks,
      sleep_hours,steps_last_24h (names must match preproc)
    habit_catalog: DataFrame with habit columns:
      habit_id,category,difficulty,time_min,dopamine_level,recommended_for_state,
      indoor,required_device,popularity_prior
    returns: df where user features are repeated for each habit
    """
    # convert user_row to DataFrame (1,row) if needed
    if isinstance(user_row, dict):
        df_user = pd.DataFrame([user_row])
    else:
        df_user = user_row.copy().reset_index(drop=True)
    # normalize recommended_for_state in habit catalog and user if present
    if "recommended_for_state" in habit_catalog.columns:
        habit_catalog = habit_catalog.copy()
        habit_catalog["recommended_for_state"] = habit_catalog["recommended_for_state"].apply(normalize_recommended_state)
    # repeat user row for each habit
    n = len(habit_catalog)
    df_user_rep = pd.concat([df_user]*n, ignore_index=True)
    # concat user features and habit features side-by-side
    # ensure no column name collision: if both have same col (like 'date'/'user_id'), handle explicitly
    df = pd.concat([df_user_rep.reset_index(drop=True), habit_catalog.reset_index(drop=True)], axis=1)
    return df

def preprocess_candidates(df, pre):
    encs = pre["encoders"]
    scaler = pre["scaler"]
    cat_cols = pre["categorical_cols"]
    num_cols = pre["numeric_cols"]

    df = df.copy()

    # categorical
    for c in cat_cols:
        le = encs[c]
        df[c] = df[c].astype(str).fillna("unknown")
        # map using label encoder, unknown → first class
        df[c] = df[c].apply(
            lambda x: le.transform([x])[0] if x in le.classes_ else 0
        )

    # numeric
    if num_cols:
        for c in num_cols:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
        df[num_cols] = scaler.transform(df[num_cols])

    # convert to model inputs
    inp = {}
    for c in cat_cols:
        inp[f"inp_{c}"] = df[c].values.astype("int32")
    if num_cols:
        inp["numeric_input"] = df[num_cols].values.astype("float32")

    return inp, df

def recommend_for_user_snapshot(user_row, habit_catalog, top_positive=5):
    """
    user_row: dict or single-row DataFrame with user features (single snapshot)
    habit_catalog: DataFrame with habit rows
    returns: pos_df, neg_df containing habit_id and score
    """
    pre, mdl = load_model_and_preproc()

    # build candidate table
    df_cand = build_candidate_table_from_user(user_row, habit_catalog)

    # preprocess whole candidate set
    inp, df_proc = preprocess_candidates(df_cand, pre)

    # predict scores
    scores = mdl.predict(inp, batch_size=1024).ravel()
    df_proc["score"] = scores

    # sort & return top/bottom
    pos = df_proc.sort_values("score", ascending=False).head(top_positive)[["habit_id", "score"]].reset_index(drop=True)
    # neg = df_proc.sort_values("score", ascending=True).head(top_negative)[["habit_id", "score"]].reset_index(drop=True)
    return pos
print("\nDeepFM training complete.")





# Background task
def process_journal_pipeline(user_id: int, journal_id: int, payload: JournalIn, ner_outputs, top5_labels, top5_probs):
    """Runs in background: build feature row, run analysis, save HabitAnalysis,
       call recommend_for_user_snapshot, save HabitInteraction records.
       This function must manage its own DB session and exceptions.
    """
    db = SessionLocal()
    try:
        # 1) Build feature row (reuse your existing function)
        features = {
            "screen_time_mins": payload.screen_minutes,
            "unlock_counts": payload.unlock_count,
            "sleep_hours": payload.sleep_hours,
            "steps": payload.steps,
            "dominant_emotion": top5_labels[0] if top5_labels else "Neutral",
            "emotion_score": top5_probs[0] if top5_probs else 0.0,
            "dominant_entity": ner_outputs[0]["label"] if ner_outputs else "person",
            "dominant_entity_score": ner_outputs[0]["score"] if ner_outputs else 0.0,
            "wrote_journal_flag": 1,
            "weekend_flag": 1 if datetime.datetime.today().weekday() >=5 else 0
        }
        df_row = build_feature_row_from_payload(features)
        analysis_result = analyse_row(df_row, features)  # returns risk_score, label, top_features

        # 2) Save HabitAnalysis
        ha = HabitAnalysis(
            user_id=user_id,
            journal_id=journal_id,
            risk_score=analysis_result["risk_score"],
            prediction_label=str(analysis_result["prediction_label"]),
            top_features=analysis_result["top_features"]
        )
        db.add(ha)
        db.commit()
        db.refresh(ha)

        # 3)update journal row to mark analysis complete
        j = db.query(Journal).filter(Journal.journal_id == journal_id).first()
        if j:
            j.analysis_done = True   # add this boolean column to Journal model
            db.add(j)
            db.commit()

        # 3) Create user_snapshot dict — build from features + emotions + analysis
        user_snapshot = {
                "risk_score": analysis_result["risk_score"],
                "prediction": analysis_result["prediction_label"],
                "dominant_emotion": features["dominant_emotion"],
                "emotion_score": features["emotion_score"],
                "screen_time": features["screen_time_mins"],
                "unlocks": features["unlock_counts"],
                "sleep_hours": features["sleep_hours"],
                "steps_last_24h": features["steps"]
        }

        # 4) Generate recommendations
        catalog_path = os.path.join("Recommendation", "habit_catalog.json")
        habit_catalog = pd.read_json(catalog_path)
        pos_df = recommend_for_user_snapshot(user_snapshot, habit_catalog, top_positive=5)
        pos_list = pos_df.to_dict(orient="records")

        # 5) Save HabitInteraction for positive ones
        for item in pos_list:
            hi = HabitInteraction(
                user_id=user_id,
                journal_id=journal_id,
                analysis_id=ha.analysis_id,
                habit_id=int(item["habit_id"])
            )
            db.add(hi)
        db.commit()

        

    except Exception as e:
        # log error; optionally store failure reason in DB
        print("Background pipeline error:", e)
    finally:
        db.close()
    
    print(f"Background processing for journal_id={journal_id} complete.")




# ---------- API Endpoints ----------
@app.post("/auth/signup", response_model=AuthResponse)
def signup(payload: SignupPayload):
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == payload.email).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")

        password_hash = hash_password(payload.password)
        user = User(
            username=payload.name,
            email=payload.email,
            password_hash=password_hash
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user_to_response(user)
    finally:
        db.close()


@app.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginPayload):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == payload.email).first()
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return user_to_response(user)
    finally:
        db.close()


@app.post("/journal-analyse")
def analyse_journal(payload: JournalIn, background_tasks: BackgroundTasks):
    # First extract emotional data and entities from the text
    text = payload.text
    inputs = bert_tokenizer(text, return_tensors="pt")
    # Predict
    with torch.no_grad():
        bert_outputs = emotion_model(**inputs)
        ner_outputs = entity_model.predict_entities(text, entity_labels)
        probs = torch.sigmoid(bert_outputs.logits).squeeze(0)  # Convert logits to probabilities using sigmoid function and squeeze to only one dim
    # Get top 5 predictions(emotions)
    top5_indices = torch.argsort(probs, descending=True)[:5]  # Get indices of top 5 labels
    top5_labels = [emotion_labels[i] for i in top5_indices]
    top5_probs = [probs[i].item() for i in top5_indices] #convert probs to float

    emotions = {}
    for label, prob in zip(top5_labels, top5_probs):
        emotions[label] = prob

    #store in db
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == payload.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        j = Journal(
            user_id=payload.user_id,
            text=payload.text,
            screen_minutes=payload.screen_minutes,
            unlock_count=payload.unlock_count,
            sleep_hours=payload.sleep_hours,
            steps=payload.steps,
            dominant_emotion=top5_labels[0],
            dominant_emotion_score=top5_probs[0],
        )
        db.add(j)
        db.commit()
        db.refresh(j)
        journal_id = j.journal_id

  
    finally:
        db.close()
    
    # Launch background processing
    # schedule the pipeline - won't block the response
    background_tasks.add_task(process_journal_pipeline, payload.user_id, journal_id, payload, ner_outputs, top5_labels, top5_probs)
    message = "Journal received and is being processed"
    return {"message": message}


# @app.post("/analyse-day")
# def analyse_day(features_payload: FeaturesPayload, journal_id: int, user_id: int):
#     if model is None or feature_cols is None or explainer is None:
#         raise HTTPException(status_code=503, detail="Model not loaded")
#     if feature_cols is None:
#         raise HTTPException(status_code=503, detail="Feature columns not loaded")   
#     if explainer is None:   
#         raise HTTPException(status_code=503, detail="SHAP explainer not loaded")

#     db = SessionLocal()
#     df_row = build_feature_row_from_payload(features_payload.features)
#     analysis_result = analyse_row(df_row, features_payload.features)

#     # Store analysis result
#     ha = HabitAnalysis(
#         user_id=user_id,
#         journal_id=journal_id,
#         risk_score=analysis_result["risk_score"],
#         prediction_label=str(analysis_result["prediction_label"]),
#         top_features=analysis_result["top_features"]
#     )
#     db.add(ha)
#     db.commit()
#     db.refresh(ha)
#     result = {
#         "analysis_id": ha.analysis_id,
#         "risk_score": ha.risk_score,
#         "prediction_label": ha.prediction_label,
#         "top_features": ha.top_features
#     }
#     return result


# @app.post("/recommend-habits")
# def recommend_habits(user_id:int, journal_id:int, analysis_id:int, user_snapshot: Dict[str, Any]):
#     # load habit catalog
#     catalog_path = os.path.join("Recommendation", "habit_catalog.json")
#     if not os.path.exists(catalog_path):
#         raise HTTPException(status_code=500, detail="Habit catalog not found on server")
#     habit_catalog = pd.read_json(catalog_path)

#     # get recommendations
#     pos_df, neg_df = recommend_for_user_snapshot(user_snapshot, habit_catalog, top_positive=5, top_negative=5)

#     # convert to lists of dicts
#     pos_list = pos_df.to_dict(orient="records")
#     neg_list = neg_df.to_dict(orient="records")

#     db = SessionLocal()
#     result = ""
#     #saved = []
#     try:
#         for item in pos_list:
#             hid = int(item["habit_id"])
#             hi = HabitInteraction(
#                 user_id=user_id,
#                 journal_id=journal_id,
#                 analysis_id=analysis_id,
#                 habit_id=hid
#             )
#             db.add(hi)
#         db.commit()
#         db.refresh(hi)
#         result = f"Saved {len(pos_list)} recommended habits for user."
#     finally:
#         db.close()

#     return {
#         "positive_recommendations": pos_list,
#     }

        
           
