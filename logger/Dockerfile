# ==========================================
# ETAPA 1: Compilación de Go
# ==========================================
FROM golang:alpine AS builder

WORKDIR /app

# Copiamos el código fuente
COPY logger/main.go .

# Inicializamos el módulo y descargamos dependencias
# (Esto crea el go.mod y go.sum si no existen)
RUN go mod init logger_service || true
RUN go mod tidy

# Compilamos el binario estático
RUN CGO_ENABLED=0 GOOS=linux go build -o logger_app main.go

# ==========================================
# ETAPA 2: Imagen Final Ligera
# ==========================================
FROM alpine:latest

WORKDIR /root/

# Copiamos el binario compilado
COPY --from=builder /app/logger_app .

# Ejecutamos
CMD ["./logger_app"]