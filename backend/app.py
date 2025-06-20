from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import threading
import json
import time
from datetime import datetime
import paho.mqtt.publish as publish

from memcache_wrapper import (
    get_latest_sensor_data, set_latest_sensor_data,
    get_mode, set_mode,
    get_relay_status, set_relay_status,
    log_relay_event, get_sensor_logs, get_relay_logs
)
from log_writer import log_latency

app = Flask(__name__)
CORS(app)

THRESHOLD_SOIL = 50
ADC_DRY = 3000
ADC_WET = 1000

def publish_relay_status(status):
    publish.single("sensors/moist_threshold", payload=status,
        hostname="103.76.120.64", port=1883,
        auth={'username': 'myuser', 'password': 'tugasakhir'}
    )

@app.route("/api/status")
def api_status():
    start = time.time()
    data = get_latest_sensor_data()
    relay_status = get_relay_status() or "OFF"
    mode = get_mode() or "AUTO"

    if data:
        try:
            soil_adc = float(data.get("soil_moist", 0))
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
    end = time.time()
    log_latency("memcached", "-", "-", "-", f"{(end-start)*1000:.2f}ms")
    return jsonify(data)

@app.route("/api/relay-toggle", methods=["POST"])
def toggle_relay():
    current = get_relay_status() or "OFF"
    new_status = "OFF" if current == "ON" else "ON"
    set_relay_status(new_status)
    log_relay_event(new_status, "manual")
    publish_relay_status(new_status)
    return jsonify({"relay_status": new_status})

@app.route("/api/auto-mode-toggle", methods=["POST"])
def toggle_mode():
    current = get_mode() or "AUTO"
    new_mode = "MANUAL" if current == "AUTO" else "AUTO"
    set_mode(new_mode)
    return jsonify({"mode": new_mode})

@app.route("/api/chart-data")
def chart_data():
    logs = get_sensor_logs()
    labels, soil, temp, hum, ph = [], [], [], [], []
    for d in reversed(logs):
        try:
            dt = json.loads(d)
            labels.append(datetime.fromisoformat(dt["timestamp"]).strftime("%H:%M:%S"))
            soil.append(dt.get("soil_moist", 0))
            temp.append(dt.get("env_temp", 0))
            hum.append(dt.get("env_hum", 0))
            ph.append(dt.get("soil_temp", 0))
        except:
            continue
    return jsonify({
        "labels": labels, "soil": soil, "temperature": temp,
        "humidity": hum, "ph": ph
    })

@app.route("/api/relay-log")
def get_relay():
    logs = get_relay_logs()
    return jsonify([json.loads(l) for l in logs])

@app.route("/")
def index():
    return send_from_directory('../frontend', 'index.html')

@app.route("/css/<path:filename>")
def css(filename):
    return send_from_directory('../frontend/css', filename)

@app.route("/js/<path:filename>")
def js(filename):
    return send_from_directory('../frontend/js', filename)

def auto_control_logic():
    data = get_latest_sensor_data()
    mode = get_mode() or "AUTO"
    if not data or mode != "AUTO":
        return
    try:
        soil_adc = float(data.get("soil_moist", 0))
        moisture_percent = max(0, min(100, 100 - ((soil_adc - ADC_WET) / (ADC_DRY - ADC_WET) * 100)))
        current_status = get_relay_status() or "OFF"
        if moisture_percent < THRESHOLD_SOIL and current_status != "ON":
            set_relay_status("ON")
            log_relay_event("ON", "auto")
            publish_relay_status("ON")
        elif moisture_percent >= THRESHOLD_SOIL and current_status != "OFF":
            set_relay_status("OFF")
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
