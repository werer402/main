"""
Модуль для работы с JSON-файлами данных.
Управляет сотрудниками, лидами, диалогами и отпусками.

ИСПРАВЛЕНИЯ:
- vacations.json читается как список объектов {"id", "name", "status"},
  а не словарь с blacklist_ids (соответствует промту из документа 2)
- Убрана зависимость от дат — статус vacation определяется полем "status"
- Исправлен метод _load_json: теперь синхронный (убран лишний async)
- Исправлена логика was_fallback в process_lead_logic (main.py)
"""

import json
import os
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

ROLES = {
    "Активный продавец": "active_seller",
    "Технолог": "technologist",
    "Экономист": "economist",
    "Диспетчер": "dispatcher",
    "Руководитель": "manager"
}


@dataclass
class Employee:
    id: int
    name: str
    last_name: str
    position: str
    role: Optional[str] = None

    @property
    def full_name(self) -> str:
        return f"{self.name} {self.last_name}"


class DataManager:
    def __init__(
        self,
        employees_path: str = "employees.json",
        leads_path: str = "leads.json",
        dialogs_path: str = "dialogs.json",
        vacations_path: str = "vacations.json"
    ):
        self.employees_path = employees_path
        self.leads_path = leads_path
        self.dialogs_path = dialogs_path
        self.vacations_path = vacations_path

        self._employees: List[Employee] = []
        self._leads: List[Dict[str, Any]] = []
        self._dialogs: List[Dict[str, Any]] = []
        # blacklist_ids — множество int-идентификаторов сотрудников в отпуске
        self._blacklist_ids: set = set()

        self._role_mapping: Dict[str, List[Employee]] = {
            "Активный продавец": [],
            "Технолог": [],
            "Экономист": [],
            "Диспетчер": [],
            "Руководитель": []
        }

    async def load_all(self) -> None:
        """Загрузка всех данных при старте."""
        await self._load_employees()
        await self._load_leads()
        await self._load_dialogs()
        await self._load_vacations()
        self._map_roles()
        logger.info("✅ Все данные загружены успешно")

    def _load_json_sync(self, path: str) -> Any:
        """Синхронная загрузка JSON (вызывается из async через await)."""
        if not os.path.exists(path):
            logger.error(f"❌ Файл не найден: {path}")
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга {path}: {e}")
            return []

    async def _load_employees(self) -> None:
        data = self._load_json_sync(self.employees_path)
        self._employees = []
        for emp in data:
            try:
                employee = Employee(
                    id=int(emp.get("ID", 0)),
                    name=emp.get("NAME", ""),
                    last_name=emp.get("LAST_NAME", ""),
                    position=emp.get("POSITION", "")
                )
                self._employees.append(employee)
            except (ValueError, TypeError) as e:
                logger.warning(f"⚠️ Пропущена запись сотрудника: {e}")
        logger.info(f"👥 Загружено сотрудников: {len(self._employees)}")

    async def _load_leads(self) -> None:
        data = self._load_json_sync(self.leads_path)
        self._leads = data if isinstance(data, list) else data.get("leads", [])
        logger.info(f"📋 Загружено лидов: {len(self._leads)}")

    async def _load_dialogs(self) -> None:
        data = self._load_json_sync(self.dialogs_path)
        self._dialogs = data if isinstance(data, list) else data.get("dialogs", [])
        logger.info(f"💬 Загружено диалогов: {len(self._dialogs)}")

    async def _load_vacations(self) -> None:
        """
        ИСПРАВЛЕНО: vacations.json — список объектов вида:
        [{"id": "42", "name": "Иван Петров", "status": "vacation"}, ...]

        Сотрудник попадает в blacklist только при status == "vacation".
        """
        data = self._load_json_sync(self.vacations_path)

        self._blacklist_ids = set()

        if isinstance(data, list):
            for entry in data:
                if entry.get("status") == "vacation":
                    try:
                        self._blacklist_ids.add(int(entry["id"]))
                    except (KeyError, ValueError) as e:
                        logger.warning(f"⚠️ Некорректная запись в vacations.json: {entry} — {e}")
        else:
            # Поддержка старого формата (словарь с blacklist_ids) как fallback
            self._blacklist_ids = set(data.get("blacklist_ids", []))

        logger.info(f"🏖️ Сотрудников в отпуске: {len(self._blacklist_ids)}")
        logger.info(f"🚫 ID в отпуске: {self._blacklist_ids}")

    def _map_roles(self) -> None:
        """Маппинг сотрудников по ролям на основе должности."""
        role_keywords = {
            "Активный продавец": ["продавец", "sales", "менеджер по продажам", "коммерческий"],
            "Технолог": ["технолог", "tech", "инженер", "производство", "технический"],
            "Экономист": ["экономист", "эконом", "финанс", "бухгалтер", "ценовой"],
            "Диспетчер": ["диспетчер", "dispatch", "логист", "координатор", "оператор"],
            "Руководитель": ["руководитель", "директор", "начальник", "head", "chief", "manager"]
        }

        # Сброс маппинга перед заполнением
        for role in self._role_mapping:
            self._role_mapping[role] = []

        for emp in self._employees:
            position_lower = emp.position.lower()
            assigned = False
            for role, keywords in role_keywords.items():
                if any(kw in position_lower for kw in keywords):
                    emp.role = role
                    self._role_mapping[role].append(emp)
                    assigned = True
                    break
            if not assigned:
                emp.role = "Активный продавец"
                self._role_mapping["Активный продавец"].append(emp)

        for role, emps in self._role_mapping.items():
            logger.info(f"  • {role}: {len(emps)} чел.")

    # ──────────────────────────────────────────────
    # Публичные методы
    # ──────────────────────────────────────────────

    def get_dialogs(self) -> List[Dict[str, Any]]:
        return self._dialogs

    def get_lead_by_id(self, lead_id: int) -> Optional[Dict[str, Any]]:
        for lead in self._leads:
            if int(lead.get("ID", 0)) == lead_id:
                return lead
        return None

    def get_all_leads(self) -> List[Dict[str, Any]]:
        return self._leads

    def get_available_specialist(self, role: str) -> Optional[Employee]:
        """
        Поиск доступного специалиста по роли с учётом отпусков.

        Порядок:
        1. Основной специалист роли — не в отпуске
        2. Дублер из смежных ролей
        3. Любой доступный сотрудник
        4. None — нет никого
        """
        specialists = self._role_mapping.get(role, [])
        available = [s for s in specialists if s.id not in self._blacklist_ids]

        if available:
            chosen = available[0]
            logger.info(f"✅ Назначен основной специалист: {chosen.full_name} (ID: {chosen.id})")
            return chosen

        logger.warning(f"⚠️ Все специалисты роли '{role}' в отпуске!")

        fallback_order = ["Руководитель", "Активный продавец", "Диспетчер", "Технолог", "Экономист"]
        for fallback_role in fallback_order:
            if fallback_role == role:
                continue
            fb_specs = self._role_mapping.get(fallback_role, [])
            available_fb = [s for s in fb_specs if s.id not in self._blacklist_ids]
            if available_fb:
                chosen = available_fb[0]
                logger.info(f"🔄 Назначен дублер из '{fallback_role}': {chosen.full_name} (ID: {chosen.id})")
                return chosen

        all_available = [e for e in self._employees if e.id not in self._blacklist_ids]
        if all_available:
            chosen = all_available[0]
            logger.info(f"🆘 Экстренное назначение: {chosen.full_name} (ID: {chosen.id})")
            return chosen

        logger.error("❌ Нет доступных сотрудников вообще!")
        return None

    def get_employee_by_id(self, emp_id: int) -> Optional[Employee]:
        for emp in self._employees:
            if emp.id == emp_id:
                return emp
        return None

    def is_on_vacation(self, emp_id: int) -> bool:
        return emp_id in self._blacklist_ids

    def get_role_stats(self) -> Dict[str, int]:
        return {role: len(emps) for role, emps in self._role_mapping.items()}


# Singleton
data_manager = DataManager()
