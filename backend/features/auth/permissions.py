from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.database import db_session

from .models import User, UserRole


def current_user(db: Session) -> User | None:
    user_id = get_jwt_identity()
    if not user_id:
        return None
    return db.scalar(
        select(User).where(
            User.id == user_id,
            User.is_active.is_(True),
        )
    )


def _admin_error(db: Session, forbidden_message: str):
    user = current_user(db)
    if user is None:
        return jsonify(error="Autenticação necessária."), 401
    if user.role != UserRole.ADMIN:
        return jsonify(error=forbidden_message), 403
    return None


def require_admin(db: Session, forbidden_message: str = "Acesso restrito a administradores."):
    """Run the administrator policy for flows that cannot use a decorator."""
    return _admin_error(db, forbidden_message)


def admin_required(view=None, *, forbidden_message: str = "Acesso restrito a administradores."):
    """Protect an endpoint with the application's administrator policy."""
    def decorator(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with db_session() as db:
                authorization_error = _admin_error(db, forbidden_message)
            if authorization_error:
                return authorization_error
            return function(*args, **kwargs)

        return wrapped

    if view is None:
        return decorator
    return decorator(view)
