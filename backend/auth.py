"""Supabase JWT authentication for multi-user deployment."""

import os
import time
import jwt
import requests
from fastapi import HTTPException, Depends, Header
from typing import Optional

# Try to import PyJWK for ES256 support (requires cryptography)
try:
    from jwt import PyJWK
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    PyJWK = None

# Supabase JWT configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
# Try backend env var first, then fallback to VITE_ prefix for local dev
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or os.getenv("VITE_SUPABASE_ANON_KEY", "")

# Legacy password auth (for backward compatibility during migration)
API_PASSWORD = os.getenv("COUNCIL_API_PASSWORD")

# Cached JWKS data
_jwks_cache = None
_jwks_cache_time = 0
JWKS_CACHE_TTL = 3600  # 1 hour cache


def fetch_jwks():
    """Fetch JWKS from Supabase with proper authentication."""
    global _jwks_cache, _jwks_cache_time

    # Return cached JWKS if still valid
    if _jwks_cache and (time.time() - _jwks_cache_time) < JWKS_CACHE_TTL:
        return _jwks_cache

    if not SUPABASE_URL:
        return None

    headers = {}
    if SUPABASE_ANON_KEY:
        headers["apikey"] = SUPABASE_ANON_KEY

    # Try the .well-known endpoint first
    jwks_url = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
    try:
        response = requests.get(jwks_url, headers=headers, timeout=10)
        if response.status_code == 200:
            _jwks_cache = response.json()
            _jwks_cache_time = time.time()
            return _jwks_cache
    except Exception:
        pass

    # Fallback to alternate endpoint
    jwks_url = f"{SUPABASE_URL}/auth/v1/jwks"
    try:
        response = requests.get(jwks_url, headers=headers, timeout=10)
        if response.status_code == 200:
            _jwks_cache = response.json()
            _jwks_cache_time = time.time()
            return _jwks_cache
    except Exception:
        pass

    return None


def get_signing_key_from_jwks(token: str):
    """Get the signing key for a JWT token from JWKS."""
    if not HAS_CRYPTO:
        return None

    jwks = fetch_jwks()
    if not jwks:
        return None

    # Get the kid from token header
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")

    # Find matching key in JWKS
    for key_data in jwks.get("keys", []):
        if key_data.get("kid") == kid:
            try:
                jwk = PyJWK.from_dict(key_data)
                return jwk.key
            except Exception:
                return None

    return None


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    Verify the Supabase JWT and return user info.

    Expected format: "Bearer <jwt_token>"

    Returns dict with user_id and email.
    """
    # If no auth configured at all, allow anonymous (development only)
    if not SUPABASE_URL and not SUPABASE_JWT_SECRET and not API_PASSWORD:
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

    # Try Supabase JWT verification
    if SUPABASE_URL:
        try:
            # Check what algorithm the token uses
            header = jwt.get_unverified_header(token)
            alg = header.get("alg", "HS256")

            if alg == "ES256":
                # Use JWKS for ES256 tokens
                signing_key = get_signing_key_from_jwks(token)
                if signing_key:
                    payload = jwt.decode(
                        token,
                        signing_key,
                        algorithms=["ES256"],
                        options={"verify_aud": False}
                    )
                    return {
                        "user_id": payload.get("sub"),
                        "email": payload.get("email"),
                        "role": payload.get("role"),
                    }
            elif alg == "HS256" and SUPABASE_JWT_SECRET:
                # Use JWT secret for HS256 tokens
                payload = jwt.decode(
                    token,
                    SUPABASE_JWT_SECRET,
                    algorithms=["HS256"],
                    options={"verify_aud": False}
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
        except jwt.InvalidTokenError:
            pass  # Fall through to legacy password check
        except Exception:
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
