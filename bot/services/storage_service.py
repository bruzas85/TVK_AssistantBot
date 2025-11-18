import json
import os
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from ..models.timesheet import Timesheet, TimesheetEntry, WorkStatus
from ..models.employee import Employee
from ..models.salary_report import SalaryReport


class StorageService:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        # Папки для разных типов данных
        self.employees_file = self.data_dir / "employees.json"
        self.timesheets_dir = self.data_dir / "timesheets"
        self.reports_dir = self.data_dir / "salary_reports"

        self.timesheets_dir.mkdir(exist_ok=True)
        self.reports_dir.mkdir(exist_ok=True)

    # Методы для сотрудников
    def save_employee(self, employee: Employee) -> None:
        employees = self._load_employees()
        employees[employee.id] = employee.__dict__
        self._save_employees(employees)

    def get_employee(self, employee_id: str) -> Optional[Employee]:
        employees = self._load_employees()
        emp_data = employees.get(employee_id)
        if emp_data:
            # Конвертируем строку даты обратно в объект date
            if 'created_at' in emp_data and isinstance(emp_data['created_at'], str):
                emp_data['created_at'] = date.fromisoformat(emp_data['created_at'])
            return Employee(**emp_data)
        return None

    def get_all_employees(self) -> List[Employee]:
        employees = self._load_employees()
        result = []
        for emp_data in employees.values():
            if 'created_at' in emp_data and isinstance(emp_data['created_at'], str):
                emp_data['created_at'] = date.fromisoformat(emp_data['created_at'])
            result.append(Employee(**emp_data))
        return result

    def _load_employees(self) -> Dict[str, Any]:
        if not self.employees_file.exists():
            return {}
        with open(self.employees_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_employees(self, employees: Dict[str, Any]) -> None:
        with open(self.employees_file, 'w', encoding='utf-8') as f:
            json.dump(employees, f, ensure_ascii=False, indent=2, default=str)

    # Методы для табелей
    def save_timesheet(self, timesheet: Timesheet) -> None:
        filename = self.timesheets_dir / f"{timesheet.employee_id}_{timesheet.year}_{timesheet.month:02d}.json"
        data = {
            'employee_id': timesheet.employee_id,
            'month': timesheet.month,
            'year': timesheet.year,
            'entries': [
                {
                    'employee_id': entry.employee_id,
                    'date': entry.date.isoformat(),
                    'status': entry.status.value,
                    'hours_worked': entry.hours_worked,
                    'created_at': entry.created_at.isoformat()
                }
                for entry in timesheet.entries
            ]
        }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_timesheet(self, employee_id: str, month: int, year: int) -> Optional[Timesheet]:
        filename = self.timesheets_dir / f"{employee_id}_{year}_{month:02d}.json"
        if not filename.exists():
            return None

        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)

        entries = []
        for entry_data in data['entries']:
            entries.append(TimesheetEntry(
                employee_id=entry_data['employee_id'],
                date=date.fromisoformat(entry_data['date']),
                status=WorkStatus(entry_data['status']),
                hours_worked=entry_data['hours_worked'],
                created_at=datetime.fromisoformat(entry_data['created_at'])
            ))

        return Timesheet(
            employee_id=data['employee_id'],
            month=data['month'],
            year=data['year'],
            entries=entries
        )

    def get_or_create_timesheet(self, employee_id: str, for_date: date) -> Timesheet:
        """Получает или создает табель для сотрудника на указанный месяц"""
        timesheet = self.get_timesheet(employee_id, for_date.month, for_date.year)
        if timesheet is None:
            timesheet = Timesheet(
                employee_id=employee_id,
                month=for_date.month,
                year=for_date.year
            )
        return timesheet

    # Методы для отчетов по зарплате
    def save_salary_report(self, report: SalaryReport) -> None:
        filename = self.reports_dir / f"report_{report.period_start}_{report.period_end}.json"
        data = {
            'period_start': report.period_start.isoformat(),
            'period_end': report.period_end.isoformat(),
            'generated_at': report.generated_at.isoformat(),
            'entries': report.entries
        }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_salary_report(self, period_start: date, period_end: date) -> Optional[SalaryReport]:
        filename = self.reports_dir / f"report_{period_start}_{period_end}.json"
        if not filename.exists():
            return None

        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)

        report = SalaryReport(
            period_start=date.fromisoformat(data['period_start']),
            period_end=date.fromisoformat(data['period_end']),
            generated_at=date.fromisoformat(data['generated_at']),
            entries=data['entries']
        )
        return report

    def is_report_exists(self, period_start: date, period_end: date) -> bool:
        filename = self.reports_dir / f"report_{period_start}_{period_end}.json"
        return filename.exists()