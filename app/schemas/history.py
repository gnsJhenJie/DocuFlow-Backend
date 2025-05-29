from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class HistoryEntry(BaseModel):
    id: int
    document_id: int
    action: str
    actor_id: int
    timestamp: datetime
    details: Optional[str]
    class Config:
        orm_mode = True