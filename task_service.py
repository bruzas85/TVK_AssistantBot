import logging
from sqlalchemy.orm import Session
from models import Task, TaskDay
from database import get_db
from datetime import datetime, date, timedelta
import json
from typing import List, Dict

logger = logging.getLogger(__name__)


class TaskService:
    # Символы для отображения
    PRIORITY_SYMBOLS = {
        'low': '🟦',
        'medium': '🟨',
        'high': '🟥',
        'urgent': '⚡'
    }

    STATUS_SYMBOLS = {
        'pending': '🔳',
        'completed': '✅',
        'moved': '➡️',
        'cancelled': '❌',
        'partial': '🔄'
    }

    DAYS_OF_WEEK = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

    @staticmethod
    def get_current_week_dates():
        """Возвращает даты текущей недели (понедельник - воскресенье)"""
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())
        week_dates = [start_of_week + timedelta(days=i) for i in range(7)]
        return week_dates

    @staticmethod
    def create_task(user_id: int, title: str, day_of_week: int, priority: str = "medium", description: str = None):
        """Создает новую задачу"""
        db = next(get_db())

        try:
            # Создаем задачу
            task = Task(
                user_id=user_id,
                title=title,
                description=description,
                priority=priority,
                original_day=day_of_week,
                current_day=day_of_week
            )
            db.add(task)
            db.commit()
            db.refresh(task)

            # Создаем записи для дней выполнения
            TaskService._create_task_days(db, task)

            logger.info(f"Создана задача: {title} для пользователя {user_id}")
            return task

        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка при создании задачи: {e}")
            return None

    @staticmethod
    def _create_task_days(db: Session, task: Task):
        """Создает записи дней выполнения для задачи"""
        week_dates = TaskService.get_current_week_dates()
        target_date = week_dates[task.current_day]

        task_day = TaskDay(
            task_id=task.id,
            user_id=task.user_id,
            date=target_date,
            day_of_week=task.current_day,
            priority=task.priority
        )
        db.add(task_day)
        db.commit()

    @staticmethod
    def get_week_tasks(user_id: int):
        """Получает задачи на текущую неделю"""
        db = next(get_db())

        try:
            week_dates = TaskService.get_current_week_dates()
            start_date = week_dates[0]
            end_date = week_dates[-1]

            # Получаем активные задачи пользователя
            tasks = db.query(Task).filter(
                Task.user_id == user_id,
                Task.status == "active"
            ).all()

            # Получаем дни выполнения для этих задач
            task_days = db.query(TaskDay).filter(
                TaskDay.user_id == user_id,
                TaskDay.date >= start_date,
                TaskDay.date <= end_date
            ).all()

            # Формируем структуру данных
            week_tasks = {}
            for day_idx, day_date in enumerate(week_dates):
                day_tasks = []
                for task_day in task_days:
                    if task_day.date == day_date:
                        task = next((t for t in tasks if t.id == task_day.task_id), None)
                        if task:
                            day_tasks.append({
                                'task': task,
                                'task_day': task_day
                            })

                week_tasks[day_idx] = {
                    'date': day_date,
                    'tasks': day_tasks
                }

            return week_tasks

        except Exception as e:
            logger.error(f"Ошибка при получении задач недели: {e}")
            return {}

    @staticmethod
    def format_week_tasks_display(week_tasks: Dict):
        """Форматирует отображение задач недели"""
        today = date.today()
        current_week_dates = TaskService.get_current_week_dates()
        today_index = current_week_dates.index(today) if today in current_week_dates else -1

        lines = []
        lines.append("📅 **Running List на неделю:**")
        lines.append("")

        # Заголовок с днями недели
        header = "     "  # Отступ для выравнивания
        for i in range(7):
            day_label = TaskService.DAYS_OF_WEEK[i]
            if i == today_index:
                day_label = f"**{day_label}**"  # Выделяем сегодняшний день
            header += f"{day_label}   "
        lines.append(header)
        lines.append("")

        # Формируем строки для каждой задачи
        task_rows = []

        # Собираем все задачи недели
        all_task_days = []
        for day_idx in range(7):
            for task_data in week_tasks[day_idx]['tasks']:
                all_task_days.append((day_idx, task_data))

        # Группируем по задачам
        tasks_map = {}
        for day_idx, task_data in all_task_days:
            task_id = task_data['task'].id
            if task_id not in tasks_map:
                tasks_map[task_id] = {
                    'task': task_data['task'],
                    'days': {}
                }
            tasks_map[task_id]['days'][day_idx] = task_data['task_day']

        # Создаем строки для каждой задачи
        for task_id, task_info in tasks_map.items():
            task = task_info['task']
            task_days = task_info['days']

            # Создаем строку статусов
            status_line = "     "  # Отступ для выравнивания
            for day_idx in range(7):
                if day_idx in task_days:
                    task_day = task_days[day_idx]
                    if task_day.status == 'pending':
                        symbol = TaskService.PRIORITY_SYMBOLS[task_day.priority]
                    else:
                        symbol = TaskService.STATUS_SYMBOLS[task_day.status]
                else:
                    symbol = '🔳'
                status_line += f"{symbol}    "

            # Добавляем название задачи
            task_row = f"{status_line} - {task.title}"
            task_rows.append(task_row)

        lines.extend(task_rows)
        lines.append("")
        lines.append("**Легенда:**")
        lines.append("🟦 - низкий  🟨 - средний  🟥 - высокий  ⚡ - срочный")
        lines.append("✅ - выполнено  ➡️ - перенесено  ❌ - отменено  🔄 - частично")

        return "\n".join(lines)

    @staticmethod
    def update_task_status(user_id: int, task_id: int, day_of_week: int, status: str):
        """Обновляет статус задачи на определенный день"""
        db = next(get_db())

        try:
            week_dates = TaskService.get_current_week_dates()
            target_date = week_dates[day_of_week]

            # Находим запись дня выполнения
            task_day = db.query(TaskDay).filter(
                TaskDay.user_id == user_id,
                TaskDay.task_id == task_id,
                TaskDay.date == target_date
            ).first()

            if not task_day:
                logger.warning(f"Задача {task_id} не найдена для дня {day_of_week}")
                return False

            # Обновляем статус
            old_status = task_day.status
            task_day.status = status
            task_day.updated_at = datetime.utcnow()

            # Если задача переносится, создаем запись на следующий день
            if status == 'moved':
                next_day = (day_of_week + 1) % 7
                next_date = week_dates[next_day]

                # Проверяем, нет ли уже записи на следующий день
                existing_next_day = db.query(TaskDay).filter(
                    TaskDay.user_id == user_id,
                    TaskDay.task_id == task_id,
                    TaskDay.date == next_date
                ).first()

                if not existing_next_day:
                    # Создаем новую запись с тем же приоритетом
                    new_task_day = TaskDay(
                        task_id=task_id,
                        user_id=user_id,
                        date=next_date,
                        day_of_week=next_day,
                        priority=task_day.priority,
                        status='pending'
                    )
                    db.add(new_task_day)

            # Если задача выполнена, обновляем историю
            elif status == 'completed':
                task = db.query(Task).filter(Task.id == task_id).first()
                if task:
                    history = task.completion_history or []
                    history.append({
                        'date': target_date.isoformat(),
                        'status': 'completed'
                    })
                    task.completion_history = history

            db.commit()
            logger.info(f"Обновлен статус задачи {task_id}: {old_status} -> {status}")
            return True

        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка при обновлении статуса задачи: {e}")
            return False

    @staticmethod
    def complete_task(user_id: int, task_id: int):
        """Отмечает задачу как выполненную и архивирует"""
        db = next(get_db())

        try:
            task = db.query(Task).filter(
                Task.user_id == user_id,
                Task.id == task_id
            ).first()

            if task:
                task.status = 'completed'
                task.completed_at = datetime.utcnow()
                db.commit()
                logger.info(f"Задача {task_id} завершена и архивирована")
                return True
            return False

        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка при завершении задачи: {e}")
            return False

    @staticmethod
    def get_tasks_for_day(user_id: int, day_of_week: int):
        """Получает задачи на конкретный день"""
        db = next(get_db())

        try:
            week_dates = TaskService.get_current_week_dates()
            target_date = week_dates[day_of_week]

            task_days = db.query(TaskDay).filter(
                TaskDay.user_id == user_id,
                TaskDay.date == target_date,
                TaskDay.status.in_(['pending', 'partial'])
            ).join(Task).filter(Task.status == 'active').all()

            return task_days

        except Exception as e:
            logger.error(f"Ошибка при получении задач дня: {e}")
            return []