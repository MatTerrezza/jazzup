import sqlite3
import os
from dotenv import load_dotenv
import bot
from datetime import datetime  # Добавьте в начало файла

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
        
        
        # Таблица задач
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                task_text TEXT,
                task_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_completed BOOLEAN DEFAULT FALSE,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        conn.commit()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS report_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_id INTEGER,
                user_id INTEGER,
                report_text TEXT,
                report_date TIMESTAMP,
                edited_by INTEGER,
                edited_at TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        conn.commit()
        
def add_task(user_id, task_text):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO tasks (user_id, task_text) 
               VALUES (?, ?)''',
            (user_id, task_text)
        )
        conn.commit()
        return cursor.lastrowid

def get_user_tasks(user_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, task_text, task_date, is_completed 
            FROM tasks 
            WHERE user_id = ?
            ORDER BY task_date DESC
        ''', (user_id,))
        return cursor.fetchall()

def migrate_db():
    """Добавляет недостающие таблицы и колонки в базу данных"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            # Проверяем существующие таблицы
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [table[0] for table in cursor.fetchall()]

            # 1. Миграция таблицы reports
            if 'reports' in tables:
                cursor.execute("PRAGMA table_info(reports)")
                report_columns = [column[1] for column in cursor.fetchall()]
                
                if 'edited_by' not in report_columns:
                    cursor.execute('ALTER TABLE reports ADD COLUMN edited_by INTEGER DEFAULT NULL')
                
                if 'edited_at' not in report_columns:
                    cursor.execute('ALTER TABLE reports ADD COLUMN edited_at TIMESTAMP DEFAULT NULL')

            # 2. Создаем таблицу истории отчетов, если ее нет
            if 'report_history' not in tables:
                cursor.execute('''
                    CREATE TABLE report_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        original_id INTEGER,
                        user_id INTEGER,
                        report_text TEXT,
                        report_date TIMESTAMP,
                        edited_by INTEGER,
                        edited_at TIMESTAMP,
                        FOREIGN KEY(user_id) REFERENCES users(user_id)
                    )
                ''')
                print("Создана таблица report_history")

            # 3. Проверяем таблицу tasks (на всякий случай)
            if 'tasks' in tables:
                cursor.execute("PRAGMA table_info(tasks)")
                task_columns = [column[1] for column in cursor.fetchall()]
                
                if 'is_completed' not in task_columns:
                    cursor.execute('ALTER TABLE tasks ADD COLUMN is_completed BOOLEAN DEFAULT FALSE')

            conn.commit()
            print("Миграция базы данных успешно завершена")
            
        except Exception as e:
            print(f"Ошибка миграции: {e}")
            conn.rollback()
            raise  # Можно убрать raise, если хотите продолжить работу при ошибке

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
            SELECT id, user_id, report_text, report_date, edited_by, edited_at 
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
    """Обновляет текст отчета и автоматически сохраняет старую версию"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            # Получаем текущую дату/время
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Сначала получаем старый отчет
            cursor.execute('SELECT * FROM reports WHERE id = ?', (report_id,))
            old_report = cursor.fetchone()
            
            if not old_report:
                print(f"Отчет с ID {report_id} не найден")
                return False

            # Создаем архивную копию старого отчета
            cursor.execute('''
                INSERT INTO report_history 
                (original_id, user_id, report_text, report_date, edited_by, edited_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                report_id,
                old_report[1],  # user_id
                old_report[2],  # report_text
                old_report[3],  # report_date
                editor_id,
                current_time
            ))
            
            # Обновляем текущий отчет
            cursor.execute('''
                UPDATE reports 
                SET report_text = ?, edited_by = ?, edited_at = ?
                WHERE id = ?
            ''', (new_text, editor_id, current_time, report_id))
            
            conn.commit()
            print(f"Отчет {report_id} успешно обновлен, старая версия сохранена")
            return True
            
        except sqlite3.Error as e:
            print(f"Ошибка SQL при обновлении отчета {report_id}: {e}")
            conn.rollback()
            return False
        except Exception as e:
            print(f"Неожиданная ошибка при обновлении отчета {report_id}: {e}")
            conn.rollback()
            return False
def get_report_history(report_id):
    """Получает историю изменений отчета"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, report_text, edited_at 
            FROM report_history 
            WHERE original_id = ?
            ORDER BY edited_at DESC
        ''', (report_id,))
        return cursor.fetchall()

def can_edit_report(user_id, report_id):
    """Проверяет, может ли пользователь редактировать отчет"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM reports WHERE id = ?', (report_id,))
        report = cursor.fetchone()
        if not report:
            return False
        return user_id == report[0] 

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
