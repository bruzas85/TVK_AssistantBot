from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Employee:
    id: str
    name: str
    daily_salary: float
    position: str
    is_active: bool = True
    created_at: date = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = date.today()