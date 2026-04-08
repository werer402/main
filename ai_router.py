import os
import asyncio
import logging
import subprocess
import sys
import aiohttp
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class AIRouter:
    def __init__(self):
        # Настройки локальной Ollama
        self.url = "http://localhost:11434/v1/chat/completions"
        self.model = "qwen2.5:7b" # Модель, которую скинул Виталик

    async def ensure_ollama_server(self):
        """Проверяет запуск Ollama (код Виталика с исправлениями)"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:11434", timeout=2) as resp:
                    if resp.status == 200:
                        return True
        except:
            pass

        logger.info("🚀 Запуск сервера Ollama...")
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        
        for _ in range(10):
            await asyncio.sleep(1)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get("http://localhost:11434", timeout=1) as resp:
                        if resp.status == 200:
                            logger.info("✅ Ollama поднялась")
                            return True
            except:
                pass
        return False

    def _build_system_prompt(self) -> str:
        return "Ты — диспетчер типографии. Отвечай только одним словом (ролью): Активный продавец, Технолог, Экономист, Диспетчер или Руководитель."

    async def classify_lead(self, text: str) -> Dict[str, Any]:
        # Сначала проверяем сервер
        await self.ensure_ollama_server()

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._build_system_prompt()},
                {"role": "user", "content": f"Классифицируй: {text}"}
            ],
            "temperature": 0.1
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.url, json=payload) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        role = result['choices'][0]['message']['content'].strip()
                        return {"success": True, "role": role}
        except Exception as e:
            logger.error(f"Ошибка локальной нейронки: {e}")
            return {"success": False, "role": "Руководитель"}

ai_router = AIRouter()