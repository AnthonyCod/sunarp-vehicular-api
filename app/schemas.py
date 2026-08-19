from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from enum import Enum

class VehicularQueryRequest(BaseModel):
    placa: str = Field(..., min_length=6, max_length=6, description="Placa vehicular de 6 caracteres alfanuméricos")

class VehicularQueryResponse(BaseModel):
    success: bool
    placa: str
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None

class BatchQueryRequest(BaseModel):
    placas: List[str] = Field(..., min_length=1, max_length=500, description="Lista de placas a consultar (máximo 500)")

class BatchJobStatus(str, Enum):
    EN_PROGRESO = "en_progreso"
    COMPLETADO = "completado"

class BatchJobCreatedResponse(BaseModel):
    job_id: str
    status: BatchJobStatus
    total: int

class BatchJobResponse(BaseModel):
    job_id: str
    status: BatchJobStatus
    total: int
    completadas: int
    resultados: List[VehicularQueryResponse]
