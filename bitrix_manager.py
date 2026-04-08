import requests
import json

class BitrixManager:
    def __init__(self):
        # Твой актуальный вебхук из присланных файлов
        self.webhook_url = "https://b24-tmb6tt.bitrix24.by/rest/1/s0z8fofh0w0x73ng/"

    def _call(self, method, params):
        """Внутренний метод для отправки запросов"""
        url = f"{self.webhook_url}{method}.json"
        try:
            response = requests.post(url, json=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ Ошибка Bitrix API ({method}): {e}")
            return None

    def create_lead(self, title, message, assigned_id=1):
        """
        Создает лид. 
        assigned_id — это ID первого спеца, которого нашел ИИ.
        """
        params = {
            "fields": {
                "TITLE": title,
                "COMMENTS": message,
                "STATUS_ID": "NEW",
                "ASSIGNED_BY_ID": assigned_id,
                "SOURCE_ID": "AI_ROUTER" # Пометка, что лид обработан роботом
            }
        }
        result = self._call("crm.lead.add", params)
        if result and "result" in result:
            print(f"✅ Лид создан! ID: {result['result']}")
            return result['result']
        return None

    def send_notification(self, user_id, text):
        """Отправляет персональное сообщение специалисту в чат"""
        params = {
            "DIALOG_ID": user_id,
            "MESSAGE": f"🤖 **AI-Уведомление**\n\n{text}"
        }
        result = self._call("im.message.add", params)
        if result:
            print(f"📧 Сообщение отправлено пользователю ID {user_id}")
        return result

    def route_to_specialists(self, ai_result):
        """
        Метод-связка. Принимает результат от нашего SmartDispatcher.
        ai_result — это словарь вида {'msg': '...', 'to': [{'id': '51', 'pos': '...'}]}
        """
        message_text = ai_result['msg']
        targets = ai_result['to']

        if not targets:
            return

        # 1. Создаем общий лид на первого в списке (основной ответственный)
        main_id = targets[0]['id']
        lead_id = self.create_lead(f"Запрос: {message_text[:30]}...", message_text, main_id)

        # 2. Рассылаем всем спецам (из разных сфер) уведомления
        for target in targets:
            notification = (
                f"Вам назначен новый запрос из сферы: *{target['pos']}*\n"
                f"Текст клиента: {message_text}\n"
                f"Ссылка на лид: https://b24-tmb6tt.bitrix24.by/crm/lead/details/{lead_id}/"
            )
            self.send_notification(target['id'], notification)

# --- ТЕСТОВЫЙ ЗАПУСК ---
if __name__ == "__main__":
    bx = BitrixManager()
    
    # Имитация того, что вернул твой ИИ-роутер
    mock_ai_data = {
        "msg": "Нужна консультация по ламинации ПП и расчет цены",
        "to": [
            {"id": "51", "pos": "Инженер-технолог"},
            {"id": "13", "pos": "Ведущий специалист отдела сбыта"}
        ]
    }
    
    bx.route_to_specialists(mock_ai_data)