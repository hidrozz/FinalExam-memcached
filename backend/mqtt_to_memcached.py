import paho.mqtt.client as mqtt
from memcache_wrapper import set, push_to_list
from datetime import datetime
import json

MQTT_HOST = "103.23.198.211"
MQTT_PORT = 1883
MQTT_USER = "myuser"
MQTT_PASS = "tugasakhir"
MQTT_TOPIC = "sensors/report"

def on_connect(client, userdata, flags, rc):
    print("[MQTT] Connected:", rc)
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        data["timestamp"] = datetime.now().isoformat()

        set("latest_sensor_data", data)
        push_to_list("sensor_data_log", data)

        print("[MQTT -> Memcached] Updated data")

    except Exception as e:
        print("[MQTT ERROR]", e)

client = mqtt.Client()
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_HOST, MQTT_PORT, 60)
client.loop_forever()
