"""Trusted request context derived from a verified SaaS delegation token."""

from datetime import datetime
from typing import FrozenSet, Optional, Tuple
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SaaSRequestContext(BaseModel):
    """Immutable authorization and data-scope context for one AI request."""

    model_config = ConfigDict(frozen=True)

    user_id: UUID
    org_id: UUID
    role: str = Field(min_length=1, max_length=64)
    allowed_location_ids: Tuple[UUID, ...] = ()
    selected_location_id: Optional[UUID] = None
    permissions: FrozenSet[str] = frozenset()
    features: FrozenSet[str] = frozenset()
    locale: str = Field(default="en-BD", min_length=2, max_length=16)
    timezone: str = Field(default="Asia/Dhaka", min_length=1, max_length=64)
    request_id: str = Field(min_length=1, max_length=128)
    token_id: str = Field(min_length=1, max_length=128)
    issued_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def selected_location_must_be_allowed(self) -> "SaaSRequestContext":
        if (
            self.selected_location_id is not None
            and self.selected_location_id not in self.allowed_location_ids
        ):
            raise ValueError("selected location is outside the delegated location scope")
        return self

    def has_any_feature(self, *feature_names: str) -> bool:
        return any(name in self.features for name in feature_names)

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

