from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt

from app.core.config.settings import JwtSettings, get_settings


class TokenPayload:
    def __init__(
        self,
        sub: str,
        org_id: str | None = None,
        exp: datetime | None = None,
        iat: datetime | None = None,
        jti: str | None = None,
        token_type: str = "access",
    ) -> None:
        self.sub = sub
        self.org_id = org_id
        self.exp = exp or self._default_expiry()
        self.iat = iat or datetime.now(UTC)
        self.jti = jti or uuid4().hex
        self.token_type = token_type

    def to_dict(self) -> dict[str, Any]:
        return {
            "sub": self.sub,
            "org_id": self.org_id,
            "exp": self.exp,
            "iat": self.iat,
            "jti": self.jti,
            "type": self.token_type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TokenPayload:
        return cls(
            sub=data["sub"],
            org_id=data.get("org_id"),
            exp=data.get("exp"),
            iat=data.get("iat"),
            jti=data.get("jti"),
            token_type=data.get("type", "access"),
        )

    def _default_expiry(self) -> datetime:
        settings = get_settings().jwt
        if self.token_type == "access":
            return datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
        return datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)


class TokenService:
    def __init__(self, settings: JwtSettings | None = None) -> None:
        self._settings = settings or get_settings().jwt

    def create_access_token(self, user_id: str, org_id: str | None = None) -> str:
        payload = TokenPayload(sub=user_id, org_id=org_id, token_type="access")
        return self._encode(payload)

    def create_refresh_token(self, user_id: str, org_id: str | None = None) -> str:
        payload = TokenPayload(sub=user_id, org_id=org_id, token_type="refresh")
        return self._encode(payload)

    def decode_token(self, token: str) -> TokenPayload:
        try:
            data = jwt.decode(
                token,
                self._get_secret_key(),
                algorithms=[self._settings.algorithm],
            )
            return TokenPayload.from_dict(data)
        except JWTError as exc:
            raise InvalidTokenError("Token is invalid or expired") from exc

    def _encode(self, payload: TokenPayload) -> str:
        return jwt.encode(
            payload.to_dict(),
            self._get_secret_key(),
            algorithm=self._settings.algorithm,
        )

    def _get_secret_key(self) -> str:
        return get_settings().app.secret_key


class InvalidTokenError(Exception):
    pass
