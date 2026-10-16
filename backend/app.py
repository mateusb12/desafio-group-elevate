from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/")
def hello():
    return "Hello, world!"


@app.get("/ping")
def ping():
    return jsonify(status="ok", message="pong")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
