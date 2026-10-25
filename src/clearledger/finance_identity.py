"""Trusted identity port; never promote local bearer tokens or actor labels."""

import hashlib
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, Protocol
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

Permission = Literal[
    "FINANCE_READ",
    "PROPOSE",
    "REVIEW_SOURCES",
    "REVIEW_POLICY",
    "REVIEW_TAX_POLICY",
    "APPROVE",
    "SIMULATE_POST",
    "REVIEW_READ",
    "REVIEW_WORK",
    "REVIEW_CONTROL",
]


class Principal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    issuer: Annotated[str, Field(pattern=r"^[A-Za-z0-9_.:/-]{1,100}$")]
    subject: UUID
    organization_id: UUID
    authorization_version: Annotated[str, Field(pattern=r"^[A-Za-z0-9_.:-]{1,100}$")]
    permissions: frozenset[Permission]
    service: bool = False
    authenticated_at: datetime
    expires_at: datetime

    @property
    def identity(self) -> str:
        return "finance:" + hashlib.sha256(f"{self.issuer}:{self.subject}".encode()).hexdigest()

    def require(self, permission: Permission, organization_id: UUID) -> None:
        now = datetime.now(UTC)
        if (
            self.organization_id != organization_id
            or self.authenticated_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.authenticated_at <= now < self.expires_at
        ):
            raise HTTPException(403, "FINANCE_IDENTITY_INVALID")
        if permission not in self.permissions:
            raise HTTPException(403, "FINANCE_PERMISSION_REQUIRED")
        if (permission == "SIMULATE_POST") != self.service and permission != "FINANCE_READ":
            raise HTTPException(403, "FINANCE_IDENTITY_KIND_REQUIRED")

    def provenance(self) -> dict[str, Any]:
        value = self.model_dump(mode="json")
        value["permissions"] = sorted(self.permissions)
        return value


class IdentityVerifier(Protocol):
    """Provisioned trusted host adapter, not an API body/header-selected backend."""

    def authenticate(self, request: Request) -> Principal: ...

    def revalidate(self, provenance: dict[str, Any]) -> Principal: ...


def authenticated(request: Request) -> Principal:
    verifier = getattr(request.app.state, "finance_identity_verifier", None)
    if verifier is None:
        raise HTTPException(503, "VERIFIED_FINANCE_IDENTITY_UNAVAILABLE")
    try:
        principal = verifier.authenticate(request)
        if not isinstance(principal, Principal):
            raise ValueError
        return principal
    except Exception:
        raise HTTPException(401, "FINANCE_AUTHENTICATION_FAILED") from None


Identity = Annotated[Principal, Depends(authenticated)]
