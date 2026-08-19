from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from app.schemas import (
    BatchJobCreatedResponse,
    BatchJobResponse,
    BatchQueryRequest,
    VehicularQueryResponse,
)
from app.automation.batch_manager import batch_manager
from app.automation.browser_manager import session_manager
from app.automation.vehicular_service import extract_vehicular_data

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialización del gestor de navegación al arrancar la API
    await session_manager.initialize()
    yield
    # Cierre ordenado de sesiones al apagar la API
    await session_manager.shutdown()

app = FastAPI(
    title="SUNARP Public Vehicular Data API",
    version="1.0.0",
    description="Microservicio de integración y consulta automatizada de datos vehiculares públicos.",
    lifespan=lifespan
)

@app.get(
    "/api/v1/vehiculo/{placa}",
    response_model=VehicularQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener datos vehiculares públicos por placa"
)
async def get_vehiculo(placa: str):
    sanitized_placa = placa.replace("-", "").replace(" ", "").upper()

    if len(sanitized_placa) != 6 or not sanitized_placa.isalnum():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de placa inválido. Debe consistir en 6 caracteres alfanuméricos."
        )

    try:
        result_data = await extract_vehicular_data(sanitized_placa)
        return VehicularQueryResponse(
            success=True,
            placa=sanitized_placa,
            data=result_data,
            message="Consulta procesada exitosamente."
        )
    except Exception as exc:
        return VehicularQueryResponse(
            success=False,
            placa=sanitized_placa,
            data=None,
            message=str(exc)
        )

@app.post(
    "/api/v1/vehiculo/lote",
    response_model=BatchJobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Encolar una consulta masiva de placas vehiculares"
)
async def post_vehiculo_lote(payload: BatchQueryRequest):
    sanitized_placas = []
    seen = set()
    for raw_placa in payload.placas:
        placa = raw_placa.replace("-", "").replace(" ", "").upper()
        if placa in seen:
            continue
        seen.add(placa)
        sanitized_placas.append(placa)

    job_id = batch_manager.create_job(sanitized_placas)
    job = batch_manager.get_job(job_id)

    return BatchJobCreatedResponse(
        job_id=job_id,
        status=job["status"],
        total=job["total"]
    )

@app.get(
    "/api/v1/vehiculo/lote/{job_id}",
    response_model=BatchJobResponse,
    summary="Consultar el progreso y los resultados de una carga masiva"
)
async def get_vehiculo_lote(job_id: str):
    job = batch_manager.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró una carga masiva con ese job_id."
        )

    return BatchJobResponse(
        job_id=job_id,
        status=job["status"],
        total=job["total"],
        completadas=len(job["resultados"]),
        resultados=job["resultados"]
    )
