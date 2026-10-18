from flask import Blueprint


auth_blueprint = Blueprint("auth", __name__, url_prefix="/auth")

from . import routes  # noqa: E402,F401
