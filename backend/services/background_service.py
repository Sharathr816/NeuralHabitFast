from database.db import SessionLocal
from database.models import HabitAnalysis, Journal, HabitInteraction
import datetime
import os
import pandas as pd
from database.schema import JournalIn
from services.analysis_service import build_feature_row_from_payload, analyse_row
from services.recommendation_service import recommend_for_user_snapshot_live
from services.sbii_service import predict_sbii

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
        print("Feature row built for the model")
        analysis_result = analyse_row(df_row, features)  # returns risk_score, label, top_features
        print("Analysis done by the model")

        # 2) Save HabitAnalysis
        ha = HabitAnalysis(
            user_id=user_id,
            journal_id=journal_id,
            risk_score=analysis_result["risk_score"],
            prediction_label=str(analysis_result["prediction_label"]),
            top_features=analysis_result["top_features"],
            
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

        # Get SBII score
        try:
            sbii_score = predict_sbii(user_id)
            print("forecasting completed by the model successfully)")
        except Exception as e:
            print("SBII error:", e)
            sbii_score = None
        
        ha.sbii_score = sbii_score
        db.add(ha)
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