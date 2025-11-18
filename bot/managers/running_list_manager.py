# managers/running_list_manager.py
from typing import Dict, List
from models.running_task import RunningTask, Priority, TaskStatus


class RunningListManager:
    def __init__(self):
        self.tasks: Dict[int, RunningTask] = {}
        self.next_task_id = 1

    def add_task(self, name: str, days_indexes: List[int], priority: Priority, description: str = "") -> int:
        task = RunningTask(name, description, priority)
        task.set_schedule(days_indexes)

        task_id = self.next_task_id
        self.tasks[task_id] = task
        self.next_task_id += 1
        return task_id

    def get_task_display(self, task_id: int) -> str:
        task = self.tasks.get(task_id)
        if not task:
            return "Задача не найдена"
        return f"{task.get_week_display()} - {task.name}"

    def get_all_tasks_display(self) -> List[str]:
        if not self.tasks:
            return ["Running list пуст"]

        max_name_length = max(len(task.name) for task in self.tasks.values())

        displays = []
        for task_id, task in self.tasks.items():
            week_days = task.get_week_display()
            name_padded = task.name.ljust(max_name_length)
            displays.append(f"{week_days} - {name_padded} [#{task_id}]")

        return displays

    def get_task_details(self, task_id: int) -> str:
        task = self.tasks.get(task_id)
        if not task:
            return "Задача не найдена"

        days_of_week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        schedule_info = "\n".join(
            f"{days_of_week[i]}: {task.week_days[i]}"
            for i in range(7)
            if task.week_days[i] != TaskStatus.PENDING.value
        )

        return f"""📋 Задача: {task.name}
🎯 Приоритет: {task.priority.value}
📅 Расписание:
{schedule_info}
📝 Описание: {task.description or 'Нет описания'}
🆔 ID: #{task_id}"""