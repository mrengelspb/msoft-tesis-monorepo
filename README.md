# (1) Para compilar la libreria de BRAINFLOW:
cd D:\SolucionesPlanB\SW\MAXV3\msoft-tesis-monorepo\brainflow\build
cmake -G "Visual Studio 17 2022" -A x64 ..
cmake --build . --config Release
# (2) Para reinstalar el paquete de python
cd D:\SolucionesPlanB\SW\MAXV3\brainflow\brainflow\python_package
python -m pip install -e .

# ###########################################################################
# Para ver de donde esta corriendo la libreria de BRAINFLOW
# Ejecuta un pequeño script de Python DENTRO del contenedor
docker exec -it python-analyzer-service python -c "import brainflow; import os; print(f'\n[ORIGEN] La libreria se carga desde: {os.path.dirname(brainflow.__file__)}')"

# ###########################################################################

# Para montar todos los servicios:
docker-compose up -d
docker-compose up --build

# ###########################################################################
### Verificacion de origen de libreria

  **Prueba de Origen:**
    docker exec -it python-analyzer-service python -c "import brainflow; import os; print(f'Ubicación: {os.path.dirname(brainflow.__file__)}'); print(f'Versión: {brainflow.__version__}')"
   
  **Prueba de Instalación:**
    docker exec -it python-analyzer-service pip list | grep brainflow
