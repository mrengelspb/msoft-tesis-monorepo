# Para compilar la libreria de BRAINFLOW:
# (1)
cd D:\SolucionesPlanB\SW\MAXV3\brainflow\build
cmake -G "Visual Studio 17 2022" -A x64 ..
cmake --build . --config Release
# (2)
Para reinstalar el paquete de python
cd D:\SolucionesPlanB\SW\MAXV3\brainflow\brainflow\python_package
python -m pip install -e .

# ###########################################################################


# Para montar todos los servicios:
# en el path razi ejecutar:
docker-compose up -d