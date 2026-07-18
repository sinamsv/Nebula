"""Pydantic schemas for /admin/* and /users/*/coins routes."""
from typing import List, Literal, Optional

from pydantic import BaseModel


class PendingUser(BaseModel):
    nebula_user_id: int
    username: str
    display_name: str
    created_at: str


class PendingUsersResponse(BaseModel):
    pending: List[PendingUser]


class ReviewUserRequest(BaseModel):
    """Confirmed shape: a single combined review endpoint, not separate
    approve/reject endpoints. status is a closed set of exactly two
    values -- anything else is a 422 from FastAPI's own validation
    before the route body even runs."""
    status: Literal["approved", "rejected"]


class ReviewUserResponse(BaseModel):
    nebula_user_id: int
    username: str
    approved: bool


class PlatformInfo(BaseModel):
    id: str
    name: str
    supports_guild_moderation: bool


class PlatformsResponse(BaseModel):
    platforms: List[PlatformInfo]


class CoinStatusResponse(BaseModel):
    balance: int
    seconds_until_reset: int


class ModifyCoinsRequest(BaseModel):
    amount: int
    mode: Literal["add", "set"] = "add"


class ModifyCoinsResponse(BaseModel):
    nebula_user_id: int
    new_balance: int
