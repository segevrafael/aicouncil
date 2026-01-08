"""Simple password authentication for single-user deployment."""

import os
from fastapi import HTTPException, Depends, Header
from typing import Optional

# Password stored in environment variable
API_PASSWORD = os.getenv("COUNCIL_API_PASSWORD")


def verify_password(authorization: Optional[str] = Header(None)) -> bool:
    """
    Verify the password from Authorization header.

    Expected format: "Bearer <password>"

    For single-user deployment, this provides basic protection
    without the complexity of user management.
    """
    # If no password is configured, allow all requests (development mode)
    if not API_PASSWORD:
        return True

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
            detail="Invalid authorization format. Use: Bearer <password>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    if token != API_PASSWORD:
        raise HTTPException(
            status_code=401,
            detail="Invalid password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True


# Dependency for protected routes
def require_auth(authorized: bool = Depends(verify_password)) -> None:
    """Dependency that ensures request is authenticated."""
    pass
