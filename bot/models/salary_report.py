from dataclasses import dataclass
from datetime import date
from typing import List, Dict
from .employee import Employee
from .timesheet import TimesheetEntry, WorkStatus


@dataclass
class SalaryReport:
    period_start: date
    period_end: date
    generated_at: date
    entries: List[Dict]  # Список расчетов по сотрудникам

    def add_employee_calculation(self, employee: Employee, entries: List[TimesheetEntry], total_salary: float):
        """Добавляет расчет по сотруднику в отчет"""
        worked_days = len([e for e in entries if e.status == WorkStatus.WORKED])
        absent_days = len([e for e in entries if e.status == WorkStatus.ABSENT])
        sick_days = len([e for e in entries if e.status == WorkStatus.SICK])
        vacation_days = len([e for e in entries if e.status == WorkStatus.VACATION])

        self.entries.append({
            'employee_name': employee.name,
            'employee_position': employee.position,
            'daily_salary': employee.daily_salary,
            'worked_days': worked_days,
            'absent_days': absent_days,
            'sick_days': sick_days,
            'vacation_days': vacation_days,
            'total_salary': total_salary
        })

    def get_total_payroll(self) -> float:
        """Возвращает общий фонд оплаты труда за период"""
        return sum(entry['total_salary'] for entry in self.entries)