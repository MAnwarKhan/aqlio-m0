"""Streamlit OIDC identity adapter; Aqlio authorization remains separate."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.domain import User
from app.ports import AuthenticationRequired


class StreamlitOIDCAuth:
    """Map validated OIDC claims to a stable minimal Aqlio identity."""

    def __init__(
        self,
        claims_loader: Callable[[], Mapping[str, Any]],
        *,
        provider: str = "google",
        admin_emails: frozenset[str] = frozenset(),
    ) -> None:
        self._claims_loader = claims_loader
        self._provider = provider
        self._admin_emails = frozenset(email.lower() for email in admin_emails)

    def current_user(self) -> User:
        claims = self._claims_loader()
        subject = str(claims.get("sub", "")).strip()
        email = str(claims.get("email", "")).strip().lower()
        verified = claims.get("email_verified", False)
        if not subject or not email or verified not in {True, "true", "True"}:
            raise AuthenticationRequired("Sign in to continue.")
        name = str(claims.get("name", "")).strip() or email.split("@", 1)[0]
        stable_id = str(uuid5(NAMESPACE_URL, f"aqlio:{self._provider}:{subject}"))
        return User(
            id=stable_id,
            email=email,
            display_name=name,
            active=True,
            is_admin=email in self._admin_emails,
            identity_provider=self._provider,
            identity_subject=subject,
        )
