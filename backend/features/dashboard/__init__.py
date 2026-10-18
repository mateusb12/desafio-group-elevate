from flask import Blueprint

dashboard_blueprint = Blueprint("dashboard", __name__, url_prefix="/dashboard")

from . import routes  # noqa: E402,F401
