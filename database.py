import sqlite3
import uuid
from datetime import datetime

class UserDatabase:
    def __init__(self, db_name="users.db"):
        self.db_name = db_name
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                tg_id INTEGER PRIMARY KEY,   -- Используем Telegram ID как основной ключ
                internal_id TEXT,            -- UUID для системы
                name TEXT,
                last_name TEXT,
                company_title TEXT,
                date_create TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def add_user(self, tg_id, name, last_name, company):
        """Добавляет или обновляет пользователя"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        u_id = str(uuid.uuid4())
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO users (tg_id, internal_id, name, last_name, company_title, date_create)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (tg_id, u_id, name, last_name, company, datetime.now().isoformat()))
            conn.commit()
        finally:
            conn.close()

    def get_user(self, tg_id):
        """Та самая функция для Виталика: достает юзера по его Telegram ID"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT name, last_name, company_title, internal_id FROM users WHERE tg_id = ?", (tg_id,))
        user = cursor.fetchone()
        conn.close()
        return user # Вернет кортеж или None