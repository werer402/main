import json
from datetime import datetime

class ProductionDispatcher:
    def __init__(self, employees_list, vacations_list=None):
        self.employees = employees_list
        self.vacations = vacations_list or []
        
        # Четкое разделение по сферам (позиции из твоего файла employees.json)
        self.sphere_map = {
            "technologist": ["Инженер-технолог", "Начальник цеха ППО"],
            "economist": ["Финансовый директор", "Ведущий специалист отдела сбыта"],
            "sales": ["Специалист по продаже", "Руководитель отдела продаж Москва"],
            "dispatcher": ["Специалист по работе с клиентами", "Начальник отдела закупок и логистики"],
            "manager": ["Директор по продажам", "Бизнес-аналитик"]
        }

    def _is_available(self, emp_id):
        """Проверка: работает ли человек сегодня"""
        today = datetime.now().date()
        for v in self.vacations:
            if str(v.get('employee_id')) == str(emp_id):
                # Формат даты в CRM обычно YYYY-MM-DD
                start = datetime.strptime(v['start'], '%Y-%m-%d').date()
                end = datetime.strptime(v['end'], '%Y-%m-%d').date()
                if start <= today <= end:
                    return False
        return True

    def get_best_from_sphere(self, sphere_name):
        """Находит одного первого доступного человека в конкретной сфере"""
        allowed_positions = self.sphere_map.get(sphere_name, [])
        
        for emp in self.employees:
            if emp['POSITION'] in allowed_positions:
                if self._is_available(emp['ID']):
                    return {"id": emp['ID'], "pos": emp['POSITION']}
        return None

    def route_lead(self, message_text, logits, threshold=0.45):
        """
        Главная функция: 1 логит выше порога = 1 человек из этой сферы
        """
        final_targets = []
        
        # Проверяем каждую сферу отдельно
        for sphere, score in logits.items():
            if score >= threshold:
                person = self.get_best_from_sphere(sphere)
                if person:
                    final_targets.append(person)
        
        # Если ни один логит не прошел порог, отправляем "дежурному" менеджеру
        if not final_targets:
            fallback = self.get_best_from_sphere("manager")
            if fallback:
                final_targets.append(fallback)

        return {
            "msg": message_text,
            "to": final_targets
        }

# --- ПРИМЕР ---
# Если logits = {"technologist": 0.62, "economist": 0.58, "sales": 0.1}
# Результат будет таким:
# {
#   "msg": "Текст сообщения...",
#   "to": [
#     {"id": "51", "pos": "Инженер-технолог"},  <-- Один от технологов
#     {"id": "13", "pos": "Ведущий специалист отдела сбыта"} <-- Один от экономистов
#   ]
# }