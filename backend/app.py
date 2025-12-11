import torch
import os,sys
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
from models import (
    Base,
    Journal,
    User,
    HabitAnalysis,
    HabitInteraction,
    UserHabit,
    UserTasks,
    UserStats,
)
from schema import JournalIn, JournalResponse
from config_main import emotion_labels, entity_labels, emotion_model, entity_model, bert_tokenizer
from config_main import  MODELS_DIR, MODEL_FILENAME, FEATURE_COLS_FILENAME, MODEL_DIR_REC    
from Analysis.utils import NEL, PEL, Neutral_Emotions
from typing import List, Dict, Any
from schema import FeaturesPayload, SignupPayload, LoginPayload, AuthResponse, ChatRequest, ChatResponse
from pydantic import EmailStr, Field, BaseModel
import tensorflow as tf
from tensorflow.keras import layers, Model, Input
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
import keras.ops as K
from tensorflow.keras.layers import Layer
from fastapi.middleware.cors import CORSMiddleware
import sys
from pathlib import Path
from Coach.bot import RAGChatbot
from sqlalchemy import text

chatbot = RAGChatbot() 

app = FastAPI()


# DEV: allow your frontend origin. For quick testing you can use ["*"], but DON'T use that in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#only creates tables IF they don’t already exist.
Base.metadata.create_all(bind=engine)

# Ensure DB has newer columns added to models (safe-online migration for simple cases)
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE userstats ADD COLUMN IF NOT EXISTS minigame_plays_today INTEGER DEFAULT 0"))
        # ensure new per-level minigame columns exist
        conn.execute(text("ALTER TABLE userstats ADD COLUMN IF NOT EXISTS minigame_plays_for_level INTEGER DEFAULT 0"))
        conn.execute(text("ALTER TABLE userstats ADD COLUMN IF NOT EXISTS minigame_level_ref INTEGER"))
        # ensure userhabit has a deleted flag for soft-deletes
        conn.execute(text("ALTER TABLE userhabit ADD COLUMN IF NOT EXISTS deleted BOOLEAN DEFAULT FALSE"))
except Exception as e:
    print("Warning: failed to ensure userstats.minigame_plays_today column exists:", e)

# for habit coach
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "."))  
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)



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


# Helper: normalize datetimes to UTC timestamps for safe comparisons
def _to_utc_timestamp(dt: datetime.datetime) -> float:
    if dt is None:
        return None
    if dt.tzinfo is None:
        # treat naive datetimes as UTC for comparison purposes
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc).timestamp()

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
    Returns a 1-D numpy array of SHAP values aligned to feature_cols for the positive class (class=1).
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
        summed = tf.reduce_sum(inputs, axis=1)
        summed_square = tf.square(summed)
        squared = tf.square(inputs)
        squared_sum = tf.reduce_sum(squared, axis=1)
        return 0.5 * tf.reduce_sum(summed_square - squared_sum, axis=1, keepdims=True)


PREPROC_PATH = os.path.join(MODEL_DIR_REC, "preproc.joblib")
MODEL_PATH = os.path.join(MODEL_DIR_REC, "model.keras")
_model = None
_preproc = None
def load_model_and_preproc_once():
    global _model, _preproc
    if _preproc is None or _model is None:
        _preproc = joblib.load(PREPROC_PATH)
        _model = tf.keras.models.load_model(MODEL_PATH, custom_objects={"FMLayer": FMLayer})
    return _preproc, _model

# call on import/startup
try:
    _preproc, _model = load_model_and_preproc_once()
    print("Loaded preproc and model at startup")
except Exception as e:
    print("Warning: failed to load model at startup:", e)
    _preproc, _model = None, None

def safe_map_series(series, le):
    """Map a Python series/list -> encoded int array using LabelEncoder `le`.
       If value unseen, map to 'unknown' class index if present, else 0."""
    classes = le.classes_
    has_unknown = "unknown" in classes
    out = []
    # convert classes dtype to string for robust comparison
    classes_set = set([str(x) for x in classes])
    for v in series:
        v_s = str(v)
        if v_s in classes_set:
            try:
                out.append(int(le.transform([v_s])[0]))
            except Exception:
                out.append(0)
        else:
            if has_unknown:
                out.append(int(np.where(classes == "unknown")[0][0]))
            else:
                out.append(0)
    return np.array(out, dtype="int32")


def build_candidates(user_row: dict, catalog_df: pd.DataFrame):
    # repeated user row per habit (exactly like training)
    if isinstance(user_row, dict):
        df_user = pd.DataFrame([user_row])
    else:
        df_user = user_row.copy().reset_index(drop=True)
    df_user_rep = pd.concat([df_user] * len(catalog_df), ignore_index=True)
    return pd.concat([df_user_rep.reset_index(drop=True), catalog_df.reset_index(drop=True)], axis=1)


def preprocess_inf(df_rows: pd.DataFrame, pre):
    encs = pre["encoders"]
    scaler = pre.get("scaler", None)
    cat_cols = pre["categorical_cols"]
    num_cols = pre["numeric_cols"]

    dfp = df_rows.copy()

    # ensure expected cols exist
    for c in cat_cols:
        if c not in dfp.columns:
            dfp[c] = "unknown"
    for n in num_cols:
        if n not in dfp.columns:
            dfp[n] = 0.0

    # categorical -> label encoded using training encoders
    for c in cat_cols:
        le = encs[c]
        # ensure string-typed, fillna
        dfp[c] = dfp[c].astype(str).fillna("unknown")
        dfp[c] = safe_map_series(dfp[c].tolist(), le)

    # numeric -> scaler
    if num_cols and scaler is not None:
        for c in num_cols:
            dfp[c] = pd.to_numeric(dfp[c], errors="coerce").fillna(0.0)
        dfp[num_cols] = scaler.transform(dfp[num_cols])

    # convert to model inputs
    inp = {}
    for c in cat_cols:
        inp[f"inp_{c}"] = dfp[c].astype("int32").values
    if num_cols:
        inp["numeric_input"] = dfp[num_cols].astype("float32").values

    return inp, dfp



def recommend_for_user_snapshot_live(user_row: dict, habit_catalog: pd.DataFrame, top_k: int = 5):
    global _preproc, _model, _model_lock
    if _preproc is None or _model is None:
        raise RuntimeError("Model/preproc not loaded")

    # build candidate table
    df_cand = build_candidates(user_row, habit_catalog)

    # preprocess inputs
    inp, df_proc = preprocess_inf(df_cand, _preproc)

    # model prediction
    scores = _model.predict(inp, batch_size=512).ravel()

    df_proc["score"] = scores

    # optionally combine heuristic score if catalog has it — small weight
    if "heuristic_score" in df_proc.columns:
        df_proc["score"] = df_proc["score"] + 0.12 * df_proc["heuristic_score"].fillna(0.0)

    # sort and return decoded habit ids + metadata
    df_sorted = df_proc.sort_values("score", ascending=False).reset_index(drop=True)

    # decode habit_id original if encoder present
    habit_le = _preproc["encoders"].get("habit_id", None)
    if habit_le is not None:
        # careful: habit_id currently numeric in catalog; the encoder maps strings used in training; cast accordingly
        try:
            df_sorted["habit_id_original"] = habit_le.inverse_transform(df_sorted["habit_id"].astype(int))
        except Exception:
            # fallback: if the encoder used string habit ids, try mapping as str
            df_sorted["habit_id_original"] = df_sorted["habit_id"].astype(str)

    # select top_k with extra fields for UI
    out_df = df_sorted.head(top_k)[["habit_id_original", "score", "category", "difficulty", "time_min"]].copy()
    return out_df


#========================Gamification utilities========================
# ----- Helper: award XP and handle level-up -----
def _award_xp_and_handle_level(db, user_id: int, xp_amount: int):
    stats = db.query(UserStats).filter(UserStats.user_id == user_id).with_for_update().first()
    if not stats:
        # create if missing
        stats = UserStats(user_id=user_id, level=1, xp=0, hp=100, played_health_potion_minigame=False, current_streak=0)
        db.add(stats)
        db.flush()

    stats.xp = (stats.xp or 0) + int(xp_amount)
    # simple level-up rule: 200 xp per level
    while stats.xp >= stats.level * 200:
        stats.xp -= stats.level * 200
        stats.level += 1
    db.add(stats)
    return stats



#================ Background processing pipeline =================
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
                "dominant_emotion": features["dominant_emotion"].lower(),
                "emotion_score": features["emotion_score"],
                "screen_time": features["screen_time_mins"],
                "unlocks": features["unlock_counts"],
                "sleep_hours": features["sleep_hours"],
                "steps_last_24h": features["steps"]
        }

        # 4) Generate recommendations
        catalog_path = os.path.join("Recommendation", "habit_catalog_clean.json")
        habit_catalog = pd.read_json(catalog_path)
        pos_df = recommend_for_user_snapshot_live(user_snapshot, habit_catalog, top_k=5)
        pos_list = pos_df.to_dict(orient="records")


        # 5) Save HabitInteraction for positive ones
        for item in pos_list:
            hi = HabitInteraction(
                user_id=user_id,
                journal_id=journal_id,
                analysis_id=ha.analysis_id,
                habit_id=int(item["habit_id_original"])
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
        # create initial gamification/stats row for user
        stats = UserStats(user_id=user.user_id, level=1, xp=0, hp=100, played_health_potion_minigame=False, current_streak=0)
        db.add(stats)
        db.commit()
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
        # set last_login for per-login rules
        user.last_login = datetime.datetime.utcnow()
        db.add(user)
        # reset per-login play flag so user can play minigame once per login
        stats = db.query(UserStats).filter(UserStats.user_id == user.user_id).first()
        if stats:
            # reset play flag
            stats.played_health_potion_minigame = False
            # award a small login health bonus (+10 HP) — only on explicit login
            try:
                old_hp = stats.hp or 0
                stats.hp = min(100, old_hp + 10)
            except Exception:
                stats.hp = stats.hp or 0
            db.add(stats)
        db.commit()
        return user_to_response(user)
    finally:
        db.close()


# ------ Habit endpoints ------
@app.post("/user/habits")
def create_user_habit(payload: dict):
    user_id = payload.get("user_id")
    habit_name = payload.get("habit_name")
    category = payload.get("category")
    number_of_days = payload.get("number_of_days", 0)
    habit_type = payload.get("habit_type", "positive")
    if not user_id or not habit_name:
        raise HTTPException(status_code=400, detail="user_id and habit_name required")
    db = SessionLocal()
    try:
        h = UserHabit(user_id=user_id, habit_name=habit_name, category=category, number_of_days=number_of_days, habit_type=habit_type)
        db.add(h)
        db.commit()
        db.refresh(h)
        return {"status": "ok", "habit_id": h.id}
    finally:
        db.close()


@app.get("/user/{user_id}/habits")
def list_user_habits(user_id: int):
    db = SessionLocal()
    try:
        # Exclude soft-deleted habits
        rows = db.query(UserHabit).filter(UserHabit.user_id == user_id, UserHabit.deleted == False).all()
        out = []
        for r in rows:
            out.append({
                "id": r.id,
                "habit_name": r.habit_name,
                "category": r.category,
                "number_of_days": r.number_of_days,
                "habit_type": r.habit_type,
                "is_checked": bool(r.is_checked),
            })
        return {"habits": out}
    finally:
        db.close()


@app.delete("/user/habits/{habit_id}")
def delete_user_habit(habit_id: int):
    """Soft-delete a user habit so it does not reappear after reload/login."""
    db = SessionLocal()
    try:
        h = db.query(UserHabit).filter(UserHabit.id == habit_id).first()
        if not h:
            raise HTTPException(status_code=404, detail="Habit not found")
        # mark deleted so it remains hidden for this user
        h.deleted = True
        db.add(h)
        db.commit()
        return {"status": "ok", "habit_id": habit_id}
    finally:
        db.close()


@app.post("/user/habits/{habit_id}/check")
def check_user_habit(habit_id: int, payload: dict):
    checked = payload.get("checked", True)
    db = SessionLocal()
    try:
        h = db.query(UserHabit).filter(UserHabit.id == habit_id).first()
        if not h:
            raise HTTPException(status_code=404, detail="Habit not found")
        # Only apply changes on a state transition (unchecked -> checked or checked -> unchecked)
        prev_checked = bool(h.is_checked)
        xp_award = 0
        hp_delta = 0
        stats = None

        if checked and not prev_checked:
            # Transition: now checked
            if h.habit_type == "positive":
                xp_award = 25
                stats = _award_xp_and_handle_level(db, h.user_id, xp_award)
            else:
                stats = db.query(UserStats).filter(UserStats.user_id == h.user_id).first()
                if stats:
                    old_hp = stats.hp or 0
                    stats.hp = max(0, old_hp - 10)
                    hp_delta = (stats.hp - old_hp)
                    db.add(stats)
        else:
            if not checked and prev_checked:
                # Transition: now unchecked -> reverse previous effect
                if h.habit_type == "positive":
                    # remove previously awarded XP
                    stats = db.query(UserStats).filter(UserStats.user_id == h.user_id).first()
                    if stats:
                        old_xp = stats.xp or 0
                        stats.xp = max(0, old_xp - 25)
                        db.add(stats)
                        xp_award = -25
                else:
                    stats = db.query(UserStats).filter(UserStats.user_id == h.user_id).first()
                    if stats:
                        old_hp = stats.hp or 0
                        stats.hp = min(100, old_hp + 10)
                        hp_delta = (stats.hp - old_hp)
                        db.add(stats)

        # persist new checked state
        h.is_checked = bool(checked)
        db.add(h)
        db.commit()

        if stats is None:
            stats = db.query(UserStats).filter(UserStats.user_id == h.user_id).first()
        resp = {"status": "ok", "xp_awarded": xp_award, "hp_delta": hp_delta}
        if stats:
            resp.update({"level": stats.level, "xp": stats.xp, "hp": stats.hp, "streaks": stats.current_streak})
        return resp
    finally:
        db.close()

@app.delete("/user/tasks/{task_id}")
def delete_user_task(task_id: int):
        db = SessionLocal()
        try:
            t = db.query(UserTasks).filter(UserTasks.id == task_id).first()
            if not t:
                raise HTTPException(status_code=404, detail="Task not found")
            db.delete(t)
            db.commit()
            return {"status": "ok", "task_id": task_id}
        finally:
            db.close()


# ------ Task endpoints ------
@app.post("/user/tasks")
def create_user_task(payload: dict):
    user_id = payload.get("user_id")
    title = payload.get("title")
    deadline = payload.get("deadline")  # expect ISO string
    if not user_id or not title:
        raise HTTPException(status_code=400, detail="user_id and title required")
    db = SessionLocal()
    try:
        dt = None
        if deadline:
            try:
                dt = datetime.datetime.fromisoformat(deadline)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid deadline format; use ISO format")
        t = UserTasks(user_id=user_id, title=title, deadline=dt)
        db.add(t)
        db.commit()
        db.refresh(t)
        return {"status": "ok", "task_id": t.id}
    finally:
        db.close()


@app.get("/user/{user_id}/tasks")
def list_user_tasks(user_id: int):
    db = SessionLocal()
    try:
        rows = db.query(UserTasks).filter(UserTasks.user_id == user_id).all()
        out = []
        for r in rows:
            out.append({
                "id": r.id,
                "title": r.title,
                "deadline": r.deadline.isoformat() if r.deadline else None,
                "completed": bool(r.completed),
            })
        return {"tasks": out}
    finally:
        db.close()


@app.post("/user/tasks/{task_id}/complete")
def complete_user_task(task_id: int):
    db = SessionLocal()
    try:
        t = db.query(UserTasks).filter(UserTasks.id == task_id).first()
        if not t:
            raise HTTPException(status_code=404, detail="Task not found")
        now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        xp_award = 0
        hp_delta = 0
        stats = None

        if t.deadline:
            try:
                dl_ts = _to_utc_timestamp(t.deadline)
            except Exception:
                dl_ts = None
        else:
            dl_ts = None

        # if deadline exists and now > deadline => missed -> reduce hp
        if dl_ts is not None and now_ts > dl_ts:
            stats = db.query(UserStats).filter(UserStats.user_id == t.user_id).first()
            if stats:
                old_hp = stats.hp or 0
                stats.hp = max(0, old_hp - 10)
                hp_delta = (stats.hp - old_hp)
                db.add(stats)
        else:
            # award xp for completing before deadline — match frontend task XP
            xp_award = 20
            stats = _award_xp_and_handle_level(db, t.user_id, xp_award)

        t.completed = True
        db.add(t)
        db.commit()

        if stats is None:
            stats = db.query(UserStats).filter(UserStats.user_id == t.user_id).first()
        resp = {"status": "ok", "xp_awarded": xp_award, "hp_delta": hp_delta}
        if stats:
            resp.update({"level": stats.level, "xp": stats.xp, "hp": stats.hp, "streaks": stats.current_streak})
        return resp
    finally:
        db.close()


# ------ Gamification endpoints ------
@app.get("/user/{user_id}/stats")
def get_user_stats(user_id: int):
    db = SessionLocal()
    try:
        stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
        if not stats:
            # create default
            stats = UserStats(user_id=user_id, level=1, xp=0, hp=100, played_health_potion_minigame=False, current_streak=0)
            db.add(stats)
            db.commit()
            db.refresh(stats)
        return {
            "level": stats.level, 
            "xp": stats.xp,
            "hp": stats.hp,
            "played_health_potion_minigame": bool(stats.played_health_potion_minigame),
            # per-level minigame counters so frontend can disable the game when limit reached
            "minigame_plays_for_level": int(stats.minigame_plays_for_level or 0),
            "minigame_level_ref": int(stats.minigame_level_ref) if stats.minigame_level_ref is not None else None,
            # keep response key 'streaks' for backwards compatibility
            "streaks": stats.current_streak,
        }
    finally:
        db.close()


@app.post("/user/{user_id}/minigame/play_health_potion")
def play_health_potion(user_id: int, payload: dict):
    """Record a mini-game play. Payload includes {'won': bool}.
    Awards +10 HP for a win, up to 3 plays per calendar day. Returns updated stats and play count.
    """
    won = bool(payload.get("won", False))
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        stats = db.query(UserStats).filter(UserStats.user_id == user_id).with_for_update().first()
        if not stats:
            stats = UserStats(user_id=user_id, level=1, xp=0, hp=100, played_health_potion_minigame=False, current_streak=0, minigame_plays_today=0)
            db.add(stats)
            db.flush()

        # Per-level play limit: if user's recorded level ref differs from current level, reset counter
        current_level = stats.level or 1
        if stats.minigame_level_ref != current_level:
            stats.minigame_plays_for_level = 0
            stats.minigame_level_ref = current_level

        MAX_PLAYS_PER_LEVEL = 3
        if (stats.minigame_plays_for_level or 0) >= MAX_PLAYS_PER_LEVEL:
            raise HTTPException(status_code=400, detail="Mini-game play limit reached for current level")

        # increment per-level play count
        stats.minigame_plays_for_level = (stats.minigame_plays_for_level or 0) + 1
        # update last play timestamp
        stats.last_minigame_play_at = datetime.datetime.utcnow()

        hp_delta = 0
        xp_delta = 0
        if won:
            old_hp = stats.hp or 0
            stats.hp = min(100, old_hp + 10)
            hp_delta = stats.hp - old_hp

        db.add(stats)
        db.commit()

        return {
            "status": "ok",
            "won": won,
            "hp_delta": hp_delta,
            "minigame_plays_for_level": stats.minigame_plays_for_level,
            "minigame_level_ref": stats.minigame_level_ref,
            "level": stats.level,
            "xp": stats.xp,
            "hp": stats.hp,
            "streaks": stats.current_streak,
        }
    finally:
        db.close()


# ------ Journal analysis endpoint ------
@app.post("/journal-analyse", response_model=JournalResponse)
def analyse_journal(payload: JournalIn, background_tasks: BackgroundTasks):
    text = payload.text
    # run you NLP prediction logic (your snippet)
    inputs = bert_tokenizer(text, return_tensors="pt") 
    with torch.no_grad():
        bert_outputs = emotion_model(**inputs)
        ner_outputs = entity_model.predict_entities(text, entity_labels)
        probs = torch.sigmoid(bert_outputs.logits).squeeze(0)

    top5_indices = torch.argsort(probs, descending=True)[:5]
    top5_labels = [emotion_labels[i] for i in top5_indices]
    top5_probs = [probs[i].item() for i in top5_indices]

    emotions = {label: prob for label, prob in zip(top5_labels, top5_probs)}

    db: Session = SessionLocal()
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
            dominant_emotion=top5_labels[0] if top5_labels else None,
            dominant_emotion_score=top5_probs[0] if top5_probs else None,
        )
        db.add(j)
        db.commit()
        db.refresh(j)
        journal_id = j.journal_id
    finally:
        db.close()

    # schedule background processing without blocking
    background_tasks.add_task(
        process_journal_pipeline,
        payload.user_id,
        journal_id,
        payload,
        ner_outputs,
        top5_labels,
        top5_probs
    )

    return JournalResponse(message="Journal received and processing started, say hi to coach to see your recommended habits!", journal_id=journal_id)


@app.get("/coach/ping")
async def ping():
    return {"status": "ok", "detail": "coach API up"}


#------ Coach chat endpoints ------
@app.post("/coach/chat", response_model=ChatResponse)
async def coach_chat(req: ChatRequest):
    try:
        result = chatbot.chat(req.session_id, req.message)  # result can be dict or ChatResponse
        # if chatbot.chat returns dict already, ensure keys are answer & history
        if isinstance(result, dict):
            # normalize keys if needed (support older return)
            answer = result.get("answer") or result.get("reply") or ""
            history = result.get("history", [])
            return ChatResponse(answer=answer, history=history)
        # If it's already a ChatResponse instance, just return it
        return result
    except Exception as e:
        #logger.exception("Error in /coach/chat")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/coach/history")
async def coach_history(session_id: str):
    try:
        history = chatbot.get_session_history(session_id)  # your existing method
        # convert to simple dicts
        serialized = []
        for m in history.messages:
            role = getattr(m, "role", getattr(m, "author", "assistant"))
            text = getattr(m, "text", getattr(m, "content", ""))
            ts = getattr(m, "ts", None)
            serialized.append({"role": role, "text": text, "ts": ts})
        return {"history": [ chatbot._serialize_message(m) for m in history.messages ]}

    except Exception as e:
        # logger.exception("Error in /coach/history")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/coach/clear_history")
async def clear_history(payload: dict):
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    try:
        history = chatbot.get_session_history(session_id)
        chatbot.last_seen_analysis = {}  # reset any analysis cache
        # If the history object has a method to clear messages:
        if hasattr(history, 'clear') and callable(history.clear):
            history.clear()
        elif hasattr(history, 'delete_all') and callable(history.delete_all):
            history.delete_all()
        else:
            # fallback to explicit SQL deletion (see Option B)
            raise RuntimeError("No clear method on history object")

        return {"status": "cleared"}
    except Exception as e:
        print("Error clearing history")
        raise HTTPException(status_code=500, detail=str(e))



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

        
           
