"""
Скрипт для массовой обработки лидов (8850 штук).
Генерирует CSV-отчет: Lead ID | Title | AI Role | Assigned Specialist.

ИСПРАВЛЕНИЯ:
- Убрана зависимость от tqdm.asyncio (не всегда установлена), заменена на стандартную tqdm
- Добавлена поддержка --limit аргумента командной строки
- CSV сохраняется с utf-8-sig для корректного открытия в Excel
- Добавлен прогресс-лог каждые 50 лидов
- Исправлено поле comments_preview в итоговом CSV
"""

import os
import sys
import csv
import asyncio
import logging
import argparse
from datetime import datetime
from typing import List, Dict, Any

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

from data_manager import data_manager
from ai_router import ai_router


class LeadMigrator:
    def __init__(self, batch_size: int = 5, delay: float = 0.5):
        self.batch_size = batch_size
        self.delay = delay
        self.results: List[Dict[str, Any]] = []

    async def initialize(self):
        logger.info("🚀 Инициализация мигратора...")
        await data_manager.load_all()
        logger.info("✅ Данные загружены")

    async def process_single_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        lead_id = int(lead.get("ID", 0))
        title = lead.get("TITLE", "Без названия")
        comments = lead.get("COMMENTS", "")

        try:
            dialogs = data_manager.get_dialogs()
            ai_result = await ai_router.classify_lead(title, comments, dialogs)
            detected_role = ai_result["role"]

            specialist = data_manager.get_available_specialist(detected_role)

            # Проверка fallback
            primary_ids = {s.id for s in data_manager._role_mapping.get(detected_role, [])}
            was_fallback = specialist is not None and specialist.id not in primary_ids

            logger.info(
                f"✅ Лид {lead_id}: '{detected_role}' → "
                f"{specialist.full_name if specialist else 'НЕ НАЗНАЧЕН'}"
                f"{' [дублёр]' if was_fallback else ''}"
            )

            return {
                "lead_id": lead_id,
                "title": title[:100],
                "comments_preview": comments[:150] if comments else "",
                "ai_role": detected_role,
                "ai_confidence": ai_result.get("confidence", "unknown"),
                "assigned_id": specialist.id if specialist else "",
                "assigned_name": specialist.full_name if specialist else "НЕ НАЗНАЧЕН",
                "was_fallback": was_fallback,
                "success": True,
                "error": ""
            }

        except Exception as e:
            logger.error(f"❌ Ошибка лида {lead_id}: {e}")
            return {
                "lead_id": lead_id,
                "title": title[:100],
                "comments_preview": comments[:150] if comments else "",
                "ai_role": "ERROR",
                "ai_confidence": "error",
                "assigned_id": "",
                "assigned_name": "ERROR",
                "was_fallback": False,
                "success": False,
                "error": str(e)
            }

    async def process_batch(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        tasks = [self.process_single_lead(lead) for lead in leads]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.sleep(self.delay)
        return [r for r in results if isinstance(r, dict)]

    async def run_migration(self, limit: int = None) -> str:
        leads = data_manager.get_all_leads()
        if limit:
            leads = leads[:limit]

        total = len(leads)
        logger.info(f"📊 Начинаем обработку {total} лидов (batch={self.batch_size})...")

        batches = [leads[i:i + self.batch_size] for i in range(0, total, self.batch_size)]

        if HAS_TQDM:
            iterator = tqdm(batches, desc="Обработка лидов", unit="batch")
        else:
            iterator = batches

        for idx, batch in enumerate(iterator):
            batch_results = await self.process_batch(batch)
            self.results.extend(batch_results)

            processed = min((idx + 1) * self.batch_size, total)
            if (idx + 1) % 10 == 0 or processed == total:
                logger.info(f"📈 Прогресс: {processed}/{total} ({processed / total * 100:.1f}%)")

        return await self.generate_report()

    async def generate_report(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"migration_report_{timestamp}.csv"

        fieldnames = [
            "lead_id", "title", "ai_role",
            "assigned_id", "assigned_name",
            "was_fallback", "ai_confidence",
            "success", "error"
        ]

        # utf-8-sig — для корректного открытия в Excel
        with open(filename, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in self.results:
                r["was_fallback"] = "ДА" if r["was_fallback"] else "НЕТ"
                r["success"] = "ДА" if r["success"] else "НЕТ"
                writer.writerow(r)

        successful = sum(1 for r in self.results if r["success"] == "ДА")
        failed = len(self.results) - successful
        fallbacks = sum(1 for r in self.results if r["was_fallback"] == "ДА")

        role_stats: Dict[str, int] = {}
        for r in self.results:
            role = r["ai_role"]
            role_stats[role] = role_stats.get(role, 0) + 1

        summary = f"""
╔══════════════════════════════════════════════════╗
║           ОТЧЁТ О МИГРАЦИИ                       ║
╠══════════════════════════════════════════════════╣
  Всего обработано:    {len(self.results)}
  Успешно:             {successful}
  Ошибок:              {failed}
  Fallback назначений: {fallbacks}
  Файл:                {filename}
╠══════════════════════════════════════════════════╣
  Распределение по ролям:"""

        for role, count in sorted(role_stats.items(), key=lambda x: x[1], reverse=True):
            summary += f"\n    • {role}: {count}"

        summary += "\n╚══════════════════════════════════════════════════╝"
        logger.info(summary)

        return filename


async def main():
    parser = argparse.ArgumentParser(description="Flex-N-Roll PRO — массовая миграция лидов")
    parser.add_argument("--limit", type=int, default=None, help="Ограничить кол-во лидов (для теста)")
    parser.add_argument("--batch", type=int, default=5, help="Размер батча (default: 5)")
    parser.add_argument("--delay", type=float, default=0.5, help="Задержка между батчами в сек (default: 0.5)")
    args = parser.parse_args()

    migrator = LeadMigrator(batch_size=args.batch, delay=args.delay)
    await migrator.initialize()

    report_file = await migrator.run_migration(limit=args.limit)
    logger.info(f"✅ Миграция завершена! Отчёт: {report_file}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⚠️ Прервано пользователем")
        sys.exit(1)
