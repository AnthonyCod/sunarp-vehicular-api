import io
import re
import os
import base64
import asyncio
from PIL import Image
import pytesseract
from patchright.async_api import TimeoutError as AutomationTimeoutError
from app.automation.browser_manager import session_manager
from app.config import settings

# Configurar ruta de ejecución de Tesseract en macOS si está instalado mediante Homebrew
TESSERACT_PATH = "/opt/homebrew/bin/tesseract"
if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

def parse_ocr_text(text: str) -> dict:
    """
    Parsea el texto plano extraído del OCR en un diccionario limpio y estructurado.
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    
    key_mappings = {
        "placa": r"(?:N.?\s*PLACA|PLACA)\s*:\s*(.*)",
        "serie": r"(?:N.?\s*SERIE|SERIE)\s*:\s*(.*)",
        "vin": r"(?:N.?[O]?\s*VIN|VIN)\s*:\s*(.*)",
        "motor": r"(?:N.?\s*MOTOR|MOTOR)\s*:\s*(.*)",
        "color": r"COLOR\s*:\s*(.*)",
        "marca": r"MARCA\s*:\s*(.*)",
        "modelo": r"MODELO\s*:\s*(.*)",
        "placa_vigente": r"(?:PLACA\s*VIGENTE|PLACAVIGENTE)\s*:\s*(.*)",
        "placa_anterior": r"PLACA\s*ANTERIOR\s*:\s*(.*)",
        "estado": r"ESTADO\s*:\s*(.*)",
        "anotaciones": r"ANOTACIONES\s*:\s*(.*)",
        "sede": r"SEDE\s*:\s*(.*)",
        "ano_modelo": r"(?:ANO\s*DE\s*MODELO|AÑO\s*DE\s*MODELO)\s*:\s*(.*)",
    }
    
    result = {}
    
    # Buscar correspondencias usando expresiones regulares
    for key, pattern in key_mappings.items():
        found = False
        for line in lines:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                val = match.group(1).strip()
                val = re.sub(r'^[|:\s\-\*]+|[|:\s\-\*]+$', '', val).strip()
                result[key] = val
                found = True
                break
        if not found:
            result[key] = None

    # Extraer los propietarios (pueden ser de múltiples líneas)
    propietarios = []
    found_propietarios_header = False
    
    for line in lines:
        if re.search(r"PROPIETARIO\(S\)\s*:", line, re.IGNORECASE):
            found_propietarios_header = True
            continue
            
        if found_propietarios_header:
            is_another_key = False
            for pattern in key_mappings.values():
                if re.search(pattern, line, re.IGNORECASE):
                    is_another_key = True
                    break
            
            # Detenerse si encuentra el timestamp de pie de página
            is_timestamp = re.search(r"\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}", line)
            
            if is_another_key or is_timestamp:
                break
                
            owner_name = re.sub(r'^[|:\s\-\*]+|[|:\s\-\*]+$', '', line).strip()
            if owner_name:
                propietarios.append(owner_name)
                
    result["propietarios"] = propietarios
    return result

# Intentos totales por placa (1 inicial + reintentos) ante fallos transitorios
# de la automatización: el click no registra, el Turnstile no termina de
# resolverse a tiempo, o el XHR de datos no llega a capturarse.
MAX_ATTEMPTS = 3

class PlacaNoEncontradaError(Exception):
    """La placa no existe en el registro de SUNARP. No es un fallo técnico
    de la automatización, así que reintentar no cambiará el resultado."""
    pass

async def extract_vehicular_data(placa: str) -> dict:
    """
    Ejecuta el flujo de consulta en el portal y extrae los datos resultantes usando Scrapling.
    """
    if not session_manager.session:
        raise Exception("El navegador de Scrapling no ha sido inicializado.")

    async def fill_and_submit(page):
        # Detectar en tiempo real cuándo llega la respuesta de datos vehiculares,
        # en vez de dormir un tiempo fijo sin saber si ya terminó.
        xhr_arrived = asyncio.Event()

        def on_response(response):
            if "getdatosvehiculo" in response.url.lower():
                xhr_arrived.set()

        page.on("response", on_response)

        # Pequeño respiro: justo cuando el widget de Cloudflare pasa de
        # "verificando" a "verificado", el formulario puede re-renderizarse
        # (framework Angular), lo que deja el input "inestable" si lo tocamos
        # en ese instante. Este margen busca reducir esa carrera.
        await page.wait_for_timeout(800)

        # 1. Completar el formulario con la placa requerida
        input_field = page.locator("input#nroPlaca").first
        await input_field.wait_for(state="visible", timeout=10000)
        # fill() ya hace su propio foco + chequeo de estabilidad; el click()
        # explícito previo era redundante y un punto de falla de más.
        await input_field.fill(placa, timeout=15000)
        await input_field.evaluate("el => el.dispatchEvent(new Event('input', { bubbles: true }))")
        await input_field.evaluate("el => el.dispatchEvent(new Event('change', { bubbles: true }))")
        await page.wait_for_timeout(500)

        # 2. Enviar consulta usando el selector del botón corregido
        submit_button = page.locator("button.btn-sunarp-green, button:has-text('Realizar Busqueda')").first
        await submit_button.wait_for(state="visible", timeout=10000)
        await submit_button.click(timeout=15000)
        print("[INFO] Click en botón de búsqueda realizado.")

        # 3. Esperar hasta 3 segundos para detectar si aparece Turnstile post-click
        for _ in range(6):
            if any("challenges.cloudflare.com" in f.url for f in page.frames):
                print("[INFO] Detectado iframe de Turnstile en carga post-click.")
                break
            await page.wait_for_timeout(500)

        # Resolver Turnstile post-click si aparece el challenge
        try:
            await session_manager.session._cloudflare_solver(page)
            print("[INFO] Finalizado proceso de resolución Turnstile post-click.")
        except Exception as e:
            print(f"[INFO] Solver de Turnstile post-click omitido/error: {e}")
            
        # 4. Esperar a que llegue la respuesta real (con techo de seguridad de 10s
        # por si nunca llega, en vez de dormir siempre esos 10s a ciegas)
        try:
            await asyncio.wait_for(xhr_arrived.wait(), timeout=10)
        except asyncio.TimeoutError:
            pass
        finally:
            page.remove_listener("response", on_response)

    last_error = Exception("Error desconocido durante la extracción.")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            # Ejecutamos la petición con Scrapling, gestionando automáticamente el bypass de Cloudflare
            # y la captura de XHR gracias a capture_xhr en la sesión.
            response = await session_manager.session.fetch(
                settings.SUNARP_PORTAL_URL,
                page_setup=None,
                page_action=fill_and_submit,
                solve_cloudflare=True,
                timeout=settings.OPERATION_TIMEOUT * 1000
            )

            # 1. Intentar capturar y retornar el JSON de getDatosVehiculo
            target_xhr = None
            for xhr in getattr(response, "captured_xhr", []):
                if "getdatosvehiculo" in xhr.url.lower():
                    target_xhr = xhr
                    break

            if not target_xhr:
                raise Exception("No se pudo capturar la respuesta del servicio de datos vehiculares.")

            data = target_xhr.json()
            if not isinstance(data, dict):
                raise Exception("Respuesta inesperada del servicio de datos vehiculares.")

            model = data.get("model")
            img_b64 = model.get("imagen") if isinstance(model, dict) else None

            if not img_b64:
                # Sin imagen no hay datos que extraer: normalmente significa que la
                # placa no existe en el registro. Usamos el mensaje real de SUNARP
                # en vez de caer en un respaldo que raspe una tabla no relacionada.
                mensaje = data.get("mensaje") or data.get("mensajeTxt") or "La placa no existe en el registro de SUNARP."
                raise PlacaNoEncontradaError(mensaje)

            # Decodificar imagen base64
            img_bytes = base64.b64decode(img_b64)
            image = Image.open(io.BytesIO(img_bytes))
            # Ejecutar OCR con segmentación en bloque (PSM 4 es ideal para columnas paralelas de clave:valor)
            ocr_text = pytesseract.image_to_string(image, config="--psm 4")

            # Parsear texto del OCR en un JSON limpio
            return parse_ocr_text(ocr_text)

        except PlacaNoEncontradaError:
            # No es un fallo técnico transitorio: reintentar no va a cambiar
            # el resultado, así que devolvemos esto de inmediato.
            raise
        except AutomationTimeoutError:
            last_error = Exception("Tiempo de espera agotado al conectar con el servicio público.")
        except Exception as e:
            last_error = Exception(f"Error durante la extracción: {str(e)}")

        if attempt < MAX_ATTEMPTS:
            print(f"[INFO] Intento {attempt}/{MAX_ATTEMPTS} fallido para placa {placa}: {last_error}. Reintentando...")
            await asyncio.sleep(3)

    raise last_error
