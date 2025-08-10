from flask import Flask, request, jsonify

#make app
app = Flask(__name__)

##set startubg varuabkes
sensor_data = {"moisture" : 0}
pump_state = {"pump": False}

# /sensor POST sets sensor data and returns status ✅
# /status GET returns sensor and pump unpacked in a list ✅
# /pump GET return pump_state ✅
# /pump POST  sets the pump state to the value if it is there and false if it isn't, returns status ✅

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



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)