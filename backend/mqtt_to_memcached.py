import paho.mqtt.client as mqtt
import memcache
import json
from datetime import datetime

MQTT_HOST = "103.76.120.64"
MQTT_PORT = 1883
MQTT_USER = "myuser"
MQTT_PASS = "tugasakhir"
MQTT_TOPIC = "sensors/report"

mc = memcache.Client(["127.0.0.1:11211"])
mc.behaviors = {"tcp_nodelay": True, "ketama": True}

KEY_DATA = "memcached:latest_sensor_data"
KEY_LOG = "memcached:sensor_data_log"
MAX_LOG = 100

def on_connect(client, userdata, flags, rc):
    print("[MQTT] Connected with result code", rc)
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        data["timestamp"] = datetime.now().isoformat()

        mc.set(KEY_DATA, json.dumps(data), time=0)

        logs = mc.get(KEY_LOG)
        if not isinstance(logs, list):
            logs = []
        logs.insert(0, data)
        mc.set(KEY_LOG, logs[:MAX_LOG], time=0)

        print(f"[MQTT->Memcached] Stored: {data}")

    except Exception as e:
        print("[ERROR] Failed to handle message:", e)

client = mqtt.Client()
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_HOST, MQTT_PORT, 60)
client.loop_forever()
