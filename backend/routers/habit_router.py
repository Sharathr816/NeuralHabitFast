from fastapi import APIRouter, HTTPException
from database.db import SessionLocal
from database.models import UserHabit, UserStats
from services.game_service import _award_xp_and_handle_level


router = APIRouter(prefix="/user", tags=["Habits"])


@router.post("/habits")
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


@router.get("/{user_id}/habits")
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


@router.delete("/habits/{habit_id}")
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


@router.post("/habits/{habit_id}/check")
def check_user_habit(habit_id: int, payload: dict):
    print("CHECK ENDPOINT HIT", habit_id)
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

