from datetime import datetime, timedelta
from typing import Dict, List, Optional
from .timesheet import Timesheet


class Expense:
    def __init__(self, category: str, amount: float, description: str, expense_type: str,
                 date: Optional[datetime] = None):
        self.category = category
        self.amount = amount
        self.description = description
        self.type = expense_type
        self.date = date or datetime.now()

    def to_dict(self):
        return {
            'date': self.date,
            'category': self.category,
            'amount': self.amount,
            'description': self.description,
            'type': self.type
        }


class UserData:
    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.expenses: List[Expense] = []
        self.state: str = 'main_menu'
        self.timesheet = Timesheet(chat_id)

    def add_expense(self, expense: Expense):
        self.expenses.append(expense)

    def clear_expenses(self):
        count = len(self.expenses)
        self.expenses = []
        return count

    def get_expenses_by_period(self, period_days: int) -> List[Expense]:
        cutoff_date = datetime.now() - timedelta(days=period_days)
        return [exp for exp in self.expenses if exp.date >= cutoff_date]

    def get_total_expenses(self) -> float:
        return sum(exp.amount for exp in self.expenses)