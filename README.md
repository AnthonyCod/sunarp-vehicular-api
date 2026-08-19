# Microservicio de Consulta Vehicular SUNARP

API REST desarrollada en **Python / FastAPI** que automatiza la consulta pública de información técnica y de propietarios de vehículos registrados en la **SUNARP** (Superintendencia Nacional de los Registros Públicos - Perú), a partir del número de placa (6 caracteres alfanuméricos).

El portal oficial de SUNARP no expone una API pública: los datos solo están disponibles a través de un formulario web protegido por Cloudflare Turnstile, y la respuesta del vehículo llega como una **imagen** (no como texto/JSON). Este proyecto resuelve ambos problemas:

1.  **Automatiza el navegador** para completar el formulario y resolver el desafío de Cloudflare.
2.  **Captura la petición XHR** interna que contiene la imagen en base64 con los datos.
3.  **Aplica OCR** (Tesseract) sobre esa imagen y parsea el texto resultante en un JSON limpio y estructurado.

> ⚠️ **Uso responsable**: este proyecto consulta información pública expuesta por SUNARP a través de su propio portal, replicando la interacción de un usuario real. Úsalo de forma razonable (sin sobrecargar el servicio) y respetando los términos de uso del portal oficial.

---

## 🚀 Características clave

*   **Evasión de Cloudflare Turnstile:** usa **Scrapling** (basado en el motor sigiloso `patchright`, un fork de Playwright) para resolver los desafíos de seguridad del portal.
*   **Procesamiento OCR local:** decodifica la imagen PNG en base64 devuelta por SUNARP y extrae el texto con **Tesseract OCR**.
*   **Extracción estructurada:** parser basado en expresiones regulares que limpia y formatea los datos del OCR (incluye propietarios con múltiples líneas).
*   **Reintentos automáticos:** hasta 3 intentos por placa ante fallos transitorios (timeouts, Turnstile no resuelto a tiempo, etc.).
*   **Dockerizado y listo para producción:** usa **XVFB** (pantalla virtual en memoria, necesaria porque el navegador corre en modo visible) y **Tini** como init process para el manejo correcto de señales dentro del contenedor.

---

## 📁 Estructura del proyecto

```
sunarp/
├── app/
│   ├── main.py                      # Definición de la API y endpoints (FastAPI)
│   ├── schemas.py                   # Modelos Pydantic de request/response
│   ├── config.py                    # Carga de configuración desde variables de entorno
│   └── automation/
│       ├── browser_manager.py       # Ciclo de vida de la sesión del navegador (Scrapling)
│       └── vehicular_service.py     # Flujo de consulta, resolución de Turnstile y OCR
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🛠️ Requisitos previos

1.  **Python 3.11+** — en macOS, el `python3` del sistema (`/usr/bin/python3`) suele ser una versión muy vieja (3.9) que no cumple este requisito; instalá una versión reciente con `brew install python@3.11` y usala explícitamente al crear el entorno virtual (ver paso 2).
2.  **Tesseract OCR** (motor de reconocimiento de texto):
    *   **macOS (Homebrew):**
        ```bash
        brew install tesseract
        ```
    *   **Linux (Ubuntu/Debian):**
        ```bash
        sudo apt-get update && sudo apt-get install -y tesseract-ocr
        ```
    *   **Windows:** descarga el instalador desde [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) y agrégalo al `PATH`.

---

## 💻 Instalación y ejecución local

### 1. Clonar el repositorio
```bash
git clone <url-del-repositorio>
cd sunarp
```

### 2. Crear y activar el entorno virtual de Python
```bash
# macOS/Linux: usá explícitamente python3.11 (no "python3" a secas), para
# evitar terminar con el Python viejo del sistema:
python3.11 -m venv .venv
source .venv/bin/activate

# Windows (Command Prompt):
# python -m venv .venv
# .venv\Scripts\activate.bat
```

> [!TIP]
> Si `pip install` más abajo falla con algo como `No matching distribution found for scrapling[fetchers]`, es señal de que el venv se creó con un Python muy viejo. Corré `python3 --version` con el venv activado: si no es 3.11+, borrá `.venv` y repetí este paso con `python3.11 -m venv .venv`.

### 3. Instalar las dependencias del proyecto
```bash
pip install -r requirements.txt
```

### 4. Instalar el navegador del motor sigiloso
Descarga la versión adaptada de Chromium y sus dependencias del sistema:
```bash
patchright install --with-deps chromium
```

### 5. Configurar las variables de entorno
Copia el archivo de ejemplo y ajústalo según tu entorno:
```bash
cp .env.example .env
```

| Variable                   | Descripción                                                                 | Valor por defecto |
|-----------------------------|------------------------------------------------------------------------------|--------------------|
| `HEADLESS_MODE`             | `true` para correr el navegador sin interfaz (producción); `false` para verlo (desarrollo/debug) | `true`             |
| `MAX_CONCURRENT_SESSIONS`   | Número máximo de consultas ejecutándose en paralelo | `3` (`1` en `.env.example`) |
| `OPERATION_TIMEOUT`         | Timeout en segundos para cada operación de consulta                        | `30`               |
| `OUTBOUND_PROXY`            | (Opcional) proxy saliente a usar en las peticiones del navegador           | *(sin proxy)*      |

> [!IMPORTANT]
> Para desarrollo local, se recomienda `HEADLESS_MODE=false`. En modo headless, Cloudflare Turnstile puede detectar la automatización con mayor facilidad y bloquear la petición.

### 6. Ejecutar el servidor de desarrollo
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

El servidor queda escuchando en `http://127.0.0.1:8000`. La documentación interactiva (Swagger UI) está disponible en [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs), donde también se pueden probar los endpoints directamente desde el navegador.

---

## 📡 Uso de la API

### Consulta por placa — `GET /api/v1/vehiculo/{placa}`

Consulta los datos de una sola placa. La búsqueda es síncrona: la respuesta se devuelve una vez completado el proceso de scraping + OCR (puede tardar varios segundos).

```bash
curl http://127.0.0.1:8000/api/v1/vehiculo/ABC123
```

**Respuesta exitosa (`200 OK`):** *(ejemplo ilustrativo, no corresponde a una placa ni persona real)*
```json
{
  "success": true,
  "placa": "ABC123",
  "data": {
    "placa": "ABC123",
    "serie": "XXXXXXXXXXXXXXXXX",
    "vin": "XXXXXXXXXXXXXXXXX",
    "motor": "XXXXXXXXXXXXXX",
    "color": "BLANCO",
    "marca": "CHEVROLET",
    "modelo": "SPARK LITE",
    "placa_vigente": "ABC123",
    "placa_anterior": "NINGUNA",
    "estado": "EN CIRCULACION",
    "anotaciones": "NINGUNA",
    "sede": "LIMA",
    "ano_modelo": "2014",
    "propietarios": [
      "APELLIDOS NOMBRES, EJEMPLO UNO"
    ]
  },
  "message": "Consulta procesada exitosamente."
}
```

**Errores:**
*   `400 Bad Request`: la placa no tiene 6 caracteres alfanuméricos.
*   `200 OK` con `success: false`: la placa no existe en el registro o falló la automatización (el detalle viene en `message`).

---

## 🐳 Despliegue en producción (Docker)

El proyecto incluye un `Dockerfile` que instala automáticamente `tesseract-ocr`, `xvfb` y `tini`.

```bash
# Construir la imagen
docker build -t sunarp-scraper .

# Ejecutar el contenedor expuesto en el puerto 8000
docker run -d -p 8000:8000 --env-file .env --name sunarp-service sunarp-scraper
```

Para desplegarlo de forma escalable, puedes usar servicios de contenedores autogestionados como **Render.com**, **Railway.app** o **Google Cloud Run**.

---

## 🧪 Probar el proyecto rápidamente

1.  Sigue los pasos de instalación local (secciones 1-6).
2.  Abre [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) para usar la interfaz Swagger interactiva, o usa los comandos `curl` de la sección anterior.
3.  Prueba con una placa peruana válida (6 caracteres alfanuméricos), por ejemplo `F8Y154`.

---

## ⚠️ Notas y limitaciones

*   Depende de la disponibilidad y estructura actual del portal de SUNARP; cambios en el HTML/selectores del formulario pueden requerir ajustes en `app/automation/vehicular_service.py`.
*   La precisión del OCR depende de la calidad de la imagen devuelta por SUNARP; en casos raros algún campo puede quedar en `null` si el reconocimiento de texto falla.
