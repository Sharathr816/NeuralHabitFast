import os
import joblib
import numpy as np
import pandas as pd
import tensorflow as tf

from tensorflow.keras import layers, Model, Input
from tensorflow.keras.layers import Layer

from config_main import MODEL_DIR_REC

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

def build_candidates(user_row: dict, catalog_df: pd.DataFrame):
    # repeated user row per habit (exactly like training)
    if isinstance(user_row, dict):
        df_user = pd.DataFrame([user_row])
    else:
        df_user = user_row.copy().reset_index(drop=True)
    df_user_rep = pd.concat([df_user] * len(catalog_df), ignore_index=True)
    return pd.concat([df_user_rep.reset_index(drop=True), catalog_df.reset_index(drop=True)], axis=1)

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
