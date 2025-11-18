from pydantic import BaseModel
from typing import Dict, Any

# for journal entry payload
class JournalIn(BaseModel):
    user_id: int
    text: str
    screen_minutes: int | None = None
    unlock_count: int | None = None
    sleep_hours: float | None = None
    steps: int | None = None

# for analysis payload
class FeaturesPayload(BaseModel):
    features: Dict[str, Any]