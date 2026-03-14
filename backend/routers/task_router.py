from fastapi import APIRouter
from fastapi import HTTPException
from database.db import SessionLocal
from database.models import UserTasks, UserStats
import datetime
from config_main import _to_utc_timestamp
from services.game_service import _award_xp_and_handle_level

router = APIRouter(prefix="/user", tags=["Tasks"])



@router.post("/tasks")
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


@router.get("/{user_id}/tasks")
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


@router.post("/tasks/{task_id}/complete")
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

@router.delete("/tasks/{task_id}")
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