# Uso una imagen base de Python 3.10 ligera
FROM python:3.10-slim

# Establezco mi directorio de trabajo dentro del contenedor
WORKDIR /app

# Actualizo los repositorios e instalo dependencias del sistema necesarias 
# para Brainflow (OpenCV libs) y PyQt
RUN apt-get update && apt-get install -y \
    libopencv-dev \
    python3-pyqt5 \
    && rm -rf /var/lib/apt/lists/*

# Copio mi archivo de requerimientos primero para aprovechar la caché de Docker
COPY requirements.txt .

# Instalo las bibliotecas de Python listadas
RUN pip install --no-cache-dir -r requirements.txt

# Copio el resto de mi código fuente al contenedor
COPY main.py .
COPY brainflow_handler.py .
COPY data_analysis.py .
COPY mqtt_handler.py .

# Defino el comando que ejecutará mi servicio cuando arranque el contenedor
CMD ["python3", "main.py"]