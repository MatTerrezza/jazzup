from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
import database
from datetime import datetime


def get_user_keyboard(user_id=None):     #Возвращает клавиатуру в зависимости от роли пользователя

    if user_id is not None and is_admin(user_id):
        return get_admin_keyboard()
    return get_main_keyboard()

def get_main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    btn_report = types.KeyboardButton("Заполнить отчет")
    btn_my_reports = types.KeyboardButton("Мои отчеты")
    btn_tasks = types.KeyboardButton("Добавить задачу")
    btn_my_tasks = types.KeyboardButton("Мои задачи")  # Новая кнопка
    btn_rule = types.KeyboardButton("Правила")
    
    keyboard.add(btn_report, btn_my_reports)
    keyboard.add(btn_tasks, btn_my_tasks)
    keyboard.add(btn_rule)
    
    return keyboard

def get_admin_keyboard():   # Клавиатура для администратора
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    btn_view_reports = types.KeyboardButton("Просмотреть отчеты")

    keyboard.add(btn_view_reports)
    
    return keyboard
    
def generate_my_reports_inline(user_id):
    """Генерирует инлайн-кнопки с отчетами пользователя для управления"""
    markup = types.InlineKeyboardMarkup()
    reports = database.get_user_reports(user_id)
    
    if not reports:
        return markup
    
    for report in reports[:10]:  # Показываем последние 10 отчетов
        try:
            report_id, date, text, edited_at = report
            date_str = date.strftime("%d.%m.%Y") if hasattr(date, 'strftime') else date
            btn_text = f"{date_str} ({'ред.' if edited_at else 'нов.'})"
            
            markup.add(
                types.InlineKeyboardButton(
                    text=btn_text,
                    callback_data=f"myreport_{report_id}"
                )
            )
        except Exception as e:
            print(f"Ошибка обработки отчета: {e}")
            continue
    
    return markup
    
def generate_my_report_actions_inline(report_id):
    """Генерирует кнопки действий с отчетом (редактирование/удаление)"""
    markup = types.InlineKeyboardMarkup()
    
    markup.row(
        types.InlineKeyboardButton(
            text="✏️ Редактировать",
            callback_data=f"edit_{report_id}"
        ),
        types.InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=f"delete_{report_id}"
        )
    )
    
    markup.row(
        types.InlineKeyboardButton(
            text="◀️ Назад к списку",
            callback_data="back_to_myreports"
        )
    )
    
    return markup    
    
def generate_users_inline():
    """Генерирует инлайн-кнопки с пользователями"""
    markup = types.InlineKeyboardMarkup()
    users = database.get_users_with_reports()
    
    if not users:
        return markup
    
    for user_id, first_name in users:
        markup.add(
            types.InlineKeyboardButton(
                text=first_name or f"Пользователь {user_id}",
                callback_data=f"user_{user_id}"
            )
        )
    
    return markup

def generate_user_dates_inline(user_id):
    """Генерирует инлайн-кнопки с датами отчетов пользователя"""
    markup = types.InlineKeyboardMarkup()
    reports = database.get_user_reports(user_id)
    
    if not reports:
        return markup
    
    for report in reports:
        try:
            report_id, report_date, report_text, edited_at = report
            # Преобразуем дату в строку, если это datetime
            date_str = report_date.strftime("%Y-%m-%d %H:%M:%S") if hasattr(report_date, 'strftime') else str(report_date)
            formatted_date = report_date.strftime("%d.%m.%Y") if hasattr(report_date, 'strftime') else report_date
            
            markup.add(
                types.InlineKeyboardButton(
                    text=formatted_date,
                    callback_data=f"report_{user_id}_{date_str}"
                )
            )
        except Exception as e:
            print(f"Ошибка обработки отчета: {e}")
            continue
    
    markup.add(
        types.InlineKeyboardButton(
            text="◀️ Назад к списку пользователей",
            callback_data="back_to_users"
        )
    )
    
    return markup

def generate_report_actions_inline(user_id, report_id, report_date):     #Генерирует кнопки действий с отчетом (редактирование/удаление)

    markup = types.InlineKeyboardMarkup()
    
    markup.add(
        types.InlineKeyboardButton(
            text="✏️ Редактировать",
            callback_data=f"edit_{report_id}"
        ),
        types.InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=f"delete_{report_id}"
        )
    )
    
    markup.add(
        types.InlineKeyboardButton(
            text="◀️ Назад к отчетам",
            callback_data=f"user_{user_id}"
        )
    )
    
    return markup


def process_edit_report(message, report_id):
    try:
        # Обновляем отчет в базе данных
        success = database.update_report(
            report_id=report_id,
            new_text=message.text,
            editor_id=message.from_user.id
        )
        
        if success:
            bot.send_message(
                message.chat.id,
                "✅ Отчет успешно обновлен!",
                reply_markup=buttons.get_main_keyboard()
            )
        else:
            bot.send_message(
                message.chat.id,
                "❌ Не удалось обновить отчет",
                reply_markup=buttons.get_main_keyboard()
            )
    except Exception as e:
        print(f"Ошибка при редактировании отчета: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при обновлении отчета",
            reply_markup=buttons.get_main_keyboard()
        )

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

def generate_my_tasks_inline(user_id):
    """Генерирует инлайн-кнопки с задачами пользователя"""
    markup = InlineKeyboardMarkup()
    tasks = database.get_user_tasks(user_id)
    
    if not tasks:
        return markup
    
    for task in tasks[:10]:  # Показываем последние 10 задач
        try:
            task_id, text, date, completed = task  # Теперь 4 значения вместо 5
            date_str = date.strftime("%d.%m.%Y") if hasattr(date, 'strftime') else str(date)
            btn_text = f"{'✅' if completed else '🟡'} {date_str}"
            
            markup.add(
                InlineKeyboardButton(
                    text=btn_text,
                    callback_data=f"mytask_{task_id}"
                )
            )
        except Exception as e:
            print(f"Ошибка обработки задачи: {e}")
            continue
    
    return markup

def generate_task_actions_inline(task_id):
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("✏️ Редактировать", callback_data=f"edittask_{task_id}"),
        InlineKeyboardButton("✅ Переключить статус", callback_data=f"toggletask_{task_id}")
    )
    markup.row(
        InlineKeyboardButton("🗑 Удалить", callback_data=f"deletetask_{task_id}"),
        InlineKeyboardButton("◀️ Назад", callback_data="back_to_mytasks")
    )
    return markup
