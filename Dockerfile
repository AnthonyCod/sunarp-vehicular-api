# Usar una imagen oficial de Python ligera
FROM python:3.11-slim

# Instalar Tesseract OCR, XVFB y tini (init real para manejar señales
# correctamente: xvfb-run se cuelga si corre directo como PID 1 en Docker)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    xvfb \
    tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar e instalar las dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Descargar el navegador modificado de Scrapling (Chromium) e instalar sus
# librerías del sistema automáticamente según la versión de Debian de la imagen
# (evita mantener a mano una lista de paquetes que se desactualiza entre
# versiones de Debian, como pasaba con libgconf-2-4).
RUN patchright install --with-deps chromium

# Copiar el código del proyecto
COPY . .

# Exponer el puerto por defecto de FastAPI
EXPOSE 8000

# tini como PID 1 reenvía señales correctamente al proceso real
ENTRYPOINT ["/usr/bin/tini", "--"]

# Ejecutar el servidor FastAPI dentro de la pantalla gráfica virtual de XVFB
CMD ["xvfb-run", "--server-args=-screen 0 1280x1024x24", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
