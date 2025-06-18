from pymemcache.client.base import Client
import json

client = Client(('localhost', 11211))

def get(key):
    value = client.get(key)
    return value.decode() if value else None

def set(key, value, expire=300):
    if isinstance(value, dict):
        value = json.dumps(value)
    client.set(key, value, expire)

def push_to_list(key, item, max_length=100):
    list_raw = get(key)
    try:
        data = json.loads(list_raw) if list_raw else []
        data.insert(0, item)
        if len(data) > max_length:
            data = data[:max_length]
        client.set(key, json.dumps(data))
    except:
        client.set(key, json.dumps([item]))

def get_list(key):
    list_raw = get(key)
    try:
        return json.loads(list_raw) if list_raw else []
    except:
        return []
