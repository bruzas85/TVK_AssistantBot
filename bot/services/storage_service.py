import json
from typing import List, Optional
from models.running_list import RunningTask, RunningTaskDB


class StorageService:
    def __init__(self, session):
        self.session = session

    def add_running_task(self, user_id: int, task_text: str, priority: str = "medium") -> RunningTask:
        task = RunningTask(user_id=user_id, task_text=task_text, priority=priority)
        task_db = RunningTaskDB.from_running_task(task)
        self.session.add(task_db)
        self.session.commit()
        task.id = task_db.id
        return task

    def get_running_tasks(self, user_id: int) -> List[RunningTask]:
        tasks_db = self.session.query(RunningTaskDB).filter(
            RunningTaskDB.user_id == user_id
        ).all()
        return [task_db.to_running_task() for task_db in tasks_db]

    def get_running_task(self, task_id: int) -> Optional[RunningTask]:
        task_db = self.session.query(RunningTaskDB).filter(
            RunningTaskDB.id == task_id
        ).first()
        return task_db.to_running_task() if task_db else None

    def update_running_task(self, task: RunningTask) -> bool:
        task_db = self.session.query(RunningTaskDB).filter(
            RunningTaskDB.id == task.id
        ).first()
        if task_db:
            task_db.task_text = task.task_text
            task_db.priority = task.priority
            task_db.days_of_week = json.dumps(task.days_of_week)
            task_db.status_history = json.dumps(task.status_history)
            self.session.commit()
            return True
        return False

    def delete_running_task(self, task_id: int) -> bool:
        task_db = self.session.query(RunningTaskDB).filter(
            RunningTaskDB.id == task_id
        ).first()
        if task_db:
            self.session.delete(task_db)
            self.session.commit()
            return True
        return False