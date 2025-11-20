from pydantic import BaseModel
from typing import Dict, Any
import datetime
from pydantic import EmailStr, Field

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

# for user authentication payloads
class SignupPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=512)

class LoginPayload(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=512)

class AuthResponse(BaseModel):
    user_id: int
    name: str
    email: EmailStr
    signup_date: datetime.datetime