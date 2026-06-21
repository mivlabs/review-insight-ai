import os
import csv
import json
import time
import sqlite3
import logging
import argparse
from openai import OpenAI
from dotenv import load_dotenv
from tqdm import tqdm

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
        
        # Убираем markdown-обёртки
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

def get_processed_texts(cursor) -> set:
    """Получает уже обработанные тексты для resume."""
    cursor.execute("SELECT original_text FROM reviews_analysis")
    return {row[0] for row in cursor.fetchall()}

def main():
    """Основная функция с batch processing."""
    parser = argparse.ArgumentParser(description='Batch review analysis')
    parser.add_argument('--limit', type=int, default=500, 
                        help='Number of reviews to process (default: 500)')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from where left off')
    args = parser.parse_args()
    
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
        
        # Читаем все строки
        rows = list(reader)
    
    logger.info(f"Total reviews in CSV: {len(rows)}")
    logger.info(f"Will process: {min(args.limit, len(rows))} reviews")
    
    # Подключение к SQLite
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Создание таблицы
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_text TEXT UNIQUE,
            sentiment TEXT,
            topics TEXT,
            intent TEXT,
            summary TEXT,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    
    # Resume: получаем уже обработанные тексты
    processed = get_processed_texts(cursor) if args.resume else set()
    logger.info(f"Already processed: {len(processed)} reviews")
    
    # Фильтруем и ограничиваем
    to_process = []
    for row in rows:
        text = row.get(text_col, '')
        if not text or len(text.strip()) < 10:
            continue
        if args.resume and text in processed:
            continue
        to_process.append(text)
        if len(to_process) >= args.limit:
            break
    
    logger.info(f"Reviews to process: {len(to_process)}")
    
    if not to_process:
        logger.info("Nothing to process. Exiting.")
        conn.close()
        return
    
    # Анализ с progress bar
    success_count = 0
    error_count = 0
    
    with tqdm(total=len(to_process), desc="Analyzing reviews") as pbar:
        for text in to_process:
            result = analyze_review(text)
            
            try:
                cursor.execute(
                    'INSERT OR IGNORE INTO reviews_analysis (original_text, sentiment, topics, intent, summary) VALUES (?, ?, ?, ?, ?)',
                    (text, result['sentiment'], json.dumps(result['topics']), result['intent'], result['summary'])
                )
                if cursor.rowcount > 0:
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                logger.error(f"DB error: {e}")
                error_count += 1
            
            conn.commit()
            pbar.update(1)
            time.sleep(0.5)  # Rate limiting
    
    conn.close()
    
    logger.info(f"✅ Done! Success: {success_count}, Errors: {error_count}")
    logger.info(f"Total in DB: {success_count + len(processed)} reviews")

if __name__ == "__main__":
    main()