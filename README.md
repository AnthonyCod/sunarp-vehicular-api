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
sunarp-vehicular-api/
├── app/
│   ├── main.py                      # Definición de la API y endpoints (FastAPI)
│   ├── schemas.py                   # Modelos Pydantic de request/response
│   ├── config.py                    # Carga de configuración desde variables de entorno
│   └── automation/
│       ├── browser_manager.py       # Ciclo de vida de la sesión del navegador (Scrapling)
│       └── vehicular_service.py     # Flujo de consulta, resolución de Turnstile y OCR
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🛠️ Requisitos previos

*   [Docker Desktop](https://www.docker.com/products/docker-desktop/) (incluye Docker Compose).

No hace falta instalar Python, Tesseract ni Chromium en tu máquina: todo queda encapsulado dentro del contenedor.

---

## 🐳 Instalación y ejecución con Docker

### 1. Clonar el repositorio
```bash
git clone https://github.com/AnthonyCod/sunarp-vehicular-api.git
cd sunarp-vehicular-api
```

### 2. Configurar las variables de entorno
Copia el archivo de ejemplo. Los valores por defecto ya sirven para levantar el servicio:
```bash
cp .env.example .env
```

| Variable                   | Descripción                                                                 | Valor por defecto |
|-----------------------------|------------------------------------------------------------------------------|--------------------|
| `HEADLESS_MODE`             | `true` para correr el navegador sin interfaz (producción); `false` para verlo (debug) | `true`             |
| `MAX_CONCURRENT_SESSIONS`   | Número máximo de consultas ejecutándose en paralelo | `1`                |
| `OPERATION_TIMEOUT`         | Timeout en segundos para cada operación de consulta                        | `30`               |
| `OUTBOUND_PROXY`            | (Opcional) proxy saliente a usar en las peticiones del navegador           | *(sin proxy)*      |

### 3. Levantar el servicio
```bash
docker compose up --build
```

> [!NOTE]
> La primera vez la build puede tardar varios minutos: instala Tesseract OCR, XVFB y descarga el navegador Chromium (motor `patchright`) junto con sus dependencias del sistema. Las siguientes veces será mucho más rápida gracias al cache de Docker.

Con eso el servicio queda escuchando en [http://localhost:8000](http://localhost:8000), y la documentación interactiva (Swagger UI) en [http://localhost:8000/docs](http://localhost:8000/docs).

Para correrlo en segundo plano:
```bash
docker compose up -d --build
```

Comandos útiles:
```bash
docker compose logs -f     # ver logs en vivo
docker compose down        # detener y eliminar el contenedor
```

### Despliegue en producción
Para desplegarlo de forma escalable, puedes usar servicios de contenedores autogestionados como **Render.com**, **Railway.app** o **Google Cloud Run**, apuntando al mismo `Dockerfile`.

---

## 📡 Uso de la API

### Consulta por placa — `GET /api/v1/vehiculo/{placa}`

Consulta los datos de una sola placa. La búsqueda es síncrona: la respuesta se devuelve una vez completado el proceso de scraping + OCR (puede tardar varios segundos).

```bash
curl http://localhost:8000/api/v1/vehiculo/ABC123
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

## 🧪 Probar el proyecto rápidamente

1.  Sigue los pasos de la sección [🐳 Instalación y ejecución con Docker](#-instalación-y-ejecución-con-docker).
2.  Abre [http://localhost:8000/docs](http://localhost:8000/docs) para usar la interfaz Swagger interactiva, o usa los comandos `curl` de la sección anterior.
3.  Prueba con una placa peruana válida (6 caracteres alfanuméricos), por ejemplo `F8Y154`.

---

## ⚠️ Notas y limitaciones

*   Depende de la disponibilidad y estructura actual del portal de SUNARP; cambios en el HTML/selectores del formulario pueden requerir ajustes en `app/automation/vehicular_service.py`.
*   La precisión del OCR depende de la calidad de la imagen devuelta por SUNARP; en casos raros algún campo puede quedar en `null` si el reconocimiento de texto falla.
