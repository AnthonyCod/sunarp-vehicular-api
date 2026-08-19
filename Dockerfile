# Usar una imagen oficial de Python ligera
FROM python:3.11-slim

# Instalar Tesseract OCR, XVFB y las librerías gráficas requeridas para Chromium
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    xvfb \
    libgconf-2-4 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libharfbuzz0b \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar e instalar las dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Descargar los binarios del navegador modificado de Scrapling (Chromium)
RUN patchright install chromium

# Copiar el código del proyecto
COPY . .

# Exponer el puerto por defecto de FastAPI
EXPOSE 8000

# Ejecutar el servidor FastAPI dentro de la pantalla gráfica virtual de XVFB
CMD ["xvfb-run", "--server-args=-screen 0 1280x1024x24", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
