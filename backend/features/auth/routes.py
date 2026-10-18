from flask import jsonify, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    jwt_required,
    set_access_cookies,
    unset_jwt_cookies,
)
from shared.database import db_session

from . import auth_blueprint
from .models import TokenBlocklist
from .permissions import current_user
from .schemas import validate_login
from .service import authenticate, user_payload


@auth_blueprint.post("/login")
def login():
    body = request.get_json(silent=True)
    login_input, validation_error = validate_login(body)
    if validation_error:
        return jsonify(error=validation_error), 400

    with db_session() as db:
        user = authenticate(db, login_input.email, login_input.password)
        if user is None:
            return jsonify(error="E-mail ou senha inválidos."), 401
        response = jsonify(user=user_payload(db, user))
        set_access_cookies(response, create_access_token(identity=user.id))
        return response


@auth_blueprint.get("/me")
@jwt_required()
def me():
    with db_session() as db:
        user = current_user(db)
        if user is None:
            return jsonify(error="Autenticação necessária."), 401
        return jsonify(user=user_payload(db, user))


@auth_blueprint.post("/logout")
@jwt_required()
def logout():
    with db_session() as db:
        db.add(TokenBlocklist(jti=get_jwt()["jti"]))
        db.commit()
    response = jsonify(status="ok")
    unset_jwt_cookies(response)
    return response
