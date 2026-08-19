from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from app.schemas import VehicularQueryResponse
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
