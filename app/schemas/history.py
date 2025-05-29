from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class HistoryEntry(BaseModel):
    id: int
    document_id: int
    action: str
    userId:   int   
    userName: str   
    timestamp: datetime
    details: Optional[str]
    class Config:
        orm_mode = True