import datetime
from fastapi import APIRouter, HTTPException
from database.db import SessionLocal
from database.models import User, UserStats
from database.schema import SignupPayload, LoginPayload, AuthResponse
from services.auth_service import hash_password, verify_password, user_to_response


router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/signup", response_model=AuthResponse)
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

@router.post("/login", response_model=AuthResponse)
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