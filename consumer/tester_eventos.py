import paho.mqtt.client as mqtt
import json
import time
import sys
from datetime import datetime

MQTT_BROKER = "localhost"
TOPIC_ZONE = "msoft/msrr/zone_change"

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] CONECTADO. Esperando cambios de zona...")
        client.subscribe(TOPIC_ZONE, qos=1)
    else:
        print(f"Error conexión: {rc}")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        
        # Extraigo datos
        old_z = payload.get('zona_anterior')
        new_z = payload.get('zona_nueva')
        bpm = payload.get('bpm_actual')
        ts_servidor = payload.get('timestamp')
        
        # Hora local de recepción
        hora_local = datetime.now().strftime('%H:%M:%S')
        
        print(f"🔔 [{hora_local}] EVENTO RECIBIDO")
        print(f"   Cambio: {old_z} -> {new_z}")
        print(f"   BPM:    {bpm:.2f}")
        print(f"   Delay:  {time.time() - ts_servidor:.4f} seg")
        print("-" * 30)
        
    except Exception as e:
        print(f"Error decodificando: {e}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

try:
    client.connect(MQTT_BROKER, 1883, 60)
    client.loop_forever()
except KeyboardInterrupt:
    print("\nSaliendo...")
except Exception as e:
    print(f"No se pudo conectar: {e}")