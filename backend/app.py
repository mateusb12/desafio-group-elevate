import os

from flask import Flask, jsonify

from auth import auth_blueprint
from auth.service import seed_demo_users
from database import db_session, initialize_database
from dispatcher import models as dispatcher_models  # noqa: F401


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "development-only-change-me")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    app.register_blueprint(auth_blueprint)

    @app.get("/")
    def hello():
        return "Hello, world!"

    @app.get("/ping")
    def ping():
        return jsonify(status="ok", message="pong")

    return app


initialize_database()
if os.getenv("SEED_DEMO") == "1":
    with db_session() as database:
        seed_demo_users(database)

app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
