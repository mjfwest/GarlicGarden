import eventlet

eventlet.monkey_patch()
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import redis
import json

import time
import random
from datetime import datetime, timedelta
import threading

redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
# make app
app = Flask(
    __name__,
    static_url_path="",
    static_folder="web/static",
    template_folder="web/templates",
)


# Update the SocketIO initialization
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    message_queue="redis://localhost:6379/0",  # Adjust if your Redis is elsewhere
    logger=True,
    engineio_logger=True,
)

##set starting variables
sensor_data = {"moisture": 0}
pump_state = {"pump": False}
max_data_points = 100


def add_humidity_data():
    while True:
        time.sleep(0.5)
        new_point = {"date": time.time(), "value": random.randint(0, 50)}
        # Append to stored data for history
        data = redis_client.get("humidity_data")
        humidity_data = json.loads(data) if data else []
        humidity_data.append(new_point)
        redis_client.set("humidity_data", json.dumps(humidity_data))
        # Publish new point to Redis pub/sub channel
        redis_client.publish("humidity_channel", json.dumps(new_point))


def humidity_pubsub_listener():
    pubsub = redis_client.pubsub()
    pubsub.subscribe("humidity_channel")
    for message in pubsub.listen():
        if message["type"] == "message":
            new_point = json.loads(message["data"])
            # Emit to all Socket.IO clients in the "humidity" room
            socketio.emit("humidity", new_point, room="humidity")


def add_temperature_data():
    while True:
        time.sleep(2.0)
        new_point = {"date": time.time(), "value": random.randint(50, 100)}
        # Append to stored data for history
        data = redis_client.get("temperature_data")
        temperature_data = json.loads(data) if data else []
        temperature_data.append(new_point)
        redis_client.set("temperature_data", json.dumps(temperature_data))
        # Publish new point to Redis pub/sub channel
        redis_client.publish("temperature_channel", json.dumps(new_point))


def temperature_pubsub_listener():
    pubsub = redis_client.pubsub()
    pubsub.subscribe("temperature_channel")
    for message in pubsub.listen():
        if message["type"] == "message":
            new_point = json.loads(message["data"])
            # Emit to all Socket.IO clients in the "humidity" room
            socketio.emit("temperature", new_point, room="temperature")


@socketio.on("subscribe")
def handle_subscribe(data):
    stream = data.get("stream")
    if stream in ("humidity", "temperature"):
        join_room(stream)
        # Send the last N points immediately from Redis
        key = f"{stream}_data"
        data_json = redis_client.get(key)
        if data_json:
            arr = json.loads(data_json)
            # Send last 100 points (or fewer if not enough)
            emit(stream, arr[-100:])
        else:
            emit(stream, [])


@app.route("/data/<stream>", methods=["GET"])
def get_data(stream):
    key = f"{stream}_data"
    data_json = redis_client.get(key)
    if data_json:
        return jsonify(json.loads(data_json))
    else:
        return jsonify([]), 404


@socketio.on("unsubscribe")
def handle_unsubscribe(data):
    stream = data.get("stream")
    if stream in ("humidity", "temperature"):
        leave_room(stream)


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/sensor", methods=["POST"])
def receive_sensor():
    data = request.json
    sensor_data["moisture"] = data["moisture"]
    return jsonify({"status": "ok"})


@app.route("/status", methods=["GET"])
def get_status():
    return jsonify(
        {**sensor_data, **pump_state}
    )  # right now unpacking is unnecercery, but if it has more properties later, it will still work


@app.route("/pump", methods=["GET"])
def get_pump():
    return jsonify(pump_state)


@app.route("/pump", methods=["POST"])
def set_pump():
    data = request.json
    pump_state["pump"] = data.get(
        "pump", False
    )  # if data["pump"] = something then it is that thing but if it doesn't exist it is False
    return jsonify({"status": "updated to " + str(pump_state["pump"])})


@app.route("/button", methods=["POST"])
def button():
    data = request.json
    print(data)
    return jsonify({"status", "ok"})


if __name__ == "__main__":
    # Start the background task using SocketIO's helper
    socketio.start_background_task(add_humidity_data)
    socketio.start_background_task(add_temperature_data)
    threading.Thread(target=humidity_pubsub_listener, daemon=True).start()
    threading.Thread(target=temperature_pubsub_listener, daemon=True).start()

    # Run the SocketIO app instead of the Flask app
    socketio.run(app, host="0.0.0.0", port=5555, debug=True)
