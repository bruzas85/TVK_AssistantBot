import logging
from sqlalchemy.orm import Session
from models import User, UserState
from database import get_db
import json

logger = logging.getLogger(__name__)


class UserService:
    @staticmethod
    def get_or_create_user(user_id: int, username: str = None, first_name: str = None,
                           last_name: str = None, language_code: str = None, is_bot: bool = False):
        """
        Получает пользователя из базы или создает нового
        """
        db = next(get_db())

        try:
            user = db.query(User).filter(User.user_id == user_id).first()

            if not user:
                user = User(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    language_code=language_code,
                    is_bot=1 if is_bot else 0
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info(f"Создан новый пользователь: {user_id}")
            else:
                # Обновляем данные существующего пользователя
                update_data = {}
                if username and username != user.username:
                    update_data['username'] = username
                if first_name and first_name != user.first_name:
                    update_data['first_name'] = first_name
                if last_name and last_name != user.last_name:
                    update_data['last_name'] = last_name

                if update_data:
                    db.query(User).filter(User.user_id == user_id).update(update_data)
                    db.commit()
                    logger.info(f"Обновлены данные пользователя: {user_id}")

            return user

        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка при работе с пользователем {user_id}: {e}")
            raise

    @staticmethod
    def update_user_data(user_id: int, phone: str = None, email: str = None,
                         preferences: dict = None, **kwargs):
        """
        Обновляет дополнительные данные пользователя
        """
        db = next(get_db())

        try:
            user = db.query(User).filter(User.user_id == user_id).first()
            if not user:
                logger.warning(f"Пользователь {user_id} не найден")
                return None

            update_data = {}
            if phone is not None:
                update_data['phone'] = phone
            if email is not None:
                update_data['email'] = email
            if preferences is not None:
                # Объединяем существующие предпочтения с новыми
                existing_prefs = {}
                if user.preferences:
                    try:
                        existing_prefs = json.loads(user.preferences)
                    except json.JSONDecodeError:
                        pass

                existing_prefs.update(preferences)
                update_data['preferences'] = json.dumps(existing_prefs, ensure_ascii=False)

            # Обновляем user_data (для произвольных данных)
            if kwargs:
                existing_data = user.user_data or {}
                existing_data.update(kwargs)
                update_data['user_data'] = existing_data

            if update_data:
                db.query(User).filter(User.user_id == user_id).update(update_data)
                db.commit()
                logger.info(f"Обновлены данные пользователя {user_id}")

            return True

        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка при обновлении данных пользователя {user_id}: {e}")
            return False

    @staticmethod
    def get_user_data(user_id: int):
        """
        Получает все данные пользователя
        """
        db = next(get_db())

        try:
            user = db.query(User).filter(User.user_id == user_id).first()
            if user and user.preferences:
                try:
                    user.preferences = json.loads(user.preferences)
                except json.JSONDecodeError:
                    user.preferences = {}
            return user
        except Exception as e:
            logger.error(f"Ошибка при получении данных пользователя {user_id}: {e}")
            return None

    @staticmethod
    def save_user_state(user_id: int, state: str, context: dict = None):
        """
        Сохраняет состояние пользователя
        """
        db = next(get_db())

        try:
            user_state = db.query(UserState).filter(UserState.user_id == user_id).first()

            if user_state:
                user_state.state = state
                user_state.context = context
            else:
                user_state = UserState(
                    user_id=user_id,
                    state=state,
                    context=context
                )
                db.add(user_state)

            db.commit()
            logger.info(f"Сохранено состояние для пользователя {user_id}: {state}")
            return True

        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка при сохранении состояния пользователя {user_id}: {e}")
            return False

    @staticmethod
    def get_user_state(user_id: int):
        """
        Получает состояние пользователя
        """
        db = next(get_db())

        try:
            user_state = db.query(UserState).filter(UserState.user_id == user_id).first()
            return user_state
        except Exception as e:
            logger.error(f"Ошибка при получении состояния пользователя {user_id}: {e}")
            return None

    @staticmethod
    def clear_user_state(user_id: int):
        """
        Очищает состояние пользователя
        """
        db = next(get_db())

        try:
            user_state = db.query(UserState).filter(UserState.user_id == user_id).first()
            if user_state:
                db.delete(user_state)
                db.commit()
                logger.info(f"Очищено состояние пользователя {user_id}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка при очистке состояния пользователя {user_id}: {e}")
            return False