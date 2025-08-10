import flask
from flask import Flask, request, jsonify
from flask_socketio import SocketIO

import threading
import time
import random
from datetime import datetime, timedelta


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
    async_mode="threading",  # Use threading mode
    logger=True,  # Enable logging
    engineio_logger=True,
)  # Enable Engine.IO logging

##set starting variables
sensor_data = {"moisture": 0}
pump_state = {"pump": False}


# Initialize data with some starting values
data = [
    {"date": 1, "value": 10},
]
max_data_points = 100  # Limit the number of data points to keep memory usage reasonable


# Function to add data periodically
def add_data_periodically():
    global data
    while True:
        time.sleep(0.5)  # Wait for 0.5 seconds (increased frequency)
        # Get the last date value and increment by 1
        last_date = data[-1]["date"] if data else 0
        new_date = last_date + 1
        # Generate a random value between 0 and 100
        new_value = random.randint(0, 100)
        # Add new data point to our array
        data.append({"date": new_date, "value": new_value})
        # Emit the updated data via SocketIO
        socketio.emit("data_update", data)
        # Keep the data array size manageable
        if len(data) > max_data_points:
            data.pop(0)


# Start the background thread after SocketIO is initialized
@socketio.on("connect")
def handle_connect():
    print("Client connected")
    # Send the current data to the newly connected client
    socketio.emit("data_update", data, to=request.sid)


@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected")


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


# Keep this endpoint for initial data loading or API compatibility
@app.route("/data", methods=["GET"])
def get_data():
    return jsonify(data)


if __name__ == "__main__":
    # Start the background thread
    data_thread = threading.Thread(target=add_data_periodically, daemon=True)
    data_thread.start()

    # Run the SocketIO app instead of the Flask app
    socketio.run(app, host="0.0.0.0", port=5555, debug=True)
