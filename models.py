from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    language_code = Column(String(10), nullable=True)
    is_bot = Column(Integer, default=0)  # 0 - человек, 1 - бот

    # Дополнительные поля для хранения произвольных данных
    user_data = Column(JSON, nullable=True)  # Для хранения любых данных в JSON формате
    preferences = Column(Text, nullable=True)  # Для текстовых предпочтений

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<User(user_id={self.user_id}, username={self.username})>"


class UserState(Base):
    __tablename__ = "user_states"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    state = Column(String(50), nullable=True)  # Текущее состояние пользователя
    context = Column(JSON, nullable=True)  # Контекст состояния
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<UserState(user_id={self.user_id}, state={self.state})>"