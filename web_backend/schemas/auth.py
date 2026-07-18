"""Pydantic schemas for /auth/* routes."""
from typing import Optional

from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=8)
    display_name: Optional[str] = None
    bootstrap_key: Optional[str] = None


class SignupResponse(BaseModel):
    nebula_user_id: int
    username: str
    is_approved: bool
    became_admin: bool
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    nebula_user_id: int
    username: str
    is_approved: bool
    is_admin: bool
    access_token: str
    token_type: str = "bearer"


class BootstrapStatusResponse(BaseModel):
    """Backs the frontend's "hide the admin checkbox if bootstrap is
    already claimed" requirement -- a tiny public (no-auth) endpoint
    the signup page checks before rendering the checkbox, rather than
    letting a stale/incorrect bootstrap_key fail silently at submit
    time."""
    bootstrap_available: bool
