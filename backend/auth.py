"""Supabase JWT authentication for multi-user deployment."""

import os
import jwt
from fastapi import HTTPException, Depends, Header
from typing import Optional

# Supabase JWT configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

# Legacy password auth (for backward compatibility during migration)
API_PASSWORD = os.getenv("COUNCIL_API_PASSWORD")


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    Verify the Supabase JWT and return user info.

    Expected format: "Bearer <jwt_token>"

    Returns dict with user_id and email.
    """
    # If no auth configured at all, allow anonymous (development only)
    if not SUPABASE_JWT_SECRET and not API_PASSWORD:
        return {"user_id": None, "email": None}

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Parse "Bearer <token>" format
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization format. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    # Try Supabase JWT verification first
    if SUPABASE_JWT_SECRET:
        try:
            # Supabase uses HS256 algorithm
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated"
            )

            return {
                "user_id": payload.get("sub"),
                "email": payload.get("email"),
                "role": payload.get("role"),
            }
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=401,
                detail="Token has expired. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as e:
            # Fall through to legacy password check
            pass

    # Legacy password auth (backward compatibility)
    if API_PASSWORD and token == API_PASSWORD:
        return {"user_id": None, "email": None, "legacy_auth": True}

    raise HTTPException(
        status_code=401,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_auth(user: dict = Depends(get_current_user)) -> dict:
    """Dependency that ensures request is authenticated and returns user info."""
    return user


# For endpoints that just need to verify auth without user info
def require_auth_simple(user: dict = Depends(get_current_user)) -> None:
    """Dependency that ensures request is authenticated."""
    pass
