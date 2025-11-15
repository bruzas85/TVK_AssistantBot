import json
import os
from datetime import datetime
from typing import Dict, List


class JSONStorageService:
    def __init__(self, storage_dir: str = "data"):
        self.storage_dir = storage_dir
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)

    def save_user_data(self, user_data):
        """Сохраняет данные пользователя в JSON файл"""
        try:
            filename = os.path.join(self.storage_dir, f"user_{user_data.chat_id}.json")

            # Преобразуем данные в JSON-совместимый формат
            data = {
                'chat_id': user_data.chat_id,
                'state': user_data.state,
                'expenses': [
                    {
                        'date': exp.date.isoformat(),
                        'category': exp.category,
                        'amount': exp.amount,
                        'description': exp.description,
                        'type': exp.type
                    } for exp in user_data.expenses
                ],
                'timesheet': {
                    'employees': [
                        {
                            'id': emp.id,
                            'name': emp.name,
                            'daily_salary': emp.daily_salary,
                            'created_date': emp.created_date.isoformat()
                        } for emp in user_data.timesheet.employees.values()
                    ],
                    'attendance_records': [
                        {
                            'employee_id': rec.employee_id,
                            'work_date': rec.work_date.isoformat(),
                            'is_present': rec.is_present,
                            'is_locked': rec.is_locked
                        } for rec in user_data.timesheet.attendance_records
                    ]
                },
                'construction_manager': {
                    'objects': [
                        {
                            'id': obj.id,
                            'name': obj.name,
                            'address': obj.address,
                            'created_date': obj.created_date.isoformat(),
                            'current_stage': obj.current_stage.name,
                            'responsible_persons': [
                                {
                                    'name': person.name,
                                    'position': person.position,
                                    'phone': person.phone,
                                    'email': person.email
                                } for person in obj.responsible_persons
                            ],
                            'comments': {
                                stage.name: comments for stage, comments in obj.comments.items()
                            },
                            'is_completed': obj.is_completed,
                            'completion_date': obj.completion_date.isoformat() if obj.completion_date else None
                        } for obj in user_data.construction_manager.objects.values()
                    ]
                },
                # ДОБАВЛЯЕМ RUNNING LIST ДАННЫЕ
                'running_list': {
                    'tasks': [
                        {
                            'id': task.id,
                            'description': task.description,
                            'priority': task.priority.name,
                            'created_date': task.created_date.isoformat(),
                            'is_completed': task.is_completed,
                            'completed_date': task.completed_date.isoformat() if task.completed_date else None,
                            'due_date': task.due_date.isoformat() if task.due_date else None
                        } for task in user_data.running_list.tasks
                    ]
                },
                'last_updated': datetime.now().isoformat()
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print(f"✅ Данные пользователя {user_data.chat_id} сохранены")

        except Exception as e:
            print(f"❌ Ошибка сохранения данных пользователя {user_data.chat_id}: {e}")

    def load_user_data(self, chat_id: int):
        """Загружает данные пользователя из JSON файла"""
        filename = os.path.join(self.storage_dir, f"user_{chat_id}.json")

        if not os.path.exists(filename):
            print(f"Файл данных для пользователя {chat_id} не найден, создаем новый")
            # Импортируем здесь, чтобы избежать циклических импортов
            from ..models.user_data import UserData
            return UserData(chat_id)

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Импортируем здесь, чтобы избежать циклических импортов
            from ..models.user_data import UserData, Expense
            from ..models.timesheet import Employee, AttendanceRecord, Timesheet
            from ..models.construction import ConstructionStage, ResponsiblePerson, ConstructionObject, \
                ConstructionManager
            from ..models.running_list import RunningTask, TaskPriority, RunningList

            user_data = UserData(chat_id)
            user_data.state = data.get('state', 'main_menu')

            # Восстанавливаем расходы
            for exp_data in data.get('expenses', []):
                expense = Expense(
                    category=exp_data['category'],
                    amount=exp_data['amount'],
                    description=exp_data['description'],
                    expense_type=exp_data['type'],
                    date=datetime.fromisoformat(exp_data['date'])
                )
                user_data.expenses.append(expense)

            # Восстанавливаем табель
            timesheet = user_data.timesheet

            # Восстанавливаем сотрудников
            for emp_data in data.get('timesheet', {}).get('employees', []):
                employee = Employee(
                    name=emp_data['name'],
                    daily_salary=emp_data['daily_salary'],
                    employee_id=emp_data['id']
                )
                employee.created_date = datetime.fromisoformat(emp_data['created_date'])
                timesheet.employees[employee.id] = employee

            # Восстанавливаем записи посещаемости
            for rec_data in data.get('timesheet', {}).get('attendance_records', []):
                record = AttendanceRecord(
                    employee_id=rec_data['employee_id'],
                    work_date=datetime.fromisoformat(rec_data['work_date']).date(),
                    is_present=rec_data['is_present']
                )
                record.is_locked = rec_data['is_locked']
                timesheet.attendance_records.append(record)

            # Восстанавливаем строительные объекты
            construction_manager = user_data.construction_manager

            for obj_data in data.get('construction_manager', {}).get('objects', []):
                obj = ConstructionObject(
                    name=obj_data['name'],
                    address=obj_data['address'],
                    object_id=obj_data['id']
                )
                obj.created_date = datetime.fromisoformat(obj_data['created_date'])
                obj.current_stage = ConstructionStage[obj_data['current_stage']]
                obj.is_completed = obj_data['is_completed']

                if obj_data['completion_date']:
                    obj.completion_date = datetime.fromisoformat(obj_data['completion_date'])

                # Восстанавливаем ответственных лиц
                for person_data in obj_data.get('responsible_persons', []):
                    person = ResponsiblePerson(
                        name=person_data['name'],
                        position=person_data['position'],
                        phone=person_data['phone'],
                        email=person_data.get('email', '')
                    )
                    obj.responsible_persons.append(person)

                # Восстанавливаем комментарии
                for stage_name, comments in obj_data.get('comments', {}).items():
                    stage = ConstructionStage[stage_name]
                    obj.comments[stage] = comments

                construction_manager.objects[obj.id] = obj

            # ВОССТАНАВЛИВАЕМ RUNNING LIST ДАННЫЕ
            running_list = user_data.running_list

            for task_data in data.get('running_list', {}).get('tasks', []):
                try:
                    task = RunningTask(
                        description=task_data['description'],
                        priority=TaskPriority[task_data['priority']],
                        task_id=task_data['id']
                    )
                    task.created_date = datetime.fromisoformat(task_data['created_date'])
                    task.is_completed = task_data['is_completed']

                    if task_data['completed_date']:
                        task.completed_date = datetime.fromisoformat(task_data['completed_date'])

                    if task_data['due_date']:
                        task.due_date = datetime.fromisoformat(task_data['due_date'])

                    running_list.tasks.append(task)

                except KeyError as e:
                    print(f"Ошибка загрузки задачи running list: {e}")
                    continue

            print(f"✅ Данные пользователя {chat_id} загружены")
            return user_data

        except Exception as e:
            print(f"❌ Ошибка загрузки данных для пользователя {chat_id}: {e}")
            from ..models.user_data import UserData
            return UserData(chat_id)

    def save_all_data(self, users_data: Dict[int, object]):
        """Сохраняет данные всех пользователей"""
        print(f"💾 Сохранение данных {len(users_data)} пользователей...")
        for user_data in users_data.values():
            self.save_user_data(user_data)
        print("✅ Все данные сохранены!")

    def load_all_data(self) -> Dict[int, object]:
        """Загружает данные всех пользователей"""
        users_data = {}

        if not os.path.exists(self.storage_dir):
            print("📁 Папка данных не существует, создаем новую")
            return users_data

        print("🔄 Загрузка данных пользователей...")
        for filename in os.listdir(self.storage_dir):
            if filename.startswith("user_") and filename.endswith(".json"):
                try:
                    chat_id = int(filename[5:-5])  # извлекаем chat_id из "user_12345.json"
                    user_data = self.load_user_data(chat_id)
                    users_data[chat_id] = user_data
                except ValueError as e:
                    print(f"✗ Ошибка обработки файла {filename}: {e}")
                    continue

        print(f"✅ Загружены данные {len(users_data)} пользователей")
        return users_data