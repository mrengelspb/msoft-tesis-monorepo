import paho.mqtt.client as mqtt
import json
import time

# --- Constantes que DEBEN COINCIDIR con tu publicador ---
#MQTT_BROKER = "broker.hivemq.com"
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "msoft/msrr/zone_change"
# -----------------------------------------------------

# Callback: Se ejecuta cuando el cliente se conecta exitosamente al broker
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"¡Conectado exitosamente al broker {MQTT_BROKER}!")
        
        # Suscribirse al topic DESPUÉS de conectar es la mejor práctica
        client.subscribe(MQTT_TOPIC)
        print(f"Suscrito al topic: {MQTT_TOPIC}")
    else:
        print(f"Error de conexión. Código: {rc}")

# Callback: Se ejecuta CADA VEZ que llega un mensaje en un topic al que estamos suscritos
def on_message(client, userdata, msg):
    print(f"\n¡Mensaje recibido! Topic: {msg.topic}")
    
    try:
        # 1. Decodificar el payload (viene en bytes) a un string UTF-8
        payload_str = msg.payload.decode('utf-8')
        
        # 2. Convertir el string JSON de vuelta a un diccionario de Python
        data = json.loads(payload_str)
        
        # 3. ¡Usar los datos!
        print("--- 🚨 Alerta de Cambio de Zona 🚨 ---")
        print(f"  Paciente:   {data.get('user_id')}")
        print(f"  BPM actual: {data.get('bpm_actual')}")
        print(f"  Zona movida: {data.get('zona_anterior')} -> {data.get('zona_nueva')}")
        print(f"  Timestamp:  {time.ctime(data.get('timestamp'))}") # Formatea la hora
        print("--------------------------------------")

    except json.JSONDecodeError:
        print(f"Error: No se pudo decodificar el JSON. Payload crudo: {msg.payload}")
    except Exception as e:
        print(f"Error procesando el mensaje: {e}")

# --- Configuración principal del suscriptor ---

# 1. Crear el cliente
# Usamos v2 para ser consistentes con tu publicador
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

# 2. Asignar las funciones de callback
client.on_connect = on_connect
client.on_message = on_message

# 3. Conectar al broker
try:
    print(f"Intentando conectar a {MQTT_BROKER}...")
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
except Exception as e:
    print(f"No se pudo conectar al broker: {e}")
    exit() # Salir si no nos podemos conectar

# 4. Iniciar el bucle de escucha
# loop_forever() es un bucle bloqueante que mantiene el script vivo
# escuchando mensajes. No consume casi nada de CPU.
print("Iniciando bucle de escucha. Presiona CTRL+C para detener.")
try:
    client.loop_forever()
except KeyboardInterrupt:
    print("\nDeteniendo cliente...")
    client.disconnect()