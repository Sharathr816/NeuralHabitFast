import numpy as np
from sqlalchemy.orm import Session
from typing import Dict, List

from database.db import SessionLocal
from database.models import Journal, HabitAnalysis


NEGATIVE_EMOTIONS = {
    "sadness","grief","anger","fear","nervousness",
    "remorse","disappointment","disgust","annoyance", "confusion"
}


def get_last_three_days(user_id: int, db: Session) -> List[dict]:
    """
    Fetch the latest 3 journal entries with their risk scores.
    """

    results = (
        db.query(
            Journal.journal_id,
            Journal.sleep_hours,
            Journal.screen_minutes,
            Journal.dominant_emotion,
            HabitAnalysis.risk_score
        )
        .join(HabitAnalysis, HabitAnalysis.journal_id == Journal.journal_id)
        .filter(Journal.user_id == user_id)
        .order_by(Journal.created_at.desc())
        .limit(3)
        .all()
    )

    print("Results:", results)
    print("Count:", len(results))

    if len(results) < 3:
        print(f"[SBII] Not enough data for user {user_id}. Found {len(results)} days.")
        return None

    data = []

    for r in results:
        data.append({
            "risk": float(r.risk_score),
            "sleep": float(r.sleep_hours),
            "screen": float(r.screen_minutes),
            "emotion": r.dominant_emotion.lower() if r.dominant_emotion else ""
        })

    return data[::-1]  # reverse so oldest -> newest


def compute_avg(values: List[float]) -> float:
    return float(np.mean(values))


def compute_variance(values: List[float]) -> float:
    return float(np.var(values))


def compute_sbii_features(user_id: int) -> Dict[str, float]:
    """
    Main feature generation function.
    Returns the 7 SBII features.
    """

    db = SessionLocal()

    try:

        data = get_last_three_days(user_id, db)
        if data is None:
            return None

        risks = [d["risk"] for d in data]
        sleeps = [d["sleep"] for d in data]
        screens = [d["screen"] for d in data]
        emotions = [d["emotion"] for d in data]

        # Feature 1
        avg_risk_3d = compute_avg(risks)

        # Feature 2
        risk_slope = risks[-1] - risks[0]

        # Feature 3
        sleep_avg_3d = compute_avg(sleeps)

        # Feature 4
        sleep_variance_3d = compute_variance(sleeps)

        # Feature 5
        screen_avg_3d = compute_avg(screens)

        # Feature 6
        screen_spike = screens[-1] - screen_avg_3d

        # Feature 7
        negative_emotion_count_3d = sum(
            1 for e in emotions if e in NEGATIVE_EMOTIONS
        )

        feature_vector = {
            "avg_risk_3d": avg_risk_3d,
            "risk_slope": risk_slope,
            "sleep_avg_3d": sleep_avg_3d,
            "sleep_variance_3d": sleep_variance_3d,
            "screen_avg_3d": screen_avg_3d,
            "screen_spike": screen_spike,
            "negative_emotion_count_3d": negative_emotion_count_3d
        }

        return feature_vector

    finally:
        db.close()