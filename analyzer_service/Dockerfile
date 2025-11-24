# ==========================================
# ETAPA 1: Compilador (Builder)
# ==========================================
FROM python:3.10-slim as builder

# Instalamos herramientas de compilación
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    swig \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# 1. Copiamos BrainFlow desde la raíz del monorepo
COPY brainflow /build/brainflow

# 2. Modificamos el setup.py para la compilacion de wrapper de BRAINFLOW
WORKDIR /build/brainflow/python_package
RUN sed -i 's/name="brainflow"/name="brainflow-msoft-modificadaparatesis"/g' setup.py && \
    sed -i 's/version=.*,/version="1.0.1",/g' setup.py

# 3. Compilamos el núcleo C++ (CORREGIDO: AÑADIDOS LOS FLAGS PARA DESACTIVAR EXTRAS)
WORKDIR /build/brainflow
RUN mkdir build && cd build && \
    cmake -DCMAKE_INSTALL_PREFIX=/install \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_PYTHON=ON \
    -DBUILD_JAVA=OFF \
    -DBUILD_CSHARP=OFF \
    -DBUILD_R=OFF \
    -DBUILD_MATLAB=OFF \
    -DBUILD_JULIA=OFF \
    -DBUILD_ONNX=OFF \
    .. && \
    make -j$(nproc) && \
    make install

# 4. Generamos el wheel (.whl)
WORKDIR /build/brainflow/python_package
RUN python3 setup.py bdist_wheel

# ==========================================
# ETAPA 2: Imagen Final (Runner)
# ==========================================
FROM python:3.10-slim

WORKDIR /app

# Librerías de sistema básicas
RUN apt-get update && apt-get install -y \
    libopencv-dev \
    && rm -rf /var/lib/apt/lists/*

# 1. Instalamos BrainFlow compilado desde la Etapa 1
COPY --from=builder /build/brainflow/python_package/dist/*.whl /tmp/
RUN pip install /tmp/*.whl

# 2. Instalamos dependencias del servicio
COPY analyzer_service/requirements.txt .
# Eliminamos brainflow del requirements.txt para no sobrescribir lo compilado
RUN sed -i '/brainflow/d' requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

# 3. Copiamos el código fuente
COPY analyzer_service/*.py .

# Comando de arranque
CMD ["python3", "-u", "main.py"]