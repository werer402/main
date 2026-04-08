import requests

class BitrixManager:
    def __init__(self):
        self.webhook_url = "https://b24-tmb6tt.bitrix24.by/rest/1/s0z8fofh0w0x73ng/"

    def create_lead(self, user_data, message_text, assigned_id):
        """
        Принимает кортеж user_data, который Виталик достал из базы.
        (name, last_name, company, internal_id)
        """
        if not user_data:
            return None

        name, last_name, company, u_id = user_data
        
        params = {
            "fields": {
                "TITLE": f"Запрос: {company}",
                "NAME": name,
                "LAST_NAME": last_name,
                "COMMENTS": f"Сообщение: {message_text}\n\nВнутренний ID: {u_id}",
                "ASSIGNED_BY_ID": assigned_id,
                "SOURCE_ID": "TELEGRAM"
            }
        }
        return requests.post(f"{self.webhook_url}crm.lead.add.json", json=params).json()

    def send_notification(self, dialog_id, text):
        """Отправка уведомления сотруднику в чат"""
        params = {"DIALOG_ID": dialog_id, "MESSAGE": f"🤖 AI: {text}"}
        return requests.post(f"{self.webhook_url}im.message.add.json", json=params).json()