import paho.mqtt.client as mqtt
import json
import time
import sys

# Configuración
MQTT_BROKER = "localhost"
TOPIC_DATA = "msoft/msrr/debug_ecg_data"

received_chunks = 0
total_points = 0
collected_data = []

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"--> Conectado. Escuchando {TOPIC_DATA} por 5 segundos...")
        client.subscribe(TOPIC_DATA, qos=0)
    else:
        print(f"Error conexión: {rc}")
        sys.exit(1)

def on_message(client, userdata, msg):
    global received_chunks, total_points, collected_data
    try:
        payload = json.loads(msg.payload.decode())
        chunk = payload.get("ecg_data", [])
        
        # Guardamos estadísticas
        chunk_len = len(chunk)
        received_chunks += 1
        total_points += chunk_len
        
        # Guardamos los datos reales
        collected_data.extend(chunk)
        
        print(f"   [Chunk #{received_chunks}] Recibidos {chunk_len} puntos", end="\r")
    except Exception as e:
        print(e)

# --- Main ---
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

try:
    client.connect(MQTT_BROKER, 1883, 60)
    client.loop_start()
except Exception as e:
    print(f"No se pudo conectar: {e}")
    sys.exit(1)

# Esperar 5 segundos para recolectar datos
time.sleep(5)
client.loop_stop()
client.disconnect()

# --- REPORTE ---
print("\n\n" + "="*40)
print("       REPORTE DE DIAGNÓSTICO       ")
print("="*40)
print(f"Tiempo de captura:    5 segundos")
print(f"Chunks recibidos:     {received_chunks}")
print(f"Puntos totales:       {total_points}")

# Cálculo de frecuencia de muestreo real aproximada
fs_real = total_points / 5.0
print(f"Frecuencia (aprox):   {fs_real:.2f} Hz (Esperado: ~250 Hz)")

avg_chunk_size = total_points / received_chunks if received_chunks > 0 else 0
print(f"Tamaño prom. Chunk:   {avg_chunk_size:.2f} puntos (Esperado: 12-13)")

print("\n" + "-"*40)
print("--- DATOS PARA PEGAR EN EL CHAT ---")
print("-"*40)
# Imprimimos los primeros 50 puntos para ver la forma de onda y el formato
print(json.dumps(collected_data[:50]))
print("-"*40)

if total_points == 0:
    print("\n⚠️ ALERTA: No se recibieron datos. Revisa si el Docker está enviando.")
elif avg_chunk_size > 500:
    print("\n⚠️ ALERTA: Los chunks son gigantes. El 'slicing' en main.py no está funcionando.")
elif avg_chunk_size < 2:
    print("\n⚠️ ALERTA: Los chunks son muy pequeños. Sobrecarga de red posible.")
else:
    print("\n✅ El flujo de datos parece correcto en tamaño y frecuencia.")