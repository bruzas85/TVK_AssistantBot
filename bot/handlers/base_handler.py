from telebot import TeleBot
from typing import Dict
from ..models.user_data import UserData


class BaseHandler:
    def __init__(self, bot: TeleBot, users_data: Dict[int, UserData]):
        self.bot = bot
        self.users_data = users_data

    def get_user_data(self, chat_id: int) -> UserData:
        if chat_id not in self.users_data:
            self.users_data[chat_id] = UserData(chat_id)
        return self.users_data[chat_id]

    def set_user_state(self, chat_id: int, state: str):
        user_data = self.get_user_data(chat_id)
        user_data.state = state

    def get_user_state(self, chat_id: int) -> str:
        user_data = self.get_user_data(chat_id)
        return user_data.state