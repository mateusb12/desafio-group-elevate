from flask import jsonify, request, session
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import db_session

from . import auth_blueprint
from .models import User
from .service import authenticate, user_payload


def current_user(db: Session) -> User | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))


@auth_blueprint.post("/login")
def login():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(error="JSON inválido."), 400
    email = str(body.get("email", "")).strip().lower()
    password = body.get("password")
    if not email or not isinstance(password, str) or not password:
        return jsonify(error="E-mail e senha são obrigatórios."), 400

    with db_session() as db:
        user = authenticate(db, email, password)
        if user is None:
            return jsonify(error="E-mail ou senha inválidos."), 401
        session.clear()
        session["user_id"] = user.id
        return jsonify(user=user_payload(db, user))


@auth_blueprint.get("/me")
def me():
    with db_session() as db:
        user = current_user(db)
        if user is None:
            return jsonify(error="Autenticação necessária."), 401
        return jsonify(user=user_payload(db, user))


@auth_blueprint.post("/logout")
def logout():
    session.clear()
    return jsonify(status="ok")
