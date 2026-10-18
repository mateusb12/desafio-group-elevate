# Group Elevate webhook callcenter
import hmac
import os

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from features.auth.permissions import require_admin
from shared.database import db_session
from .schemas import validate_webhook_payload
from .service import process_webhook

webhooks_blueprint = Blueprint('webhooks', __name__, url_prefix='/api/webhooks')


def has_valid_webhook_key(configured_key, supplied_key):
    """Verifica se a chave enviada pelo call center é válida."""
    return bool(configured_key) and hmac.compare_digest(
        configured_key,
        supplied_key,
    )


@webhooks_blueprint.post('/callcenter')
@jwt_required(optional=True)
def callcenter_webhook():
    configured_key = os.getenv('CALLCENTER_WEBHOOK_KEY', '')
    supplied_key = request.headers.get('X-Webhook-Key', '')
    webhook_key_is_valid = has_valid_webhook_key(
        configured_key, supplied_key
    )

    if not webhook_key_is_valid:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify(error='Webhook não autorizado.'), 401

        with db_session() as db:
            authorization_error = require_admin(
                db,
                forbidden_message='Apenas administradores podem simular webhooks.',
            )
            if authorization_error:
                return authorization_error

    if not request.is_json:
        return jsonify(error='Envie JSON.'), 415

    payload, validation_error = validate_webhook_payload(
        request.get_json(silent=True)
    )
    if validation_error:
        return jsonify(error=validation_error), 400

    with db_session() as db:
        response, status_code = process_webhook(db, payload)

    return jsonify(response), status_code
