from enum import Enum
from datetime import datetime, timedelta
from typing import Dict, List


class Priority(Enum):
    LOW = "🟦"
    MEDIUM = "🟨"
    HIGH = "🟥"
    URGENT = "⚡"


class TaskStatus(Enum):
    PENDING = "⬜"
    COMPLETED = "✅"
    PARTIAL = "🔳"
    CANCELLED = "❌"
    POSTPONED = "▶️"


class RunningTask:
    def __init__(self, name: str, description: str = "", priority: Priority = Priority.MEDIUM):
        self.name = name
        self.description = description
        self.priority = priority
        self.week_days = [TaskStatus.PENDING] * 7  # 7 дней недели
        self.created_date = datetime.now()

    def set_schedule(self, days_indexes: List[int]):
        """Устанавливает расписание на определенные дни"""
        for i in range(7):
            if i in days_indexes:
                self.week_days[i] = self.priority.value
            else:
                self.week_days[i] = TaskStatus.PENDING.value

    def mark_completed(self, day_index: int):
        """Отмечает выполнение за день"""
        self.week_days[day_index] = TaskStatus.COMPLETED.value

    def postpone(self, day_index: int):
        """Переносит задачу на следующий день"""
        if day_index < 6:  # Не воскресенье
            self.week_days[day_index] = TaskStatus.POSTPONED.value
            self.week_days[day_index + 1] = self.priority.value

    def get_week_display(self) -> str:
        """Возвращает строку с днями недели"""
        return "".join(self.week_days)