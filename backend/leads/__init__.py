from flask import Blueprint

leads_blueprint = Blueprint('leads', __name__, url_prefix='/api/leads')

from . import routes  # noqa: E402,F401
