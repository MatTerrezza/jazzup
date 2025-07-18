import telebot
import buttons
import database
import os
import threading
import schedule
import time
import pytz
from datetime import datetime
from dotenv import load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply, ReplyKeyboardMarkup, KeyboardButton

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)
ADMIN_IDS = list(map(int, os.getenv('ADMIN_IDS').split(',')))

def is_admin(user_id):
    return user_id in ADMIN_IDS

@bot.message_handler(commands=['start'])
def start_command(message):
    user_name = message.from_user.first_name
    database.add_user_if_not_exists(
        message.chat.id,
        message.from_user.username
    )
    
    if is_admin(message.from_user.id):
        bot.send_message(
            message.chat.id,
            "👑 Добро пожаловать, администратор!",
            reply_markup=buttons.get_admin_keyboard()
        )
    else:
        bot.send_message(
            message.chat.id,
            f"""⭐️Доброго времени суток, {user_name}!  

Рады видеть Вас в системе ежедневной отчетности JAZZ UP

Как она работает?
📅 Каждый будний день мы отправляем Reminder: 
Рабочий отчет поможет сохранить ясность и структуру в бизнес-процессах

📮Для отправки нажмите «Начать отчет» 

🕒 Рекомендуемое время сдачи – до конца рабочего дня

Благодарим за внимательность к деталям!""",
            reply_markup=buttons.get_main_keyboard()
        )

@bot.message_handler(func=lambda m: m.text == "Заполнить отчет")
def ask_for_report(message):
    msg = bot.send_message(
        message.chat.id,
        "📝 Введите ваш отчет:",
        reply_markup=ForceReply()
    )
    bot.register_next_step_handler(msg, save_report)

def save_report(message):
    try:
        report_id = database.add_report(message.from_user.id, message.text)
        bot.send_message(
            message.chat.id,
            "✅ Отчет успешно сохранен!",
            reply_markup=buttons.get_admin_keyboard() if is_admin(message.from_user.id) else buttons.get_main_keyboard()
        )
        
        # Уведомление админов
        user = database.get_user(message.from_user.id)
        user_name = user[1] if user else f"User {message.from_user.id}"
        for admin_id in ADMIN_IDS:
            try:
                bot.send_message(
                    admin_id,
                    f"📩 Новый отчет от {user_name}:\n\n{message.text}"
                )
            except Exception as e:
                print(f"Ошибка уведомления админа {admin_id}: {e}")
    except Exception as e:
        print(f"Ошибка сохранения отчета: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Ошибка при сохранении отчета",
            reply_markup=buttons.get_admin_keyboard() if is_admin(message.from_user.id) else buttons.get_main_keyboard()
        )

@bot.message_handler(func=lambda m: m.text == "Мои отчеты")
def show_my_reports(message):
    reports = database.get_user_reports(message.from_user.id)
    if not reports:
        bot.send_message(
            message.chat.id,
            "У вас пока нет сохраненных отчетов.",
            reply_markup=buttons.get_admin_keyboard() if is_admin(message.from_user.id) else buttons.get_main_keyboard()
        )
        return
    
    bot.send_message(
        message.chat.id,
        "Выберите отчет для управления:",
        reply_markup=buttons.generate_my_reports_inline(message.from_user.id)
    )
def process_edit_report(message, report_id):
    """Обработчик редактирования отчета с автоматическим сохранением старой версии"""
    try:
        # Обновляем отчет в базе данных (старая версия автоматически сохраняется)
        success = database.update_report(
            report_id=report_id,
            new_text=message.text,
            editor_id=message.from_user.id
        )
        
        keyboard = buttons.get_admin_keyboard() if is_admin(message.from_user.id) else buttons.get_main_keyboard()
        
        if success:
            bot.send_message(
                message.chat.id,
                "✅ Отчет успешно обновлен! Старая версия сохранена в архиве.",
                reply_markup=keyboard
            )
        else:
            bot.send_message(
                message.chat.id,
                "❌ Не удалось обновить отчет",
                reply_markup=keyboard
            )
    except Exception as e:
        print(f"Ошибка при редактировании отчета: {e}")
        keyboard = buttons.get_admin_keyboard() if is_admin(message.from_user.id) else buttons.get_main_keyboard()
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при обновлении отчета",
            reply_markup=keyboard
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_"))
def handle_edit_report(call):
    try:
        report_id = call.data.split("_")[1]
        
        if not database.can_edit_report(call.from_user.id, report_id):
            bot.answer_callback_query(call.id, "❌ Вы не можете редактировать этот отчет")
            return
            
        # Получаем старый отчет из базы
        old_report = database.get_report_by_id(report_id)
        if not old_report:
            bot.answer_callback_query(call.id, "❌ Отчет не найден")
            return
            
        old_text = old_report[2]  # report_text находится на 3 позиции
        
        # Отправляем сообщение с ForceReply
        msg = bot.send_message(
            call.message.chat.id,
            "✏️ Редактируйте отчет (старый текст ниже):",
            reply_markup=ForceReply(selective=True)
        )
        
        # Отправляем старый текст как отдельное сообщение
        bot.send_message(
            call.message.chat.id,
            f"Текущий текст:\n\n{old_text}",
            reply_to_message_id=msg.message_id
        )
        
        # Регистрируем обработчик
        bot.register_next_step_handler(msg, process_edit_report, report_id)
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        print(f"Ошибка в handle_edit_report: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка при редактировании")

def reminder_scheduler():                                           #Функция для запуска планировщика напоминаний
    print("Планировщик напоминаний инициализирован")
    
    # Установите правильный часовой пояс (пример для МСК)

    msk = pytz.timezone('Europe/Moscow')
    
    schedule.every().day.at("18:00", tz=msk).do(send_daily_reminder)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

def send_daily_reminder():
    print(f"[{datetime.now()}] Запуск send_daily_reminder")
    try:
        users = database.get_all_users()
        print(f"Найдено пользователей для напоминания: {len(users)}")
        
        for user_id, first_name in users:
            try:
                print(f"Отправка напоминания пользователю {user_id} ({first_name})")
                bot.send_message(
                    user_id,
                    f"⏰ Напоминание для {first_name}: сегодня до 18:00 по МСК нужно сдать отчет!\n"
                    "Нажмите кнопку 'Заполнить отчет'"
                )
            except Exception as e:
                print(f"Ошибка отправки пользователю {user_id}: {str(e)}")
    except Exception as e:
        print(f"Критическая ошибка в send_daily_reminder: {str(e)}")

@bot.message_handler(func=lambda m: m.text == "Правила")
def start_rules(message):
    rules_text = """<b>Правила заполнения ежедневного Рабочего отчета</b>\n\n
1.1 Каждый день в отчёте отражает информацию по работе с указанием конкретных результатов*\n
<b>Обращайте внимание</b> на формулировки в Ваших Рабочих отчетах:\n
<b>'Бронирование номеров' ≠ 'Номера забронированы'</b>, так как в первом случае мы подчеркиваем процесс (до конца неясно, законченный/успешный ли), а во втором - успешный ЦКП работника отдела производства📓\n
1.2 Каждый день в отчёте отражает информацию по работе над разными сделками с указанием их названий🖍\n
1.3 Финальный Рабочий отчет направляется сотрудниками каждый будний день к 19:00🏁"""
    
    bot.send_message(
        message.chat.id,
        rules_text,
        parse_mode='HTML',
        reply_markup=buttons.get_admin_keyboard() if is_admin(message.from_user.id) else buttons.get_main_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == "Просмотреть отчеты" and is_admin(m.from_user.id))
def admin_view_reports(message):
    users = database.get_users_with_reports()
    if not users:
        bot.send_message(message.chat.id, "Нет пользователей с отчетами.")
        return
    
    bot.send_message(
        message.chat.id,
        "Выберите пользователя для просмотра отчетов:",
        reply_markup=buttons.generate_users_inline()
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_inline_buttons(call):
    try:
        if call.data.startswith("myreport_"):
            report_id = call.data.split("_")[1]
            report = database.get_report_by_id(report_id)
            
            if not report:
                bot.answer_callback_query(call.id, "❌ Отчет не найден")
                return
                
            # Распаковываем данные отчета
            r_id, user_id, text, date, edited_by, edited_at = report
            date_str = date.strftime("%d.%m.%Y") if hasattr(date, 'strftime') else date
            
            # Формируем текст сообщения
            message_text = f"📅 <b>Отчет от {date_str}</b>"
            if edited_at:
                edited_time = edited_at.strftime("%d.%m.%Y %H:%M") if hasattr(edited_at, 'strftime') else edited_at
                message_text += f"\n✏️ <i>Редактировано: {edited_time}</i>"
            message_text += f"\n\n{text}"
            
            # Показываем отчет с кнопками действий
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=message_text,
                parse_mode="HTML",
                reply_markup=buttons.generate_my_report_actions_inline(report_id)
            )
        
        # Обработка кнопки "Назад" в разделе "Мои отчеты"
        elif call.data == "back_to_myreports":
            reports = database.get_user_reports(call.from_user.id)
            if not reports:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="📭 У вас пока нет сохраненных отчетов."
                )
                return
                
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="📋 Выберите отчет для управления:",
                reply_markup=buttons.generate_my_reports_inline(call.from_user.id)
            )
        
        # Обработка кнопки редактирования отчета
        elif call.data.startswith("edit_"):
            report_id = call.data.split("_")[1]
            
            if not database.can_edit_report(call.from_user.id, report_id):
                bot.answer_callback_query(call.id, "❌ Вы не можете редактировать этот отчет")
                return
                
            # Получаем текущий текст отчета
            report = database.get_report_by_id(report_id)
            if not report:
                bot.answer_callback_query(call.id, "❌ Отчет не найден")
                return
                
            old_text = report[2]  # report_text
            
            # Отправляем запрос на новый текст
            msg = bot.send_message(
                call.message.chat.id,
                "✏️ Введите новый текст отчета:",
                reply_markup=ForceReply(selective=True)
            )
            
            # Показываем старый текст для справки
            bot.send_message(
                call.message.chat.id,
                f"📄 Текущий текст:\n\n{old_text}",
                reply_to_message_id=msg.message_id
            )
            
            # Регистрируем обработчик следующего сообщения
            bot.register_next_step_handler(msg, process_edit_report, report_id)
        
        # Обработка кнопки удаления отчета
        elif call.data.startswith("delete_"):
            report_id = call.data.split("_")[1]
            
            if not database.can_edit_report(call.from_user.id, report_id):
                bot.answer_callback_query(call.id, "❌ Вы не можете удалить этот отчет")
                return
                
            # Удаляем отчет
            if database.delete_report(report_id):
                bot.answer_callback_query(call.id, "✅ Отчет удален")
                
                # Возвращаемся к списку отчетов
                reports = database.get_user_reports(call.from_user.id)
                if reports:
                    bot.edit_message_text(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        text="📋 Выберите отчет для управления:",
                        reply_markup=buttons.generate_my_reports_inline(call.from_user.id)
                    )
                else:
                    bot.edit_message_text(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        text="📭 У вас больше нет сохраненных отчетов."
                    )
            else:
                bot.answer_callback_query(call.id, "❌ Ошибка при удалении отчета")
        
        # Обработка кнопки "Назад" в админском разделе
        elif call.data == "back_to_users":
            users = database.get_users_with_reports()
            if not users:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="Нет пользователей с отчетами."
                )
                return
                
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Выберите пользователя для просмотра отчетов:",
                reply_markup=buttons.generate_users_inline()
            )
        
        # Обработка выбора пользователя (для админов)
        elif call.data.startswith("user_"):
            user_id = int(call.data.split("_")[1])
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Выберите дату отчета:",
                reply_markup=buttons.generate_user_dates_inline(user_id)
            )
        
        # Обработка выбора отчета (для админов)
        elif call.data.startswith("report_"):
            _, user_id, report_date = call.data.split("_", 2)
            reports = database.get_user_reports(int(user_id))
            
            report_info = None
            for report in reports:
                try:
                    r_id, r_date, r_text, edited_at = report
                    if str(r_date) == report_date:
                        report_info = {
                            'id': r_id,
                            'text': r_text,
                            'edited_at': edited_at
                        }
                        break
                except ValueError:
                    continue
            
            if report_info:
                user = database.get_user(int(user_id))
                user_name = user[1] if user else f"Пользователь {user_id}"
                
                try:
                    formatted_date = datetime.strptime(report_date, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y")
                except:
                    formatted_date = report_date
                
                edited_info = ""
                if report_info['edited_at']:
                    edited_info = f"\n\n<i>(Отредактировано)</i>"
                
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"<b>Отчет {user_name}</b>\n"
                         f"<i>Дата: {formatted_date}</i>\n\n"
                         f"{report_info['text']}"
                         f"{edited_info}",
                    parse_mode="HTML",
                    reply_markup=buttons.generate_report_actions_inline(
                        int(user_id), report_info['id'], report_date
                    )
                )
            else:
                bot.answer_callback_query(call.id, "Отчет не найден")
        
        # Всегда отвечаем на callback_query
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        print(f"Ошибка в обработчике кнопок: {e}")
        bot.answer_callback_query(call.id, "❌ Произошла ошибка")

@bot.message_handler(func=lambda m: m.text == "Мои задачи")
def show_my_tasks(message):
    tasks = database.get_user_tasks(message.from_user.id)
    if not tasks:
        bot.send_message(
            message.chat.id,
            "У вас пока нет сохраненных задач.",
            reply_markup=buttons.get_main_keyboard()
        )
        return
    
    response = "📋 Ваши задачи:\n\n"
    for task in tasks[:10]:  # Последние 10 задач
        try:
            task_id, text, date, completed = task
            date_str = date.strftime("%d.%m.%Y") if isinstance(date, datetime) else date
            status = "✅" if completed else "🟡"
            response += f"{status} {date_str}\n{text}\n\n"
        except ValueError:
            continue
    
    bot.send_message(
        message.chat.id,
        response,
        reply_markup=buttons.get_main_keyboard()
    )
