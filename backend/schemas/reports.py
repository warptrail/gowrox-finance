# backend/schemas/reports.py
from pydantic import BaseModel


class UncategorizedCountOut(BaseModel):
    year: int
    count: int