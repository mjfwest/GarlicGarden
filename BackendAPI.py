import flask
from flask import Flask, request, jsonify

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

##set startubg varuabkes
sensor_data = {"moisture": 0}
pump_state = {"pump": False}


# Initialize data with some starting values
data = [
    {"date": 1, "value": 10},
    {"date": 2, "value": 65},
    {"date": 3, "value": 96},
    {"date": 4, "value": 97},
    {"date": 5, "value": 97},
    {"date": 6, "value": 19},
    {"date": 7, "value": 67},
    {"date": 8, "value": 13},
    {"date": 9, "value": 43},
    {"date": 10, "value": 54},
    {"date": 11, "value": 13},
    {"date": 12, "value": 98},
]


# Function to add data periodically
def add_data_periodically():
    global data
    while True:
        time.sleep(30)  # Wait for 30 seconds
        # Get the last date value and increment by 1
        last_date = data[-1]["date"] if data else 0
        new_date = last_date + 1
        # Generate a random value between 0 and 100
        new_value = random.randint(0, 100)
        # Add new data point to our array
        data.append({"date": new_date, "value": new_value})
        print(f"Added new data point: date={new_date}, value={new_value}")


# Start the background thread
data_thread = threading.Thread(target=add_data_periodically, daemon=True)
data_thread.start()


# /sensor POST sets sensor data and returns status ✅
# /status GET returns sensor and pump unpacked in a list ✅
# /pump GET return pump_state ✅
# /pump POST  sets the pump state to the value if it is there and false if it isn't, returns status ✅


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


@app.route("/data", methods=["GET"])
def get_data():
    return jsonify(data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5555)
