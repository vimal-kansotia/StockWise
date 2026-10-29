"""API Security & Multi-tenant business authorization dependencies."""

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from sqlalchemy.orm import Session
from inventory_forecasting.authentication.security import TokenData, decode_access_token
from inventory_forecasting.config import settings
from inventory_forecasting.database.models import User
from inventory_forecasting.database.session import get_db

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user_or_api_key(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    api_key: str = Security(api_key_header),
    db: Session = Depends(get_db),
) -> TokenData:
    """Enforces authentication: accepts either Bearer JWT or Master Operational API Key."""
    # 1. Bearer JWT
    if credentials:
        token = credentials.credentials
        token_data = decode_access_token(token)
        if token_data:
            return token_data
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
        )

    # 2. Master API Key
    if api_key and api_key == settings.api_key:
        return TokenData(
            user_id="system_admin",
            email="admin@system.local",
            business_id="default_corp",
            role="OWNER",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide Bearer token or X-API-Key header.",
    )


def require_role(allowed_roles: list):
    """Role-based access control decorator/dependency."""
    def role_checker(current_user: TokenData = Depends(get_current_user_or_api_key)):
        if current_user.role not in allowed_roles and current_user.role != "OWNER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User role '{current_user.role}' lacks permission for this operation.",
            )
        return current_user
    return role_checker
