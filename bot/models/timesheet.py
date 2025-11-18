from datetime import datetime, date
from typing import List, Optional
from dataclasses import dataclass, field
from enum import Enum


class WorkStatus(Enum):
    WORKED = "worked"
    ABSENT = "absent"
    SICK = "sick"
    VACATION = "vacation"


@dataclass
class TimesheetEntry:
    employee_id: str
    date: date
    status: WorkStatus
    hours_worked: float = 8.0  # стандартный рабочий день
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Timesheet:
    employee_id: str
    month: int  # 1-12
    year: int
    entries: List[TimesheetEntry] = field(default_factory=list)

    def add_entry(self, entry: TimesheetEntry):
        """Добавляет запись в табель"""
        # Удаляем существующую запись на эту дату
        self.entries = [e for e in self.entries if e.date != entry.date]
        self.entries.append(entry)

    def get_entries_for_period(self, start_date: date, end_date: date) -> List[TimesheetEntry]:
        """Возвращает записи за указанный период"""
        return [entry for entry in self.entries if start_date <= entry.date <= end_date]

    def is_date_marked(self, check_date: date) -> bool:
        """Проверяет, отмечен ли сотрудник в табеле на указанную дату"""
        return any(entry.date == check_date for entry in self.entries)