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
    daily_limit: Optional[float] = None
    weekly_limit: Optional[float] = None
    daily_usage: Optional[float] = None
    weekly_usage: Optional[float] = None
    role: Optional[str] = None
    unlimited_mode: Optional[str] = None
    unlimited_expires_at: Optional[str] = None


class UserRoleUpdate(BaseModel):
    role: Literal["Member", "Trusted", "Researcher", "Admin"]
    unlimited_mode: Literal["none", "temporary", "permanent"] = "none"
    unlimited_duration: Optional[Literal["1 day", "1 week", "1 month", "indefinite"]] = None


class RoleSettingItem(BaseModel):
    role: str
    allowed_models: List[str]
    allowed_tools: List[str]
    daily_limit: float
    weekly_limit: float


class RoleSettingsListResponse(BaseModel):
    settings: List[RoleSettingItem]


class RoleSettingsUpdateRequest(BaseModel):
    role: Literal["Member", "Trusted", "Researcher", "Admin"]
    allowed_models: List[str]
    allowed_tools: List[str]
    daily_limit: float
    weekly_limit: float


class UserUsageResponse(BaseModel):
    nebula_user_id: int
    daily_usage: float
    weekly_usage: float
    daily_limit: float
    weekly_limit: float
    role: str
    unlimited_mode: str
    unlimited_expires_at: Optional[str]


class UserLookupResponse(BaseModel):
    nebula_user_id: int
    username: str
    display_name: str
    role: str


class ModelConfigItem(BaseModel):
    model_id: str
    display_name: str
    allowed_roles: List[str]


class ModelConfigListResponse(BaseModel):
    models: List[ModelConfigItem]
