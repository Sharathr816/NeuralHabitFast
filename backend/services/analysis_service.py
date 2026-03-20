import datetime
import pandas as pd
import numpy as np

from typing import Dict, Any
from fastapi import HTTPException

# import dependencies
# from Analysis.utils import PEL, Neutral_Emotions
import dependencies
from Analysis.utils import PEL, Neutral_Emotions


def build_feature_row_from_payload(payload_features: Dict[str, Any]) -> pd.DataFrame:
    """
    Builds a single-row DataFrame ready for model.predict, matching feature_cols order.
    - Expands one-hot groups for dominant_emotion and dominant_entity (drop_first used in training).
    - Unknown categories are treated as base (all zeros).
    - Raises HTTPException if required numeric columns are missing or casting fails.
    """
    feature_cols = dependencies.feature_cols
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

def analyse_row(df_row: pd.DataFrame, raw_input: Dict[str, Any]) -> Dict[str, Any]:
    # Prediction & risk
    model = dependencies.model
    pred_label = int(model.predict(df_row)[0])
    prob = float(model.predict_proba(df_row)[0][1])  # P(class=1)

    # SHAP values (safe)
    vals = get_shap_vector_for_positive_class(dependencies.explainer, df_row)
    pairs = list(zip(dependencies.feature_cols, vals))
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