import os
from sqlalchemy import create_engine, text


def run_migrations():
    database_url = os.getenv('DATABASE_URL')
    engine = create_engine(database_url)

    # SQL для создания таблицы running_tasks
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS running_tasks (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        task_text TEXT NOT NULL,
        priority VARCHAR(20) DEFAULT 'medium',
        days_of_week TEXT,
        status_history TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    with engine.connect() as conn:
        conn.execute(text(create_table_sql))
        conn.commit()

    print("✅ Миграции успешно применены")


if __name__ == '__main__':
    run_migrations()