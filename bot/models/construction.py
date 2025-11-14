from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class ConstructionStage(Enum):
    ACCEPTANCE = "Прием фронта работ"
    INSTALLATION = "Монтаж"
    COMPLETION = "Сдача, исполнительная документация"


class ResponsiblePerson:
    def __init__(self, name: str, position: str, phone: str, email: str = ""):
        self.name = name
        self.position = position
        self.phone = phone
        self.email = email


class ConstructionObject:
    def __init__(self, name: str, address: str, object_id: Optional[str] = None):
        self.id = object_id or str(datetime.now().timestamp())
        self.name = name
        self.address = address
        self.created_date = datetime.now()
        self.current_stage = ConstructionStage.ACCEPTANCE
        self.responsible_persons: List[ResponsiblePerson] = []  # УПРОЩАЕМ - просто список
        self.comments: Dict[ConstructionStage, List[str]] = {
            stage: [] for stage in ConstructionStage
        }
        self.is_completed = False
        self.completion_date: Optional[datetime] = None

    def add_responsible_person(self, person: ResponsiblePerson):  # УПРОЩАЕМ метод
        self.responsible_persons.append(person)

    def remove_responsible_person(self, person_index: int):  # УПРОЩАЕМ метод
        if 0 <= person_index < len(self.responsible_persons):
            self.responsible_persons.pop(person_index)
            return True
        return False

    def add_comment(self, stage: ConstructionStage, comment: str):
        self.comments[stage].append(f"{datetime.now().strftime('%d.%m.%Y %H:%M')}: {comment}")

    def move_to_next_stage(self):
        stages = list(ConstructionStage)
        current_index = stages.index(self.current_stage)
        if current_index < len(stages) - 1:
            self.current_stage = stages[current_index + 1]
            return True
        return False

    def complete_object(self):
        self.is_completed = True
        self.completion_date = datetime.now()


class ConstructionManager:
    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.objects: Dict[str, ConstructionObject] = {}

    def add_object(self, name: str, address: str) -> ConstructionObject:
        obj = ConstructionObject(name, address)
        self.objects[obj.id] = obj
        return obj

    def remove_object(self, object_id: str) -> bool:
        if object_id in self.objects:
            del self.objects[object_id]
            return True
        return False

    def get_object(self, object_id: str) -> Optional[ConstructionObject]:
        return self.objects.get(object_id)

    def get_active_objects(self) -> List[ConstructionObject]:
        return [obj for obj in self.objects.values() if not obj.is_completed]

    def get_completed_objects(self) -> List[ConstructionObject]:
        return [obj for obj in self.objects.values() if obj.is_completed]

    def get_objects_by_stage(self, stage: ConstructionStage) -> List[ConstructionObject]:
        return [obj for obj in self.objects.values() if obj.current_stage == stage and not obj.is_completed]