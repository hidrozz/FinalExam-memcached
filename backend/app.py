from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import json, threading, time
from datetime import datetime
from memcache_wrapper import get, set, push_to_list, get_list
import paho.mqtt.publish as publish

app = Flask(__name__)
CORS(app)

# Constants
THRESHOLD_SOIL = 50
ADC_DRY = 3000
ADC_WET = 1000
MAX_LOG = 100

# MQTT publish
def publish_relay_status(status):
    publish.single(
        "sensors/moist_threshold",
        payload=status,
        hostname="103.23.198.211",
        port=1883,
        auth={'username': 'myuser', 'password': 'tugasakhir'}
    )

# Logging
def log_relay_event(status, source):
    event = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "source": source
    }
    push_to_list("relay_log", event, max_length=MAX_LOG)

# === ROUTES ===

@app.route("/api/status")
def get_status():
    latest = get("latest_sensor_data")
    relay_status = get("relay_status") or "OFF"
    mode = get("mode") or "AUTO"

    if latest:
        data = json.loads(latest)
        soil_adc = data.get("soil_moist")
        try:
            soil_adc = float(soil_adc)
            moisture_percent = max(0, min(100, 100 - ((soil_adc - ADC_WET) / (ADC_DRY - ADC_WET) * 100)))
            data["soil_percent"] = round(moisture_percent, 1)
            data["soil_label"] = ("Kering" if moisture_percent < 35 else
                                  "Normal" if moisture_percent <= 70 else "Basah")
        except:
            data["soil_percent"] = None
            data["soil_label"] = None
        try:
            ph = float(data.get("soil_temp", 0))
            if 0 <= ph <= 14:
                data["ph_label"] = "Asam" if ph < 5.5 else "Netral" if ph <= 7.5 else "Basa"
            else:
                data["ph_label"] = "Invalid"
        except:
            data["ph_label"] = "Invalid"
    else:
        data = {
            "soil_moist": None, "soil_temp": "--", "env_hum": "--", "env_temp": "--",
            "soil_percent": None, "soil_label": None, "ph_label": None
        }

    data["relay_status"] = relay_status
    data["mode"] = mode
    return jsonify(data)

@app.route("/api/relay-toggle", methods=["POST"])
def toggle_relay():
    current = get("relay_status") or "OFF"
    new_status = "OFF" if current == "ON" else "ON"
    set("relay_status", new_status)
    log_relay_event(new_status, "manual")
    publish_relay_status(new_status)
    return jsonify({"relay_status": new_status})

@app.route("/api/auto-mode-toggle", methods=["POST"])
def toggle_auto_mode():
    current = get("mode") or "AUTO"
    new_mode = "MANUAL" if current == "AUTO" else "AUTO"
    set("mode", new_mode)
    return jsonify({"mode": new_mode})

@app.route("/api/chart-data")
def chart_data():
    data = get_list("sensor_data_log")
    labels = [datetime.fromisoformat(d["timestamp"]).strftime("%H:%M:%S") for d in data]
    soil = [d.get("soil_moist", 0) for d in data]
    temp = [d.get("env_temp", 0) for d in data]
    hum = [d.get("env_hum", 0) for d in data]
    ph = [d.get("soil_temp", 0) for d in data]
    return jsonify({
        "labels": labels[::-1],
        "soil": soil[::-1],
        "temperature": temp[::-1],
        "humidity": hum[::-1],
        "ph": ph[::-1]
    })

@app.route("/api/relay-log")
def get_relay_log():
    logs = get_list("relay_log")
    return jsonify(logs)

@app.route("/")
def serve_dashboard():
    return send_from_directory('../frontend', 'index.html')

@app.route("/css/<path:filename>")
def serve_css(filename):
    return send_from_directory('../frontend/css', filename)

@app.route("/js/<path:filename>")
def serve_js(filename):
    return send_from_directory('../frontend/js', filename)

# Auto controller
def auto_control_logic():
    latest = get("latest_sensor_data")
    mode = get("mode") or "AUTO"
    if not latest or mode != "AUTO":
        return
    try:
        data = json.loads(latest)
        soil_adc = float(data.get("soil_moist", 0))
        moisture_percent = max(0, min(100, 100 - ((soil_adc - ADC_WET) / (ADC_DRY - ADC_WET) * 100)))
        current_status = get("relay_status") or "OFF"
        if moisture_percent < THRESHOLD_SOIL and current_status != "ON":
            set("relay_status", "ON")
            log_relay_event("ON", "auto")
            publish_relay_status("ON")
        elif moisture_percent >= THRESHOLD_SOIL and current_status != "OFF":
            set("relay_status", "OFF")
            log_relay_event("OFF", "auto")
            publish_relay_status("OFF")
    except Exception as e:
        print("[AUTO ERROR]", e)

def auto_loop():
    while True:
        auto_control_logic()
        time.sleep(5)

threading.Thread(target=auto_loop, daemon=True).start()

if __name__ == "__main__":
    set("mode", "AUTO")
    set("relay_status", "OFF")
    app.run(host="0.0.0.0", port=5000)
