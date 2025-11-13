from datetime import datetime, date, timedelta
from typing import Dict, List, Optional


class Employee:
    def __init__(self, name: str, daily_salary: float, employee_id: Optional[str] = None):
        self.id = employee_id or str(datetime.now().timestamp())
        self.name = name
        self.daily_salary = daily_salary
        self.created_date = datetime.now()


class AttendanceRecord:
    def __init__(self, employee_id: str, work_date: date, is_present: bool = False):
        self.employee_id = employee_id
        self.work_date = work_date
        self.is_present = is_present
        self.is_locked = False  # Становится True после сохранения


class Timesheet:
    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.employees: Dict[str, Employee] = {}
        self.attendance_records: List[AttendanceRecord] = []

    def add_employee(self, name: str, daily_salary: float) -> Employee:
        employee = Employee(name, daily_salary)
        self.employees[employee.id] = employee
        return employee

    def remove_employee(self, employee_id: str) -> bool:
        if employee_id in self.employees:
            # Удаляем все записи посещаемости для этого сотрудника
            self.attendance_records = [
                record for record in self.attendance_records
                if record.employee_id != employee_id
            ]
            del self.employees[employee_id]
            return True
        return False

    def get_employee(self, employee_id: str) -> Optional[Employee]:
        return self.employees.get(employee_id)

    def get_all_employees(self) -> List[Employee]:
        return list(self.employees.values())

    def mark_attendance(self, employee_id: str, work_date: date, is_present: bool) -> bool:
        # Проверяем, не заблокирована ли уже запись на эту дату
        existing_record = self._find_attendance_record(employee_id, work_date)
        if existing_record and existing_record.is_locked:
            return False

        if existing_record:
            existing_record.is_present = is_present
        else:
            record = AttendanceRecord(employee_id, work_date, is_present)
            self.attendance_records.append(record)
        return True

    def lock_attendance_for_date(self, work_date: date):
        """Блокирует все записи на указанную дату"""
        for record in self.attendance_records:
            if record.work_date == work_date:
                record.is_locked = True

    def is_date_locked(self, work_date: date) -> bool:
        """Проверяет, заблокирована ли дата для изменений"""
        records_for_date = [r for r in self.attendance_records if r.work_date == work_date]
        return any(record.is_locked for record in records_for_date)

    def get_attendance_for_period(self, employee_id: str, start_date: date, end_date: date) -> List[AttendanceRecord]:
        return [
            record for record in self.attendance_records
            if record.employee_id == employee_id and start_date <= record.work_date <= end_date
        ]

    def calculate_salary_for_period(self, employee_id: str, start_date: date, end_date: date) -> float:
        employee = self.get_employee(employee_id)
        if not employee:
            return 0.0

        attendance_records = self.get_attendance_for_period(employee_id, start_date, end_date)
        working_days = sum(1 for record in attendance_records if record.is_present)

        return working_days * employee.daily_salary

    def get_current_period(self) -> tuple[date, date]:
        """Возвращает даты текущего периода (1-15 или 16-конец месяца)"""
        today = date.today()
        if today.day <= 15:
            start_date = date(today.year, today.month, 1)
            end_date = date(today.year, today.month, 15)
        else:
            start_date = date(today.year, today.month, 16)
            # Последний день месяца
            if today.month == 12:
                end_date = date(today.year, today.month, 31)
            else:
                end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)

        return start_date, end_date

    def _find_attendance_record(self, employee_id: str, work_date: date) -> Optional[AttendanceRecord]:
        for record in self.attendance_records:
            if record.employee_id == employee_id and record.work_date == work_date:
                return record
        return None