"""Ferramentas administrativas para demonstrar o fluxo de entregas."""

from flask import Blueprint

lab_blueprint = Blueprint("lab", __name__, url_prefix="/api/lab")

from . import routes  # noqa: E402,F401
