import os
import sys
import joblib
import shap
import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from database.db import engine
from database.models import Base

from config_main import MODELS_DIR, MODEL_FILENAME, FEATURE_COLS_FILENAME

from sqlalchemy import text

from routers.auth_router import router as auth_router
from routers.pipeline_router import router as journal_router
from routers.habit_router import router as habit_router
from routers.gamification_router import router as gamification_router
from routers.task_router import router as task_router
from routers.coach_router import router as coach_router

app = FastAPI()

app.include_router(auth_router)
app.include_router(habit_router)
app.include_router(gamification_router)
app.include_router(task_router)
app.include_router(journal_router)
app.include_router(coach_router)


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


# called after all imports(includes routers as well) are done
@app.on_event("startup")
def load_artifacts():
    import dependencies  # ensure we import the module where these globals are defined
    analysis_model_path = os.path.join(MODELS_DIR, MODEL_FILENAME)
    cols_path = os.path.join(MODELS_DIR, FEATURE_COLS_FILENAME)

    if not os.path.exists(analysis_model_path) or not os.path.exists(cols_path):
        raise RuntimeError(f"Model or feature_cols not found in {MODELS_DIR}/. Expect files: {MODEL_FILENAME}, {FEATURE_COLS_FILENAME}")

    dependencies.model = joblib.load(analysis_model_path)
    dependencies.feature_cols = joblib.load(cols_path)  # MUST be list of column names in training order
    # build SHAP explainer once (fast-ish for trees)
    dependencies.explainer = shap.TreeExplainer(dependencies.model)
    print(f"Loaded model and feature_cols ({len(dependencies.feature_cols)} cols). SHAP explainer ready.")


# ========== User authentication utilities ==========
# Done in auth_router.py for separation of concerns.

# ========== Analysis utilities ==========
# Done in pipeline_router.py for separation of concerns.

#=========== Recommendation utilities =================
# Done in pipeline_router.py for separation of concerns.

#============Gamification utilities====================
# ----- Helper: award XP and handle level-up -----
# Done in habit_router.py to reuse for both habits and mini-game plays, ensuring consistent level-up logic and XP handling.


#================ Background processing pipeline =================
# Done in pipeline_router.py for separation of concerns.



# ---------- API Endpoints ----------
# ---------- Auth endpoints ----------
# Done in auth_router.py for separation of concerns

# ------ Habit endpoints ------
# Done in habit_router.py for separation of concerns.

# ------ Task endpoints ------
# Done in task_router.py for separation of concerns.

# ------ Gamification endpoints ------
# Done in gamification_router.py for separation of concerns.

# ------ Journal analysis endpoint ------
# Done in pipeline_router.py for separation of concerns.

#------ Coach chat endpoints ------
# Done in coach_router.py for separation of concerns.



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

        
           
