from database.db import SessionLocal
from database.models import UserStats

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