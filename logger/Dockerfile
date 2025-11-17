# Etapa 1: Compilación
FROM golang:1.24-alpine AS builder
WORKDIR /app

# Copia los archivos de dependencias y las descarga
COPY go.mod go.sum ./
RUN go mod download

# Copia el código fuente y compila
COPY *.go .
RUN go build -o /logger-service .

# Etapa 2: Ejecución (imagen ligera)
FROM alpine:latest
WORKDIR /root/
# Copia el binario compilado de la etapa anterior
COPY --from=builder /logger-service .

# Comando para correr el servicio
CMD ["./logger-service"]