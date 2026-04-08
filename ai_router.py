"""
Модуль для интеграции с OpenAI API.
Реализует Few-shot prompting с использованием диалогов из dialogs.json.

ИСПРАВЛЕНИЯ:
- Модель по умолчанию изменена на gpt-4o (gpt-4 устарел и дороже)
- Добавлена обработка нового формата ответа OpenAI SDK v1.x
- Few-shot примеры теперь передаются через отдельные user/assistant сообщения
  (более надёжно, чем вставка в system prompt в виде текста)
"""

import os
import logging
from typing import Dict, Any, List
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

VALID_ROLES = [
    "Активный продавец",
    "Технолог",
    "Экономист",
    "Диспетчер",
    "Руководитель"
]


class AIRouter:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        # ИСПРАВЛЕНО: gpt-4o вместо gpt-4
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")

    def _build_system_prompt(self) -> str:
        return """Ты — интеллектуальный роутер лидов для производственной металлоторговой компании.
Твоя задача — проанализировать входящий лид и определить, какой специалист должен его обработать.

Доступные роли:
1. Активный продавец — первичная обработка, консультация по продуктам, ценам, ассортименту
2. Технолог — технические вопросы, чертежи, спецификации, ГОСТы, производственные нюансы
3. Экономист — ценообразование, сметы, счета, акты сверки, финансовые условия, договоры
4. Диспетчер — логистика, доставка, отгрузка, координация машин, сроки
5. Руководитель — VIP-клиенты, конфликты, претензии, стратегические вопросы, эскалации

Правила:
- Анализируй TITLE и COMMENTS лида
- Отвечай ТОЛЬКО одним из 5 вариантов выше, без пояснений
- Если не уверен — выбирай Активный продавец"""

    def _build_fewshot_messages(self, dialogs: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        ИСПРАВЛЕНО: Few-shot примеры передаются как чередующиеся
        user/assistant сообщения — это стандартный и более надёжный способ.
        """
        messages = []
        for dialog in dialogs[:20]:  # Берём первые 20 примеров
            title = dialog.get("title", dialog.get("TITLE", ""))
            content = dialog.get("content", dialog.get("COMMENTS", dialog.get("text", "")))
            role = dialog.get("role", dialog.get("ROLE", "Активный продавец"))

            messages.append({
                "role": "user",
                "content": f"Тема: {title}\nОписание: {content}"
            })
            messages.append({
                "role": "assistant",
                "content": role
            })
        return messages

    async def classify_lead(
        self,
        title: str,
        comments: str,
        dialogs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Классификация лида с помощью OpenAI API.
        Возвращает словарь с ролью и метаданными.
        """
        system_prompt = self._build_system_prompt()
        fewshot_messages = self._build_fewshot_messages(dialogs)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(fewshot_messages)
        messages.append({
            "role": "user",
            "content": f"Тема: {title}\nОписание: {comments if comments else 'не указано'}"
        })

        try:
            logger.info(f"🤖 Отправка запроса в OpenAI (модель: {self.model})...")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                max_tokens=30,
            )

            ai_response = response.choices[0].message.content.strip()
            logger.info(f"🎯 Ответ AI: '{ai_response}'")

            detected_role = self._normalize_role(ai_response)

            return {
                "success": True,
                "role": detected_role,
                "raw_response": ai_response,
                "confidence": "high" if ai_response in VALID_ROLES else "normalized",
                "tokens_used": response.usage.total_tokens if response.usage else 0
            }

        except Exception as e:
            logger.error(f"❌ Ошибка OpenAI API: {e}")
            return {
                "success": False,
                "role": "Активный продавец",
                "error": str(e),
                "confidence": "fallback"
            }

    def _normalize_role(self, response: str) -> str:
        """Нормализация ответа AI к одной из 5 стандартных ролей."""
        response_lower = response.lower()

        for role in VALID_ROLES:
            if role.lower() in response_lower:
                return role

        if "технолог" in response_lower or "техническ" in response_lower or "инженер" in response_lower:
            return "Технолог"
        elif "экономист" in response_lower or "эконом" in response_lower or "финанс" in response_lower or "бухгалт" in response_lower:
            return "Экономист"
        elif "диспетчер" in response_lower or "логист" in response_lower or "доставк" in response_lower:
            return "Диспетчер"
        elif "руководитель" in response_lower or "директор" in response_lower or "начальник" in response_lower:
            return "Руководитель"
        elif "продавец" in response_lower or "sales" in response_lower or "менеджер" in response_lower:
            return "Активный продавец"

        logger.warning(f"⚠️ Не удалось распознать роль: '{response}'. Fallback → Активный продавец")
        return "Активный продавец"


# Singleton
ai_router = AIRouter()
