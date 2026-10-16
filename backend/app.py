from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/")
def hello():
    return "Hello, world!"


@app.get("/ping")
def ping():
    return jsonify(status="ok", message="pong")


if __name__ == "__main__":
    app.run(debug=True)
