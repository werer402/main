# Flex-N-Roll PRO 🚀

AI-роутер лидов для Битрикс24. Классифицирует входящие лиды и назначает ответственных специалистов с учётом отпусков.

---

## Структура проекта

```
flex-n-roll-pro/
├── main.py              # FastAPI сервер (вебхуки)
├── ai_router.py         # Интеграция с OpenAI (Few-shot)
├── data_manager.py      # Работа с JSON-данными
├── migrate_leads.py     # Массовая обработка лидов → CSV
├── .env.example         # Пример настроек
├── requirements.txt
├── leads.json           # Лиды (8850 записей)
├── employees.json       # Сотрудники
├── dialogs.json         # 30 обучающих примеров (Few-shot)
└── vacations.json       # Список сотрудников в отпуске
```

---

## Формат vacations.json

```json
[
  {"id": "42", "name": "Иван Петров", "status": "vacation"},
  {"id": "23", "name": "Ольга Козлова", "status": "active"}
]
```

Только записи со `"status": "vacation"` попадают в blacklist.

---

## Запуск

### 1. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 2. Настройка .env
```bash
cp .env.example .env
# Вставь свой OPENAI_API_KEY
```

### 3. Запуск сервера
```bash
python main.py
# или
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Запуск ngrok (в отдельном терминале)
```bash
ngrok http 8000
```
Скопируй `https://....ngrok-free.app` → вставь в настройки вебхука Битрикс24.

### 5. Массовая миграция лидов
```bash
# Все лиды
python migrate_leads.py

# Первые 50 лидов (для теста/демо)
python migrate_leads.py --limit 50

# С увеличенным батчем
python migrate_leads.py --limit 100 --batch 10
```

---

## Эндпоинты

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/` | Health check |
| GET | `/health` | Статус данных |
| GET | `/stats` | Статистика ролей |
| POST | `/webhook` | Вебхук от Битрикс24 (JSON) |
| POST | `/webhook/raw` | Сырой вебхук (JSON или form-encoded) |
| POST | `/webhook/test?lead_id=10001` | Тест по ID из leads.json |
| POST | `/webhook/batch-test?limit=5` | Демо: обработать N лидов |

---

## Роли

| Роль | Когда назначается |
|------|-------------------|
| Активный продавец | Первичные запросы, прайс, ассортимент |
| Технолог | Чертежи, ГОСТы, технические вопросы |
| Экономист | Сметы, счета, акты сверки |
| Диспетчер | Доставка, отгрузка, логистика |
| Руководитель | VIP, претензии, конфликты, эскалации |

---

## Что было исправлено

1. **vacations.json** — формат изменён на список объектов `{id, name, status}` согласно промту (было: словарь с `blacklist_ids` и датами)
2. **was_fallback логика** — исправлена инвертированная проверка в `main.py`
3. **Few-shot prompting** — примеры теперь передаются как `user/assistant` сообщения (надёжнее вставки в system prompt)
4. **Модель OpenAI** — `gpt-4o` вместо устаревшего `gpt-4`
5. **Поддержка form-encoded** вебхуков Битрикс24 в `/webhook/raw`
6. **migrate_leads.py** — добавлены `--limit`, `--batch`, `--delay` аргументы
7. **_load_json** — убран лишний async, теперь синхронный метод
