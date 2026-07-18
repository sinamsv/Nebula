"""Pydantic schemas for /sync/{platform} route."""
from pydantic import BaseModel


class SyncCodeResponse(BaseModel):
    code: str
    target_platform: str
    expiry_minutes: int
    verify_command_hint: str
