"""Domínio operacional de distribuição de leads."""

from flask import Blueprint

dispatcher_blueprint = Blueprint(
    "dispatcher",
    __name__,
    url_prefix="/api/dispatcher",
)

from . import routes  # noqa: E402,F401
