import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Соответствие ролей из AI ролям/ключам в системе
ROLES_LIST = ["Активный продавец", "Технолог", "Экономист", "Диспетчер", "Руководитель"]

@dataclass
class Employee:
    id: str
    name: str
    last_name: str
    position: str
    role: str

    @property
    def full_name(self) -> str:
        return f"{self.name} {self.last_name}"

class DataManager:
    def __init__(self):
        self._employees: List[Employee] = []
        self._leads: List[Dict[str, Any]] = []
        self._blacklist_ids: List[str] = []  # Список ID тех, кто в отпуске

    async def load_all(self):
        """Загрузка всех данных из JSON файлов"""
        try:
            # 1. Загрузка сотрудников
            with open('employees.json', 'r', encoding='utf-8') as f:
                emp_data = json.load(f)
                self._employees = []
                for e in emp_data:
                    eid = str(e.get('ID'))
                    # Принудительный маппинг ролей на основе ID из твоего файла
                    role = "Активный продавец" # По умолчанию
                    if eid in ["145"]: role = "Технолог"
                    elif eid in ["1", "21"]: role = "Руководитель"
                    elif eid in ["13", "23"]: role = "Экономист"
                    elif eid in ["155"]: role = "Диспетчер"
                    
                    self._employees.append(Employee(
                        id=eid,
                        name=e.get('NAME', ''),
                        last_name=e.get('LAST_NAME', ''),
                        position=e.get('POSITION', ''),
                        role=role
                    ))
            logger.info(f"✅ Загружено сотрудников: {len(self._employees)}")

            # 2. Загрузка лидов
            with open('leads.json', 'r', encoding='utf-8') as f:
                self._leads = json.load(f)
            logger.info(f"✅ Загружено лидов: {len(self._leads)}")

            # 3. Загрузка отпусков (черный список)
            if os.path.exists('vacations.json'):
                with open('vacations.json', 'r', encoding='utf-8') as f:
                    v_data = json.load(f)
                    # Собираем только тех, у кого статус vacation
                    self._blacklist_ids = [str(v['id']) for v in v_data if v.get('status') == 'vacation']
            logger.info(f"✅ Сотрудников в отпуске: {len(self._blacklist_ids)}")

        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке данных: {e}")

    def get_lead_by_id(self, lead_id: int) -> Optional[Dict[str, Any]]:
        """Поиск лида в базе по ID"""
        for lead in self._leads:
            if str(lead.get('ID')) == str(lead_id):
                return lead
        return None

    def get_all_leads(self) -> List[Dict[str, Any]]:
        return self._leads

    def get_best_specialist(self, role: str) -> Employee:
        """
        Находит лучшего сотрудника для роли. 
        Если основной сотрудник в отпуске, ищет дублера.
        """
        # 1. Пытаемся найти доступных специалистов нужной роли
        available_specs = [
            e for e in self._employees 
            if e.role == role and e.id not in self._blacklist_ids
        ]

        if available_specs:
            chosen = available_specs[0]
            logger.info(f"🎯 Выбран специалист: {chosen.full_name} (ID: {chosen.id}) на роль {role}")
            return chosen

        # 2. Если все в отпуске — ищем Руководителя (ID 1 или 21)
        logger.warning(f"⚠️ Специалисты роли {role} недоступны (отпуск). Ищу замену...")
        
        fallback_bosses = [
            e for e in self._employees 
            if e.role == "Руководитель" and e.id not in self._blacklist_ids
        ]
        
        if fallback_bosses:
            return fallback_bosses[0]

        # 3. Крайний случай: возвращаем самого первого доступного сотрудника в базе
        for e in self._employees:
            if e.id not in self._blacklist_ids:
                return e

        # Если вообще все в отпуске (апокалипсис)
        return self._employees[0]

    def is_on_vacation(self, emp_id: str) -> bool:
        return str(emp_id) in self._blacklist_ids

data_manager = DataManager()