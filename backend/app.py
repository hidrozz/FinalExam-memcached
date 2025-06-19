from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import memcache
import json
import time
from datetime import datetime
import threading
import paho.mqtt.publish as publish
from log_writer import log_latency

app = Flask(__name__)
CORS(app)

# Setup Memcached
mc = memcache.Client(["127.0.0.1:11211"])
mc.behaviors = {"tcp_nodelay": True, "ketama": True}

KEY_LOG = "sensor_data_log_m"
RELAY_LOG = "relay_log_m"
MAX_LOG = 100
MAX_LOG_RELAY = 100

THRESHOLD_SOIL = 50
ADC_DRY = 3000
ADC_WET = 1000

# MQTT publisher
def publish_relay_status(status):
    publish.single("sensors/moist_threshold", payload=status,
        hostname="103.49.239.211", port=1883,
        auth={'username': 'myuser', 'password': 'tugasakhir'}
    )

# Log relay event
def log_relay_event(status, source):
    event = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "source": source
    }
    try:
        logs = mc.get(RELAY_LOG) or []
        logs.insert(0, event)
        mc.set(RELAY_LOG, logs[:MAX_LOG_RELAY])
    except:
        mc.set(RELAY_LOG, [event])

@app.route("/api/status")
def get_status():
    start = time.time()
    latest = mc.get("latest_sensor_data_m")
    print("[DEBUG] Latest from Memcached:", latest)
    relay_status = mc.get("relay_status_m") or "OFF"
    mode = mc.get("mode_m") or "AUTO"

    if latest:
        data = json.loads(latest)
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
    end = time.time()
    log_latency("memcached", "-", "-", "-", f"{(end-start)*1000:.2f}ms")
    return jsonify(data)

@app.route("/api/relay-toggle", methods=["POST"])
def toggle_relay():
    current = mc.get("relay_status_m") or "OFF"
    new_status = "OFF" if current == "ON" else "ON"
    mc.set("relay_status_m", new_status)
    log_relay_event(new_status, "manual")
    publish_relay_status(new_status)
    return jsonify({"relay_status": new_status})

@app.route("/api/auto-mode-toggle", methods=["POST"])
def toggle_auto_mode():
    current = mc.get("mode_m") or "AUTO"
    new_mode = "MANUAL" if current == "AUTO" else "AUTO"
    mc.set("mode_m", new_mode)
    return jsonify({"mode": new_mode})

@app.route("/api/chart-data")
def chart_data():
    raw_data = mc.get(KEY_LOG) or []
    data = [d for d in raw_data if "timestamp" in d]
    labels = [datetime.fromisoformat(d["timestamp"]).strftime("%H:%M:%S") for d in data]
    soil = [d.get("soil_moist", 0) for d in data]
    temp = [d.get("env_temp", 0) for d in data]
    hum = [d.get("env_hum", 0) for d in data]
    ph = [d.get("soil_temp", 0) for d in data]
    return jsonify({
        "labels": labels[::-1], "soil": soil[::-1], "temperature": temp[::-1],
        "humidity": hum[::-1], "ph": ph[::-1]
    })

@app.route("/api/relay-log")
def get_relay_log():
    raw_logs = mc.get(RELAY_LOG) or []
    return jsonify(raw_logs)

@app.route("/")
def serve_dashboard():
    return send_from_directory('../frontend', 'index.html')

@app.route("/css/<path:filename>")
def serve_css(filename):
    return send_from_directory('../frontend/css', filename)

@app.route("/js/<path:filename>")
def serve_js(filename):
    return send_from_directory('../frontend/js', filename)

# === AUTO CONTROL LOOP ===
def auto_control_logic():
    latest = mc.get("latest_sensor_data_m")
    mode = mc.get("mode_m") or "AUTO"
    if not latest or mode != "AUTO":
        return
    try:
        data = json.loads(latest)
        soil_adc = float(data.get("soil_moist", 0))
        moisture_percent = max(0, min(100, 100 - ((soil_adc - ADC_WET) / (ADC_DRY - ADC_WET) * 100)))
        current_status = mc.get("relay_status_m") or "OFF"
        if moisture_percent < THRESHOLD_SOIL and current_status != "ON":
            mc.set("relay_status_m", "ON")
            log_relay_event("ON", "auto")
            publish_relay_status("ON")
        elif moisture_percent >= THRESHOLD_SOIL and current_status != "OFF":
            mc.set("relay_status_m", "OFF")
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
    app.run(host="0.0.0.0", port=5050)
