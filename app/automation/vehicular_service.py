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

async def extract_vehicular_data(placa: str) -> dict:
    """
    Ejecuta el flujo de consulta en el portal y extrae los datos resultantes usando Scrapling.
    """
    if not session_manager.session:
        raise Exception("El navegador de Scrapling no ha sido inicializado.")

    async def fill_and_submit(page):
        # 1. Completar el formulario con la placa requerida
        input_field = page.locator("input#nroPlaca").first
        await input_field.wait_for(state="visible", timeout=10000)
        await input_field.click()
        await input_field.fill(placa)
        await input_field.evaluate("el => el.dispatchEvent(new Event('input', { bubbles: true }))")
        await input_field.evaluate("el => el.dispatchEvent(new Event('change', { bubbles: true }))")
        await page.wait_for_timeout(500)

        # 2. Enviar consulta usando el selector del botón corregido
        submit_button = page.locator("button.btn-sunarp-green, button:has-text('Realizar Busqueda')").first
        await submit_button.wait_for(state="visible", timeout=10000)
        await submit_button.click()
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
            
        # 4. Esperar a que la petición XHR de datos vehiculares se procese y termine
        await page.wait_for_timeout(10000)

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
            mensaje = data.get("mensaje") or data.get("mensajeTxt") or "La placa no fue encontrada en el registro."
            raise Exception(mensaje)

        # Decodificar imagen base64
        img_bytes = base64.b64decode(img_b64)
        image = Image.open(io.BytesIO(img_bytes))
        # Ejecutar OCR con segmentación en bloque (PSM 4 es ideal para columnas paralelas de clave:valor)
        ocr_text = pytesseract.image_to_string(image, config="--psm 4")

        # Parsear texto del OCR en un JSON limpio
        return parse_ocr_text(ocr_text)

    except AutomationTimeoutError:
        raise Exception("Tiempo de espera agotado al conectar con el servicio público.")
    except Exception as e:
        raise Exception(f"Error durante la extracción: {str(e)}")
