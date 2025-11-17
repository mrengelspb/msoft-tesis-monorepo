# Usa una imagen base de Python
FROM python:3.10-slim

WORKDIR /app

# Instala dependencias del sistema (para brainflow y pyqt)
RUN apt-get update && apt-get install -y \
    libopencv-dev \
    python3-pyqt5 \
    && rm -rf /var/lib/apt/lists/*

# Instala las bibliotecas de Python
# (Crea un archivo requirements.txt con numpy, paho-mqtt, brainflow)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el código fuente del servicio
COPY main.py .
COPY brainflow_handler.py .
COPY data_analysis.py .
COPY mqtt_handler.py .

# Comando para ejecutar el servicio
CMD ["python3", "main.py"]