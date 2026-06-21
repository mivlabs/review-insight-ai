import os
import csv
import json
import time
import sqlite3
import logging
from openai import OpenAI
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Инициализация OpenAI клиента через OpenRouter
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

def analyze_review(text: str) -> dict:
    """Анализирует отзыв через LLM и возвращает JSON."""
    prompt = f"""Analyze this customer review and return a JSON object with the following fields:
- sentiment: 'positive', 'negative', or 'neutral'
- topics: a list of key topics in English (e.g., 'price', 'quality', 'service', 'delivery', 'packaging', 'taste', 'value', 'freshness')
- intent: 'stay', 'leave', or 'unknown'
- summary: a brief summary in English (1-2 sentences)

Review: {text}

Return ONLY valid JSON without any additional text, markdown formatting, or explanations."""

    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-3-8b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        content = response.choices[0].message.content.strip()
        
        # Убираем markdown-обёртки если есть
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        result = json.loads(content)
        
        # Валидация topics
        topics = result.get("topics", [])
        if isinstance(topics, str):
            topics = [topics]
        if not isinstance(topics, list):
            topics = []
        topics = [t for t in topics if isinstance(t, str) and len(t) > 1]
        if not topics:
            topics = ["unknown"]
        result["topics"] = topics
        
        return result
    except Exception as e:
        logger.warning(f"Failed to parse LLM response: {e}")
        return {
            "sentiment": "error",
            "topics": ["unknown"],
            "intent": "unknown",
            "summary": "Error analyzing review"
        }

def main():
    """Основная функция."""
    csv_path = './data/reviews.csv'
    db_path = './data/reviews.db'
    
    # Загрузка CSV
    logger.info(f"Loading CSV from {csv_path}")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        logger.info(f"CSV columns: {columns}")
        
        # Определяем колонку с текстом
        text_col = None
        for col in ['text', 'Text', 'review_text', 'review', 'content', 'Review']:
            if col in columns:
                text_col = col
                break
        
        if not text_col:
            raise ValueError(f"Text column not found. Available: {columns}")
        
        # Определяем колонку с датой
        date_col = None
        for col in ['date', 'Date', 'review_date', 'created_at', 'Time', 'time', 'timestamp']:
            if col in columns:
                date_col = col
                break
        
        # Читаем первые 50 строк
        rows = []
        for i, row in enumerate(reader):
            if i >= 50:
                break
            rows.append(row)
    
    logger.info(f"Loaded {len(rows)} reviews")
    
    # Подключение к SQLite
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Создание таблицы
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_text TEXT,
            sentiment TEXT,
            topics TEXT,
            intent TEXT,
            summary TEXT,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    
    # Анализ каждого отзыва
    for i, row in enumerate(rows):
        text = row.get(text_col, '')
        if not text or len(text.strip()) < 10:
            continue
        
        logger.info(f"Analyzing review {i+1}/{len(rows)}...")
        result = analyze_review(text)
        
        # Вставка в БД
        cursor.execute(
            'INSERT INTO reviews_analysis (original_text, sentiment, topics, intent, summary) VALUES (?, ?, ?, ?, ?)',
            (text, result['sentiment'], json.dumps(result['topics']), result['intent'], result['summary'])
        )
        
        time.sleep(1)
    
    conn.commit()
    conn.close()
    
    logger.info(f"Done. Analyzed: {len(rows)} reviews. Saved to {db_path}")

if __name__ == "__main__":
    main()