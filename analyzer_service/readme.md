Para probar que la imagen este bien en el docker compilado usar:

docker run -it --rm `
  -v "${PWD}:/app" `
  -w /app `
  brainflow-msoft-msrr:v2 `
  python tester_docker.py