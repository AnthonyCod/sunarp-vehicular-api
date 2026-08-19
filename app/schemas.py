from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

class VehicularQueryRequest(BaseModel):
    placa: str = Field(..., min_length=6, max_length=6, description="Placa vehicular de 6 caracteres alfanuméricos")

class VehicularQueryResponse(BaseModel):
    success: bool
    placa: str
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
