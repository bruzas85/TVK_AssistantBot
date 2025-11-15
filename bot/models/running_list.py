from datetime import datetime
from typing import List, Optional
from enum import Enum


class TaskStatus(Enum):
    PENDING = "⏳ Ожидает"
    COMPLETED = "✅ Выполнено"
    PARTIAL = "🟡 Частично выполнено"
    CANCELLED = "❌ Отменено"
    POSTPONED = "📅 Перенесено"


class TaskPriority(Enum):
    LOW = "🔵 Низкий"
    MEDIUM = "🟡 Средний"
    HIGH = "🔴 Высокий"
    URGENT = "⚡ Срочный"


class RunningTask:
    def __init__(self, description: str, priority: TaskPriority = TaskPriority.MEDIUM,
                 task_id: Optional[str] = None, short_name: Optional[str] = None):
        self.id = task_id or str(datetime.now().timestamp())
        self.short_name = short_name or description[:20] + "..." if len(description) > 20 else description
        self.description = description
        self.priority = priority
        self.status = TaskStatus.PENDING
        self.created_date = datetime.now()
        self.updated_date = datetime.now()
        self.comments: List[str] = []
        self.due_date: Optional[datetime] = None

    def add_comment(self, comment: str):
        self.comments.append(f"{datetime.now().strftime('%d.%m.%Y %H:%M')}: {comment}")
        self.updated_date = datetime.now()

    def change_status(self, new_status: TaskStatus):
        self.status = new_status
        self.updated_date = datetime.now()


class RunningList:
    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.tasks: List[RunningTask] = []

    def add_task(self, description: str, priority: TaskPriority = TaskPriority.MEDIUM,
                 short_name: Optional[str] = None) -> RunningTask:
        task = RunningTask(description, priority, short_name=short_name)
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

    def get_tasks_by_status(self, status: TaskStatus) -> List[RunningTask]:
        return [task for task in self.tasks if task.status == status]

    def get_active_tasks(self) -> List[RunningTask]:
        return [task for task in self.tasks if task.status == TaskStatus.PENDING]

    def get_tasks_by_priority(self, priority: TaskPriority) -> List[RunningTask]:
        return [task for task in self.tasks if task.priority == priority]