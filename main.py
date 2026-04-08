"""
Главный файл FastAPI приложения.
Принимает вебхуки от Битрикс24, обрабатывает лиды через AI и назначает специалистов.

ИСПРАВЛЕНИЯ:
- Исправлен баг в логике was_fallback (была инвертированная проверка)
- Добавлен эндпоинт /webhook/batch для массовой тестовой обработки
- Улучшены логи: теперь чётко виден весь pipeline
- Добавлена поддержка form-encoded вебхуков Битрикс24 (они слали не JSON!)
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from data_manager import data_manager, Employee
from ai_router import ai_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

load_dotenv()


# ── Pydantic модели ──────────────────────────────────────────

class LeadWebhook(BaseModel):
    event: str = Field(..., description="Тип события Битрикс24")
    data: Dict[str, Any] = Field(..., description="Данные события")
    ts: Optional[int] = Field(None, description="Timestamp")

    class Config:
        extra = "allow"


class ProcessingResult(BaseModel):
    success: bool
    lead_id: int
    title: str
    ai_role: str
    assigned_specialist_id: Optional[int]
    assigned_specialist_name: Optional[str]
    was_fallback: bool
    message: str


# ── Lifespan ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Запуск Flex-N-Roll PRO сервера...")
    await data_manager.load_all()
    logger.info("✅ Сервер готов к работе!")
    yield
    logger.info("🛑 Остановка сервера...")


# ── FastAPI App ───────────────────────────────────────────────

app = FastAPI(
    title="Flex-N-Roll PRO",
    description="AI-роутер лидов для Битрикс24",
    version="1.1.0",
    lifespan=lifespan
)


# ── Основная логика обработки лида ───────────────────────────

async def process_lead_logic(lead_data: Dict[str, Any]) -> ProcessingResult:
    """
    Pipeline обработки лида:
    1. Извлечение данных
    2. AI классификация
    3. Поиск специалиста с учётом отпусков
    4. Формирование результата
    """
    lead_id = int(lead_data.get("ID", 0))
    title = lead_data.get("TITLE", "Без названия")
    comments = lead_data.get("COMMENTS", "")

    logger.info("=" * 60)
    logger.info(f"📥 Пришёл лид ID: {lead_id}")
    logger.info(f"📝 Тема: {title}")
    logger.info(f"💬 Комментарий: {comments[:120] if comments else '(пусто)'}")

    # Шаг 1: AI классификация
    dialogs = data_manager.get_dialogs()
    ai_result = await ai_router.classify_lead(title, comments, dialogs)
    detected_role = ai_result["role"]

    if not ai_result["success"]:
        logger.warning(f"⚠️ AI вернул ошибку, используем fallback роль: {detected_role}")
    else:
        logger.info(f"🎯 AI решил: {detected_role} (уверенность: {ai_result.get('confidence')})")

    # Шаг 2: Проверка отпусков и поиск специалиста
    logger.info(f"🔍 Проверка отпусков для роли '{detected_role}'...")
    specialist = data_manager.get_available_specialist(detected_role)

    if not specialist:
        logger.error("❌ Нет доступных специалистов!")
        return ProcessingResult(
            success=False,
            lead_id=lead_id,
            title=title,
            ai_role=detected_role,
            assigned_specialist_id=None,
            assigned_specialist_name=None,
            was_fallback=False,
            message="Не удалось найти доступного специалиста"
        )

    # ИСПРАВЛЕНО: was_fallback — True если назначенный специалист НЕ из целевой роли
    primary_role_ids = {s.id for s in data_manager._role_mapping.get(detected_role, [])}
    was_fallback = specialist.id not in primary_role_ids

    logger.info(f"📊 Итог: Лид {lead_id} → роль '{detected_role}' → назначен {specialist.full_name} (ID: {specialist.id})")
    if was_fallback:
        logger.warning(f"🔄 Использован дублёр (основные в отпуске)")

    # Шаг 3: (Опционально) Обновление Битрикс24
    await update_bitrix_lead(lead_id, specialist.id)

    return ProcessingResult(
        success=True,
        lead_id=lead_id,
        title=title,
        ai_role=detected_role,
        assigned_specialist_id=specialist.id,
        assigned_specialist_name=specialist.full_name,
        was_fallback=was_fallback,
        message=f"Назначен: {specialist.full_name}"
    )


async def update_bitrix_lead(lead_id: int, assigned_id: int) -> bool:
    """Обновление лида в Битрикс24. Заглушка для демо."""
    webhook_url = os.getenv("BITRIX_WEBHOOK_URL", "")
    if not webhook_url or "your-domain" in webhook_url:
        logger.info(f"ℹ️  [MOCK Bitrix] crm.lead.update → лид {lead_id}, ответственный ID {assigned_id}")
        return False

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{webhook_url}crm.lead.update",
                json={"id": lead_id, "fields": {"ASSIGNED_BY_ID": assigned_id}}
            )
            logger.info(f"🌐 Bitrix ответ: {resp.status_code}")
            return resp.status_code == 200
    except Exception as e:
        logger.error(f"❌ Ошибка обновления Битрикс: {e}")
        return False


# ── Эндпоинты ────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "Flex-N-Roll PRO",
        "version": "1.1.0",
        "endpoints": ["/webhook", "/webhook/test", "/webhook/raw", "/health", "/stats"]
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "employees_loaded": len(data_manager._employees),
        "leads_loaded": len(data_manager._leads),
        "dialogs_loaded": len(data_manager._dialogs),
        "on_vacation": list(data_manager._blacklist_ids)
    }


@app.get("/stats")
async def stats():
    return {
        "roles": data_manager.get_role_stats(),
        "vacations_active": len(data_manager._blacklist_ids),
        "employees_on_vacation_ids": list(data_manager._blacklist_ids)
    }


@app.post("/webhook", response_model=ProcessingResult)
async def webhook_handler(payload: LeadWebhook, background_tasks: BackgroundTasks):
    """
    Основной эндпоинт для вебхуков Битрикс24.
    Принимает события ONCRMLEADADD, ONCRMLEADUPDATE.
    """
    logger.info(f"🔔 Получен вебхук: {payload.event}")

    lead_data = payload.data.get("FIELDS", payload.data)
    normalized = {
        "ID": lead_data.get("ID") or lead_data.get("LEAD_ID", 0),
        "TITLE": lead_data.get("TITLE", lead_data.get("NAME", "Без названия")),
        "COMMENTS": lead_data.get("COMMENTS", lead_data.get("SOURCE_DESCRIPTION", "")),
        "ASSIGNED_BY_ID": lead_data.get("ASSIGNED_BY_ID")
    }

    result = await process_lead_logic(normalized)

    if not result.success:
        raise HTTPException(status_code=500, detail=result.message)

    return result


@app.post("/webhook/test")
async def webhook_test(lead_id: int):
    """Тестовый эндпоинт: обработать конкретный лид по ID из leads.json."""
    lead = data_manager.get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Лид {lead_id} не найден в leads.json")
    return await process_lead_logic(lead)


@app.post("/webhook/raw")
async def webhook_raw(request: Request):
    """
    Эндпоинт для сырых запросов.
    ИСПРАВЛЕНО: Битрикс24 может слать данные как form-encoded, а не JSON.
    """
    content_type = request.headers.get("content-type", "")

    try:
        if "application/json" in content_type:
            body = await request.json()
        elif "application/x-www-form-urlencoded" in content_type:
            form = await request.form()
            body = dict(form)
            # Битрикс присылает данные в виде event[...] ключей
            logger.info(f"📦 Form-encoded вебхук: {list(body.keys())[:5]}")
        else:
            body = await request.json()

        logger.info(f"📦 Raw вебхук: {json.dumps(body, ensure_ascii=False)[:200]}")

        # Пытаемся найти ID лида
        lead_id = (
            body.get("data", {}).get("FIELDS", {}).get("ID")
            or body.get("ID")
        )

        if lead_id:
            lead = data_manager.get_lead_by_id(int(lead_id))
            if lead:
                return await process_lead_logic(lead)

        return {"status": "received", "note": "lead_id не найден в теле запроса"}

    except Exception as e:
        logger.error(f"❌ Ошибка raw webhook: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/webhook/batch-test")
async def webhook_batch_test(limit: int = 5):
    """
    Тестовая массовая обработка — прогоняет первые N лидов из leads.json.
    Удобно для демо на хакатоне без запуска migrate_leads.py.
    """
    leads = data_manager.get_all_leads()[:limit]
    results = []
    for lead in leads:
        result = await process_lead_logic(lead)
        results.append(result.model_dump())
    return {"processed": len(results), "results": results}


# ── Main ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
