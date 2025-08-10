import flask
from flask import Flask, request, jsonify

#make app
app = Flask(__name__,
            static_url_path='',
            static_folder='web/static',
            template_folder='web/templates')

##set startubg varuabkes
sensor_data = {"moisture" : 0}
pump_state = {"pump": False}

# /sensor POST sets sensor data and returns status ✅
# /status GET returns sensor and pump unpacked in a list ✅
# /pump GET return pump_state ✅
# /pump POST  sets the pump state to the value if it is there and false if it isn't, returns status ✅

# @app.route('/', methods=["GET"])
# def serve_website():
#     print("got here")
#     return flask.send_from_directory('templates', 'index.html')

@app.route("/sensor", methods=["POST"])
def receive_sensor():
    data = request.json
    sensor_data["moisture"] = data["moisture"]
    return jsonify({"status": "ok"})

@app.route("/status", methods=["GET"])
def get_status ():
    return jsonify({**sensor_data,**pump_state}) # right now unpacking is unnecercery, but if it has more properties later, it will still work

@app.route("/pump", methods=["GET"])
def get_pump ():
    return jsonify(pump_state)

@app.route("/pump",methods=["POST"])
def set_pump():
    data = request.json
    pump_state["pump"] = data.get("pump", False) # if data["pump"] = something then it is that thing but if it doesn't exist it is False
    return jsonify({"status": "updated to " + str(pump_state["pump"])})

@app.route("/button",methods=["POST"])
def button():
    data = request.json
    print(data)
    return jsonify({"status","ok"})

@app.route("/data", methods=["GET"])
def make_up_data():
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
        {"date": 12, "value": 98}
    ]

    return jsonify(data)



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)