from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime
from datetime import datetime
import json


class RunningTask:
    def __init__(self, id=None, user_id=None, task_text="", priority="medium",
                 days_of_week=None, status_history=None, created_at=None):
        self.id = id
        self.user_id = user_id
        self.task_text = task_text
        self.priority = priority
        self.days_of_week = days_of_week or [False] * 7
        self.status_history = status_history or []
        self.created_at = created_at or datetime.now()

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'task_text': self.task_text,
            'priority': self.priority,
            'days_of_week': self.days_of_week,
            'status_history': self.status_history,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data.get('id'),
            user_id=data.get('user_id'),
            task_text=data.get('task_text', ''),
            priority=data.get('priority', 'medium'),
            days_of_week=data.get('days_of_week', [False] * 7),
            status_history=data.get('status_history', []),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None
        )


# Для хранения в PostgreSQL
class RunningTaskDB:
    __tablename__ = 'running_tasks'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    task_text = Column(String, nullable=False)
    priority = Column(String, default='medium')
    days_of_week = Column(String)
    status_history = Column(String)
    created_at = Column(DateTime, default=datetime.now)

    def to_running_task(self):
        return RunningTask(
            id=self.id,
            user_id=self.user_id,
            task_text=self.task_text,
            priority=self.priority,
            days_of_week=json.loads(self.days_of_week) if self.days_of_week else [False] * 7,
            status_history=json.loads(self.status_history) if self.status_history else [],
            created_at=self.created_at
        )

    @classmethod
    def from_running_task(cls, task):
        return cls(
            user_id=task.user_id,
            task_text=task.task_text,
            priority=task.priority,
            days_of_week=json.dumps(task.days_of_week),
            status_history=json.dumps(task.status_history),
            created_at=task.created_at
        )