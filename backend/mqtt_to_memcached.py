import paho.mqtt.client as mqtt
from pymemcache.client.base import Client
import json
from datetime import datetime

MQTT_HOST = "103.23.198.211"
MQTT_PORT = 1883
MQTT_USER = "myuser"
MQTT_PASS = "tugasakhir"
MQTT_TOPIC = "sensors/report"

m = Client(('localhost', 11211))
KEY_LOG = "sensor_data_log"
MAX_LOG = 100

def get_list(key):
    raw = m.get(key)
    if raw:
        try:
            return json.loads(raw)
        except:
            return []
    return []

def push_list(key, item, maxlen):
    data = get_list(key)
    data.insert(0, item)
    if len(data) > maxlen:
        data = data[:maxlen]
    m.set(key, json.dumps(data))

def on_connect(client, userdata, flags, rc):
    print("[MQTT] Connected with result code", rc)
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        data["timestamp"] = datetime.now().isoformat()
        m.set("latest_sensor_data", json.dumps(data))
        push_list(KEY_LOG, data, MAX_LOG)
        print(f"[MQTT->Memcached] Stored: {data}")
    except Exception as e:
        print("[ERROR] Failed to handle message:", e)

client = mqtt.Client()
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_HOST, MQTT_PORT, 60)
client.loop_forever()