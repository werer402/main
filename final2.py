import torch
import torch.nn.functional as F
from sentence_transformers import SentenceTransformer, util
import json
import os

class FlexRouter:
    def __init__(self, model_name='paraphrase-multilingual-MiniLM-L12-v2', threshold=0.45):
        self.model = SentenceTransformer(model_name)
        self.threshold = threshold
        self.embeddings = None
        self.roles = []
        self.texts = []

    def load_base(self, json_path):
        """Загружает 5000+ диалогов и индексирует их"""
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"Файл {json_path} не найден!")
            
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.texts = [item['messages'][0]['text'] for item in data]
        self.roles = [item['roles'][0] for item in data]
        
        print(f"Индексация {len(self.texts)} записей...")
        self.embeddings = self.model.encode(self.texts, convert_to_tensor=True)
        print("✅ Роутер готов к работе.")

    def get_targets(self, message):
        """Возвращает список ролей, прошедших порог"""
        query_vec = self.model.encode(message, convert_to_tensor=True)
        cosine_scores = util.cos_sim(query_vec, self.embeddings)[0]
        
        # Берем ТОП-15 для анализа
        top_k = 15
        top_results = torch.topk(cosine_scores, k=top_k)
        
        role_stats = {"technologist": [], "economist": [], "dispatcher": [], "sales": [], "manager": []}
        
        for i in range(top_k):
            idx = top_results.indices[i].item()
            score = top_results.values[i].item()
            role = self.roles[idx]
            role_stats[role].append(score)
            
        logits = {}
        for role, scores in role_stats.items():
            logits[role] = sum(scores) / len(scores) if scores else 0.0
            
        # Список тех, кто выше порога
        final_targets = [role for role, score in logits.items() if score >= self.threshold]
        
        # Если никто не прошел порог — отдаем менеджеру (руководителю)
        if not final_targets:
            final_targets = ["manager"]
            
        return final_targets, logits

# Пример для Виталика:
# router = FlexRouter()
# router.load_base('dialogs_big_5000.json')
# roles, debug_logits = router.get_targets("Сделайте расчет")