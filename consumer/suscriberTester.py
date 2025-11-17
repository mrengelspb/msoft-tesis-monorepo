import paho.mqtt.client as mqtt
import json
import time

# ==========================================================================
# Datos para el conexion con MQTT
# ==========================================================================
MQTT_BROKER = "localhost" 
MQTT_PORT = 1883
MQTT_TOPIC = "msoft/msrr/zone_change" # Tópico
# ==========================================================================
# Funcion de conexion al broker
# ==========================================================================
# Aquí defino qué hacer cuando logro conectarme al broker
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"¡Me conecté exitosamente al broker {MQTT_BROKER}!")
        
        # Una vez conectado, le digo al broker que me quiero suscribir a este tópico
        client.subscribe(MQTT_TOPIC)
        print(f"Me suscribí al topic: {MQTT_TOPIC}")
    else:
        print(f"No me pude conectar. Código: {rc}")

# Esta es la función más importante: se ejecuta CADA VEZ que recibo un mensaje
def on_message(client, userdata, msg):
    print(f"\n¡Recibí un mensaje! Topic: {msg.topic}")
    
    try:
        # 1. Decodifico el payload (que viene en bytes) a un string
        payload_str = msg.payload.decode('utf-8')
        
        # 2. Convierto ese string (que es un JSON) a un diccionario de Python
        data = json.loads(payload_str)
        
        # 3. ¡Ahora uso los datos de ese diccionario!
        print("--- 🚨 Alerta de Cambio de Zona 🚨 ---")
        print(f" 	Paciente:   {data.get('user_id')}")
        print(f" 	BPM actual: {data.get('bpm_actual')}")
        print(f" 	Zona movida: {data.get('zona_anterior')} -> {data.get('zona_nueva')}")
        # Uso time.ctime() para que la fecha (timestamp) sea legible
        print(f" 	Timestamp:  {time.ctime(data.get('timestamp'))}") 
        print("--------------------------------------")

    except json.JSONDecodeError:
        print(f"Error: El mensaje no era un JSON válido. Payload crudo: {msg.payload}")
    except Exception as e:
        print(f"Error procesando el mensaje: {e}")

# --- Aquí empieza la configuración principal de mi script ---

# 1. Creo mi cliente MQTT (usando la API v2)
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

# 2. Le asigno las funciones que definí arriba (on_connect y on_message)
client.on_connect = on_connect
client.on_message = on_message

# 3. Intento conectarme al broker
try:
    print(f"Intentando conectar a {MQTT_BROKER}...")
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
except Exception as e:
    print(f"No se pudo conectar al broker: {e}")
    exit() # Si no me puedo conectar, cierro el script

# 4. Inicio el bucle de escucha
# loop_forever() mantiene mi script vivo, escuchando mensajes.
# Es un bucle "bloqueante", por lo que el script no terminará.
print("Iniciando bucle de escucha. Presiona CTRL+C para detener.")
try:
    client.loop_forever()
except KeyboardInterrupt:
    print("\nDeteniendo cliente...")
    client.disconnect()