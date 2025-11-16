from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean, Date
from datetime import datetime, date, timedelta
from database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)

    # Статус задачи
    status = Column(String(10), default="active")  # active, completed, cancelled, archived

    # Приоритет: low, medium, high, urgent
    priority = Column(String(10), default="medium")

    # Дни недели (0-6, где 0 - понедельник)
    original_day = Column(Integer)  # Изначальный день недели
    current_day = Column(Integer)  # Текущий день недели (может меняться при переносах)

    # История выполнения
    completion_history = Column(JSON, default=[])  # [{date: "2024-01-01", status: "completed"}]

    # Даты
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Task(user_id={self.user_id}, title={self.title}, status={self.status})>"


class TaskDay(Base):
    __tablename__ = "task_days"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, index=True, nullable=False)
    user_id = Column(Integer, index=True, nullable=False)
    date = Column(Date, nullable=False)  # Конкретная дата
    day_of_week = Column(Integer, nullable=False)  # 0-6
    status = Column(String(10), default="pending")  # pending, completed, moved, cancelled, partial
    priority = Column(String(10), default="medium")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<TaskDay(task_id={self.task_id}, date={self.date}, status={self.status})>"