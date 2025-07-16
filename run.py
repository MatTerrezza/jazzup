import threading
from bot import bot, reminder_scheduler
import database
import time

def run_bot():
    print("Бот запущен")
    bot.polling(none_stop=True)

if __name__ == "__main__":
    # Инициализация базы данных
    database.init_db()
    database.migrate_db()
    
    # Запускаем планировщик напоминаний
    reminder_thread = threading.Thread(target=reminder_scheduler, daemon=True)
    reminder_thread.start()
    print("Планировщик напоминаний запущен")
    
    # Запускаем бота в основном потоке
    run_bot()
