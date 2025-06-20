# backend/memcache_wrapper.py

import memcache
import json

# Koneksi ke Memcached (pastikan memcached aktif dan port benar)
client = memcache.Client([("localhost", 11211)])

# Helper untuk key standar
KEY_SENSOR_DATA = "latest_sensor_data_m"
KEY_RELAY_STATUS = "relay_status_m"
KEY_MODE = "mode_m"
KEY_LOG = "sensor_data_log_m"
KEY_RELAY_LOG = "relay_log_m"

MAX_LOG = 100
MAX_RELAY_LOG = 100

# Fungsi ambil data sensor terakhir
def get_latest_sensor_data():
    raw = client.get(KEY_SENSOR_DATA)
    return json.loads(raw) if raw else None

# Simpan data sensor terbaru
def set_latest_sensor_data(data):
    client.set(KEY_SENSOR_DATA, json.dumps(data))

# Ambil/simpan status relay
def get_relay_status():
    return client.get(KEY_RELAY_STATUS) or "OFF"

def set_relay_status(status):
    client.set(KEY_RELAY_STATUS, status)

# Ambil/simpan mode auto/manual
def get_mode():
    return client.get(KEY_MODE) or "AUTO"

def set_mode(mode):
    client.set(KEY_MODE, mode)

# Simpan log sensor data
def push_sensor_log(data):
    raw = client.get(KEY_LOG)
    logs = json.loads(raw) if raw else []
    logs.insert(0, data)
    logs = logs[:MAX_LOG]
    client.set(KEY_LOG, json.dumps(logs))

def get_sensor_logs():
    raw = client.get(KEY_LOG)
    return json.loads(raw) if raw else []

# Simpan log event relay (manual/auto)
def push_relay_log(event):
    raw = client.get(KEY_RELAY_LOG)
    logs = json.loads(raw) if raw else []
    logs.insert(0, event)
    logs = logs[:MAX_RELAY_LOG]
    client.set(KEY_RELAY_LOG, json.dumps(logs))

def get_relay_logs():
    raw = client.get(KEY_RELAY_LOG)
    return json.loads(raw) if raw else []
