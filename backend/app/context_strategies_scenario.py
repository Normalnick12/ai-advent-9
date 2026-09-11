"""Visible source fixtures; intentionally no final expected-answer reference table."""
from app.context_strategies_models import SCENARIO, evaluation_question

ACK = "Ответь только: Принято. Не повторяй требования из диалога."
FIXTURES = (
    "Собираем ТЗ продукта. Область требований: shared.\ngoal=бронирование переговорных\nplatform=Android",
    "Область требований: shared. Первоначальные параметры пилота:\ndeadline_weeks=8\npilot_users=37",
    "Область требований: shared. Нужен offline просмотр ранее загруженного расписания; банковские карты не храним.\noffline_schedule=true\nstores_card_data=false",
    "Область требований: shared. Предпочитаем спокойный интерфейс и пока включаем email-напоминания.\nstyle=спокойный\nemail_reminders=true",
    "Область требований: shared. Исправляю срок с 8 на 6 недель; принимаем вход по magic link.\ndeadline_weeks=6\nauth=magic_link",
    "Область требований: shared. Договорились, что ТЗ согласует Мира. Ранее включённые email-напоминания отменяю.\napprover=Мира\nemail_reminders=cleared",
    "Область требований: A. Это отдельная альтернатива продукта с общими требованиями shared.\npayment=on_site\nconfirmation=immediate\nОплата на месте, бронирование подтверждается сразу.",
    "Область требований: B. Это отдельная альтернатива продукта с общими требованиями shared. Альтернативу A не отменяем и не изменяем.\npayment=link\nconfirmation=admin\nОплата по ссылке, бронирование подтверждает администратор.",
)
FIXTURES = tuple(text + "\n" + ACK for text in FIXTURES)
TITLES = ("Цель и платформа", "Параметры пилота", "Ограничения", "Предпочтения",
          "Корректировка требований", "Договорённости", "Альтернатива A", "Альтернатива B")


def target_for(strategy, step):
    return ("A" if step == 7 else "B") if strategy == "branches" and step > 6 else "root"


def catalog():
    return {"scenario_version": SCENARIO, "steps": [
        {"step_id": i, "title": title, "text": text,
         "preview": [line for line in text.splitlines() if "=" in line]}
        for i, (title, text) in enumerate(zip(TITLES, FIXTURES), 1)],
        "questions": {v: evaluation_question(v) for v in ("A", "B")}}
