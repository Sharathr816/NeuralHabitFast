from fastapi import APIRouter, HTTPException
from database.db import SessionLocal
from database.models import User, UserStats
import datetime

router = APIRouter(prefix="/user", tags=["Gamification"])


@router.get("/{user_id}/stats")
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


@router.post("/{user_id}/minigame/play_health_potion")
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