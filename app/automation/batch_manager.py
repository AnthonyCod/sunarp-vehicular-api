import asyncio
import random
import uuid
from typing import Dict, List, Optional

from app.config import settings
from app.schemas import BatchJobStatus, VehicularQueryResponse
from app.automation.vehicular_service import extract_vehicular_data

# Rango de pausa aleatoria (segundos) entre el inicio de cada consulta,
# para evitar un patrón de tráfico uniforme detectable como bot.
JITTER_RANGE = (1.5, 4.0)

# Reintentos ante fallos transitorios (timeouts, Turnstile lento, etc.)
MAX_RETRIES = 2


class BatchJobManager:
    def __init__(self):
        self._jobs: Dict[str, dict] = {}
        self._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_SESSIONS)

    def create_job(self, placas: List[str]) -> str:
        job_id = uuid.uuid4().hex
        valid_placas: List[str] = []
        resultados: List[VehicularQueryResponse] = []

        for placa in placas:
            if len(placa) == 6 and placa.isalnum():
                valid_placas.append(placa)
            else:
                resultados.append(VehicularQueryResponse(
                    success=False,
                    placa=placa,
                    data=None,
                    message="Formato de placa inválido. Debe consistir en 6 caracteres alfanuméricos."
                ))

        self._jobs[job_id] = {
            "status": BatchJobStatus.EN_PROGRESO if valid_placas else BatchJobStatus.COMPLETADO,
            "total": len(placas),
            "resultados": resultados,
        }

        if valid_placas:
            asyncio.create_task(self._run_job(job_id, valid_placas))

        return job_id

    def get_job(self, job_id: str) -> Optional[dict]:
        return self._jobs.get(job_id)

    async def _run_job(self, job_id: str, placas: List[str]):
        job = self._jobs[job_id]

        async def process_one(placa: str):
            async with self._semaphore:
                result = None
                for attempt in range(MAX_RETRIES + 1):
                    await asyncio.sleep(random.uniform(*JITTER_RANGE))
                    try:
                        data = await extract_vehicular_data(placa)
                        result = VehicularQueryResponse(
                            success=True,
                            placa=placa,
                            data=data,
                            message="Consulta procesada exitosamente."
                        )
                        break
                    except Exception as exc:
                        result = VehicularQueryResponse(
                            success=False,
                            placa=placa,
                            data=None,
                            message=str(exc)
                        )
                job["resultados"].append(result)

        await asyncio.gather(*(process_one(placa) for placa in placas))
        job["status"] = BatchJobStatus.COMPLETADO


batch_manager = BatchJobManager()
