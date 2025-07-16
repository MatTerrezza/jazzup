import sqlite3
import os
from dotenv import load_dotenv
import bot

load_dotenv()

DB_NAME = os.getenv("DB_NAME", "telegram_bot.db")

def get_db_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Обновленная таблица отчетов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                report_text TEXT,
                report_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                edited_by INTEGER DEFAULT NULL,
                edited_at TIMESTAMP DEFAULT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        conn.commit()

def migrate_db():
    """Добавляет недостающие колонки в существующую таблицу reports"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            # Проверяем существующие колонки
            cursor.execute("PRAGMA table_info(reports)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'edited_by' not in columns:
                cursor.execute('ALTER TABLE reports ADD COLUMN edited_by INTEGER DEFAULT NULL')
            
            if 'edited_at' not in columns:
                cursor.execute('ALTER TABLE reports ADD COLUMN edited_at TIMESTAMP DEFAULT NULL')
            
            conn.commit()
        except Exception as e:
            print(f"Ошибка миграции: {e}")
            conn.rollback()

def add_user_if_not_exists(user_id, first_name=None, username=None):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT OR IGNORE INTO users (user_id, first_name, username) 
               VALUES (?, ?, ?)''',
            (user_id, first_name, username)
        )
        conn.commit()

def get_user(user_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return cursor.fetchone()

def get_all_users():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, first_name FROM users')
        return cursor.fetchall()

def get_report_by_id(report_id):
    """Получает отчет по его ID"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, user_id, report_text, report_date 
            FROM reports 
            WHERE id = ?
        ''', (report_id,))
        return cursor.fetchone()

def add_report(user_id, report_text):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO reports (user_id, report_text) 
               VALUES (?, ?)''',
            (user_id, report_text)
        )
        conn.commit()
        return cursor.lastrowid

def get_user_reports(user_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, report_date, report_text, edited_at 
            FROM reports 
            WHERE user_id = ?
            ORDER BY report_date DESC
        ''', (user_id,))
        return cursor.fetchall()

def get_users_with_reports():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT u.user_id, u.first_name 
            FROM users u
            JOIN reports r ON u.user_id = r.user_id
            ORDER BY u.first_name
        ''')
        return cursor.fetchall()

def update_report(report_id, new_text, editor_id):
    """Обновляет текст отчета"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE reports 
                SET report_text = ?, edited_by = ?, edited_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_text, editor_id, report_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Ошибка обновления отчета: {e}")
            return False

def can_edit_report(user_id, report_id):
    """Проверяет, может ли пользователь редактировать отчет"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM reports WHERE id = ?', (report_id,))
        report = cursor.fetchone()
        if not report:
            return False
        return user_id == report[0] or user_id in ADMIN_IDS

def delete_report(report_id):
    """Удаляет отчет по ID"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM reports WHERE id = ?', (report_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Ошибка удаления отчета: {e}")
            return False

# Инициализация базы данных
init_db()
migrate_db()
