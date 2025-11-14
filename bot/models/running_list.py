from datetime import datetime
from typing import List, Optional
from enum import Enum


class TaskPriority(Enum):
    LOW = "🔵 Низкий"
    MEDIUM = "🟡 Средний"
    HIGH = "🔴 Высокий"
    URGENT = "⚡ Срочный"


class RunningTask:
    def __init__(self, description: str, priority: TaskPriority = TaskPriority.MEDIUM, task_id: Optional[str] = None):
        self.id = task_id or str(datetime.now().timestamp())
        self.description = description
        self.priority = priority
        self.created_date = datetime.now()
        self.is_completed = False
        self.completed_date: Optional[datetime] = None
        self.due_date: Optional[datetime] = None

    def complete(self):
        self.is_completed = True
        self.completed_date = datetime.now()

    def reopen(self):
        self.is_completed = False
        self.completed_date = None


class RunningList:
    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.tasks: List[RunningTask] = []

    def add_task(self, description: str, priority: TaskPriority = TaskPriority.MEDIUM) -> RunningTask:
        task = RunningTask(description, priority)
        self.tasks.append(task)
        return task

    def get_task(self, task_id: str) -> Optional[RunningTask]:
        return next((task for task in self.tasks if task.id == task_id), None)

    def delete_task(self, task_id: str) -> bool:
        task = self.get_task(task_id)
        if task:
            self.tasks.remove(task)
            return True
        return False

    def get_active_tasks(self) -> List[RunningTask]:
        return [task for task in self.tasks if not task.is_completed]

    def get_completed_tasks(self) -> List[RunningTask]:
        return [task for task in self.tasks if task.is_completed]

    def get_tasks_by_priority(self, priority: TaskPriority) -> List[RunningTask]:
        return [task for task in self.tasks if task.priority == priority and not task.is_completed]