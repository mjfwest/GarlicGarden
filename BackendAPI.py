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
import psutil
import requests

"""
GarlicGarden Backend API

A Flask-SocketIO application that collects, stores, and distributes various sensor data streams.
Uses Redis for data storage and pub/sub messaging to enable real-time data streaming to clients.
Provides HTTP endpoints for data access and IoT device integration.
"""

MAX_DATA_AGE = 3600  # Max age of data points to store per stream

# Connect to Redis server for data storage and pub/sub
redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

# Initialize Flask application with static file configuration
app = Flask(
    __name__,
    static_url_path="",
    static_folder="web/static",
    template_folder="web/templates",
)


# Initialize SocketIO with Redis message queue for scaling across multiple processes
socketio = SocketIO(
    app,
    cors_allowed_origins="*",  # Allow connections from any origin
    message_queue="redis://localhost:6379/0",  # Use Redis as message queue
    logger=True,  # Enable SocketIO logging
    engineio_logger=True,  # Enable Engine.IO logging
)

# Global variables for pump state
pump_state = {"pump": False}


# Lists to track registered data streams
registered_streams = []
registered_names = []


class Stream:
    """
    Stream class represents a data stream with associated channel, ID, name and color.

    Each stream has its own Redis pub/sub channel and socket.io room.
    The listener method subscribes to the Redis channel and broadcasts
    new data points to connected clients.

    Attributes:
        channel (str): Redis pub/sub channel name
        id (str): Unique identifier for the stream
        name (str): Human-readable name for the stream
        colour (str): Hex color code for visualization
    """

    def __init__(self, channel, id, name, colour):
        """
        Initialize a new data stream.

        Args:
            channel (str): Redis pub/sub channel name
            id (str): Unique identifier for the stream
            name (str): Human-readable name for the stream
            colour (str): Hex color code for visualization
        """
        self.channel = channel
        self.id = id
        self.name = name
        self.colour = colour
        registered_streams.append(self)
        registered_names.append(id)

    def listener(self):
        """
        Listen for new data on the Redis pub/sub channel and broadcast to socket.io clients.

        This method runs in a separate thread and continuously monitors the Redis channel
        for new messages, forwarding them to connected clients.
        """
        pubsub = redis_client.pubsub()
        pubsub.subscribe(self.channel)
        for message in pubsub.listen():
            if message["type"] == "message":
                new_point = json.loads(message["data"])
                socketio.emit(self.id, new_point, room=self.id)


# Define available data streams

# Stream(
#     channel="cpu_temp_channel", id="cpu_temp", name="CPU temperature", colour="#FF0000"
# )
Stream(channel="cpu_usage_channel", id="cpu_usage", name="CPU usage", colour="#00FF00")
Stream(channel="humidity_channel", id="humidity", name="Humidity", colour="#0000FF")
Stream(
    channel="temperature_channel",
    id="temperature",
    name="Temperature",
    colour="#FFFF00",
)
Stream(channel="moisture_channel", id="moisture", name="Moisture", colour="#00FFFF")


def get_cpu_temperature():
    """
    Read CPU temperature from the system.

    Attempts multiple methods to retrieve CPU temperature on Linux systems.

    Returns:
        float: CPU temperature in degrees Celsius, or None if unavailable
    """
    try:
        # Try the most common temperature source first
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = float(f.read().strip()) / 1000.0  # Convert millidegrees to degrees
            return temp
    except:
        try:
            # Try using sensors command if available
            import subprocess

            output = subprocess.check_output(["sensors"], universal_newlines=True)
            for line in output.split("\n"):
                if "Core 0" in line and "°C" in line:
                    return float(line.split("+")[1].split("°C")[0].strip())
        except:
            # Return a placeholder if we can't get the temperature
            return None  # Placeholder


def cpu_usage_publisher():
    """
    Publish CPU usage percentage every 5 seconds.

    Collects CPU usage data using psutil, stores it in Redis,
    and publishes it to the cpu_usage_channel for real-time updates.
    This function runs in an infinite loop in a separate thread.
    """
    while True:
        try:
            usage = psutil.cpu_percent(interval=1)
            data_point = {"value": usage, "date": time.time()}
            key = "cpu_usage_data"
            # use the sensor endpoint to store the data
            url = f"http://localhost:5555/publish/cpu_usage"
            response = requests.post(url, json=data_point)
            response.raise_for_status()  # Raise an error for bad responses

        except Exception as e:
            print(f"Error publishing CPU usage: {e}")
        time.sleep(4)  # 1s for cpu_percent + 4s = 5s total


# def cpu_temp_publisher():
#     """
#     Publish CPU temperature every 5 seconds.

#     Collects CPU temperature data, stores it in Redis,
#     and publishes it to the cpu_temp_channel for real-time updates.
#     This function runs in an infinite loop in a separate thread.
#     """
#     while True:
#         try:
#             # Get CPU temperature
#             temp = get_cpu_temperature()

#             # Create data point
#             data_point = {"value": temp, "date": time.time()}

#         except Exception as e:
#             print(f"Error publishing CPU temp: {e}")

#         # Wait 5 seconds
#         time.sleep(5)


@socketio.on("subscribe")
def handle_subscribe(data):
    """
    Handle client subscription to a data stream.

    When a client subscribes to a stream, they join a room for that stream
    and receive the most recent data points immediately.

    Args:
        data (dict): Contains 'stream' key with the stream ID to subscribe to
    """
    stream = data.get("stream")

    if stream in [s.id for s in registered_streams]:
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


@socketio.on("unsubscribe")
def handle_unsubscribe(data):
    """
    Handle client unsubscription from a data stream.

    When a client unsubscribes from a stream, they leave the room
    for that stream and stop receiving updates.

    Args:
        data (dict): Contains 'stream' key with the stream ID to unsubscribe from
    """
    stream = data.get("stream")
    if stream in [s.id for s in registered_streams]:
        leave_room(stream)


# Add a new endpoint to list all available streams
@app.route("/streams", methods=["GET"])
def get_streams():
    """
    List all available data streams.

    Returns:
        JSON array: List of available streams with their ID, name, and color
    """
    # Define available streams with friendly names and colors
    available_streams = []
    for stream in registered_streams:
        available_streams.append(
            {"id": stream.id, "name": stream.name, "colour": stream.colour}
        )
    return jsonify(available_streams)


# publish endpoints for IoT devices
@app.route("/publish/<stream>", methods=["POST"])
def publish_data(stream):
    """
    Publish data to a specific stream.

    Endpoint for IoT devices to send data to the system.

    Args:
        stream (str): Stream ID to publish to

    Request body:
        JSON object with at least a 'value' field

    Returns:
        JSON response: Confirmation or error message
    """
    if stream not in registered_names:
        return jsonify({"error": "Invalid stream"}), 400

    try:
        # Get data from request
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Ensure it has required fields
        if "value" not in data:
            return jsonify({"error": "Missing 'value' field"}), 400

        # Add timestamp if not provided
        if "date" not in data:
            data["date"] = time.time()

        # Store in Redis
        key = f"{stream}_data"
        redis_client.zadd(key, {json.dumps(data): data["date"]})

        # Remove data older than 1 hour (3600 seconds)
        long_ago = time.time() - MAX_DATA_AGE

        redis_client.zremrangebyscore(key, "-inf", long_ago)
        # Publish to channel
        redis_client.publish(f"{stream}_channel", json.dumps(data))

        return jsonify({"status": "published"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/data/<stream>", methods=["GET"])
def get_data(stream):
    """
    Get historical data for a specific stream.

    Args:
        stream (str): Stream ID to retrieve data for
    Query Parameters:
        duration (int): Optional. The number of seconds of historical data to retrieve.

    Returns:
        JSON array: Historical data points for the requested stream
    """
    key = f"{stream}_data"
    duration = request.args.get("duration", type=int)

    try:
        if duration:
            # Calculate the timestamp range
            now = time.time()
            min_score = now - duration
            max_score = now

            # Retrieve data from Redis sorted set
            data = redis_client.zrangebyscore(key, min_score, max_score)
        else:
            # Retrieve all data if no duration is specified
            data = redis_client.zrangebyscore(key, "-inf", "+inf")

        # Deserialize the data points
        return jsonify([json.loads(item) for item in data])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Add a simple simulator endpoint for development
@app.route("/simulate", methods=["GET"])
def simulate_data():
    """
    Generate and publish fake data for development and testing.

    Creates random humidity and temperature readings and publishes them.

    Returns:
        JSON response: Status and generated data points
    """
    import random

    humidity = {"value": random.randint(0, 50), "date": time.time()}
    temperature = {"value": random.randint(50, 100), "date": time.time()}

    # Store and publish humidity
    redis_client.publish("humidity_channel", json.dumps(humidity))
    redis_client.publish("temperature_channel", json.dumps(temperature))
    # Store in Redis
    for stream, data in [("humidity", humidity), ("temperature", temperature)]:
        key = f"{stream}_data"
        redis_client.zadd(key, {json.dumps(data): data["date"]})

        # Remove data older than 1 hour (3600 seconds)
        long_ago = time.time() - MAX_DATA_AGE

        redis_client.zremrangebyscore(key, "-inf", long_ago)
        # Publish to channel
        redis_client.publish(f"{stream}_channel", json.dumps(data))

    return jsonify(
        {
            "status": "simulated data sent",
            "humidity": humidity,
            "temperature": temperature,
        }
    )


@app.route("/")
def index():
    """
    Serve the main HTML page.

    Returns:
        HTML: Main application page
    """
    return app.send_static_file("index.html")


# @app.route("/sensor", methods=["POST"])
# def receive_sensor():
#     """
#     Receive sensor data from an IoT device.

#     Request body:
#         JSON object with 'moisture' field

#     Returns:
#         JSON response: Status confirmation
#     """
#     data = request.json
#     sensor_data["moisture"] = data["moisture"]
#     return jsonify({"status": "ok"})


@app.route("/status", methods=["GET"])
def get_status():
    """
    Get current sensor and pump status.

    Returns:
        JSON object: Combined sensor data and pump state
    """
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
    for stream in registered_streams:
        threading.Thread(target=stream.listener, daemon=True).start()

    # Start CPU temperature publisher
    # threading.Thread(target=cpu_usage_pubsub_listener, daemon=True).start()
    threading.Thread(target=cpu_usage_publisher, daemon=True).start()

    # Run the SocketIO app instead of the Flask app
    socketio.run(app, host="0.0.0.0", port=5555, debug=True)
