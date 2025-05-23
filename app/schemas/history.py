from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class HistoryEntry(BaseModel):
    id: int
    timestamp: datetime
    action: str
    userId: int
    userName: str
    details: Optional[Dict[str, Any]]
    class Config:
        orm_mode = True