from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from memcache_wrapper import mc
import json
import time
from datetime import datetime
import threading
import paho.mqtt.publish as publish

app = Flask(__name__)
CORS(app)

# Konstanta
KEY_LATEST = "latest_sensor_data_m"
KEY_LOG = "sensor_data_log_m"
RELAY_STATUS = "relay_status_m"
MODE_KEY = "mode_m"
RELAY_LOG = "relay_log_m"
MAX_LOG = 100
MAX_LOG_RELAY = 100

THRESHOLD_SOIL = 50
ADC_DRY = 3000
ADC_WET = 1000

# MQTT config untuk relay publish
def publish_relay_status(status):
    publish.single("sensors/moist_threshold", payload=status,
        hostname="103.76.120.64", port=1883,
        auth={'username': 'myuser', 'password': 'tugasakhir'}
    )

# Logging relay event
def log_relay_event(status, source):
    log = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "source": source
    }
    logs = mc.get(RELAY_LOG) or []
    logs.insert(0, log)
    logs = logs[:MAX_LOG_RELAY]
    mc.set(RELAY_LOG, logs)

@app.route("/api/status")
def get_status():
    latest = mc.get(KEY_LATEST)
    relay_status = mc.get(RELAY_STATUS) or "OFF"
    mode = mc.get(MODE_KEY) or "AUTO"

    if latest:
        data = latest
        soil_adc = data.get("soil_moist")
        try:
            soil_adc = float(soil_adc)
            moisture_percent = max(0, min(100, 100 - ((soil_adc - ADC_WET) / (ADC_DRY - ADC_WET) * 100)))
            data["soil_percent"] = round(moisture_percent, 1)
            data["soil_label"] = "Kering" if moisture_percent < 35 else "Normal" if moisture_percent <= 70 else "Basah"
        except:
            data["soil_percent"] = None
            data["soil_label"] = None
        try:
            ph = float(data.get("soil_temp", 0))
            data["ph_label"] = "Asam" if ph < 5.5 else "Netral" if ph <= 7.5 else "Basa"
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
    current = mc.get(RELAY_STATUS) or "OFF"
    new_status = "OFF" if current == "ON" else "ON"
    mc.set(RELAY_STATUS, new_status)
    log_relay_event(new_status, "manual")
    publish_relay_status(new_status)
    return jsonify({"relay_status": new_status})

@app.route("/api/auto-mode-toggle", methods=["POST"])
def toggle_mode():
    current = mc.get(MODE_KEY) or "AUTO"
    new_mode = "MANUAL" if current == "AUTO" else "AUTO"
    mc.set(MODE_KEY, new_mode)
    return jsonify({"mode": new_mode})

@app.route("/api/chart-data")
def chart_data():
    logs = mc.get(KEY_LOG) or []
    labels = [datetime.fromisoformat(d["timestamp"]).strftime("%H:%M:%S") for d in logs]
    soil = [d.get("soil_moist", 0) for d in logs]
    temp = [d.get("env_temp", 0) for d in logs]
    hum = [d.get("env_hum", 0) for d in logs]
    ph = [d.get("soil_temp", 0) for d in logs]
    return jsonify({
        "labels": labels[::-1], "soil": soil[::-1], "temperature": temp[::-1],
        "humidity": hum[::-1], "ph": ph[::-1]
    })

@app.route("/api/relay-log")
def relay_log():
    logs = mc.get(RELAY_LOG) or []
    return jsonify(logs)

@app.route("/")
def serve_dashboard():
    return send_from_directory('../Frontend', 'index.html')

@app.route("/css/<path:filename>")
def serve_css(filename):
    return send_from_directory('../Frontend/css', filename)

@app.route("/js/<path:filename>")
def serve_js(filename):
    return send_from_directory('../Frontend/js', filename)

# Auto Control Thread
def auto_control_logic():
    latest = mc.get(KEY_LATEST)
    mode = mc.get(MODE_KEY) or "AUTO"
    if not latest or mode != "AUTO":
        return
    try:
        soil_adc = float(latest.get("soil_moist", 0))
        moisture_percent = max(0, min(100, 100 - ((soil_adc - ADC_WET) / (ADC_DRY - ADC_WET) * 100)))
        current_status = mc.get(RELAY_STATUS) or "OFF"
        if moisture_percent < THRESHOLD_SOIL and current_status != "ON":
            mc.set(RELAY_STATUS, "ON")
            log_relay_event("ON", "auto")
            publish_relay_status("ON")
        elif moisture_percent >= THRESHOLD_SOIL and current_status != "OFF":
            mc.set(RELAY_STATUS, "OFF")
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
    app.run(host="0.0.0.0", port=5000)
