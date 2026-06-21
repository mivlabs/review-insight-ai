"""Скрипт загрузки и LLM-анализа клиентских отзывов из CSV в SQLite."""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import time
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

CSV_PATH = "./data/reviews.csv"
DB_PATH = "./data/reviews.db"
DEMO_LIMIT = 50
API_DELAY_SECONDS = 1

ANALYSIS_PROMPT = """Analyze this customer review and return a JSON object with the following fields:
- sentiment: 'positive', 'negative', or 'neutral'
- topics: a list of key topics in English (e.g., 'price', 'quality', 'service', 'delivery', 'packaging', 'taste', 'value', 'freshness')
- intent: 'stay' (customer wants to return), 'leave' (customer wants to stop using the service), or 'unknown'
- summary: a brief summary in English (1-2 sentences)

Review: {text}

Return ONLY valid JSON without any additional text, markdown formatting, or explanations."""

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS reviews_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_text TEXT,
    sentiment TEXT,
    topics TEXT,
    intent TEXT,
    summary TEXT,
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

INSERT_SQL = """
INSERT INTO reviews_analysis (original_text, sentiment, topics, intent, summary)
VALUES (?, ?, ?, ?, ?);
"""

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def create_llm_client() -> ChatOpenAI:
    """Создаёт клиент OpenRouter через LangChain ChatOpenAI."""
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("Переменная окружения OPENROUTER_API_KEY не задана")

    return ChatOpenAI(
        model="meta-llama/llama-3-8b-instruct",
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )


def extract_json(text: str) -> str:
    """Извлекает JSON из ответа LLM, убирая markdown-обёртку при необходимости."""
    cleaned = text.strip()
    fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
    if fenced_match:
        return fenced_match.group(1).strip()
    return cleaned


def analyze_review(llm: ChatOpenAI, text: str) -> dict[str, Any]:
    """
    Отправляет отзыв в LLM и возвращает распарсенный JSON.

    При ошибке парсинга возвращает словарь с полем 'error'.
    """
    prompt = ANALYSIS_PROMPT.format(text=text)

    try:
        response = llm.invoke(prompt)
        raw_content = response.content if hasattr(response, "content") else str(response)
        parsed = json.loads(extract_json(raw_content))
        return parsed
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("Не удалось распарсить ответ LLM: %s", exc)
        return {"error": "error"}
    except Exception as exc:
        logger.error("Ошибка при запросе к LLM: %s", exc)
        return {"error": "error"}


def normalize_analysis(result: dict[str, Any]) -> tuple[str, str, str, str]:
    """Приводит результат анализа к полям для записи в БД."""
    if "error" in result:
        return "error", json.dumps("error"), "error", "error"

    sentiment = str(result.get("sentiment", "unknown"))
    intent = str(result.get("intent", "unknown"))
    summary = str(result.get("summary", ""))

    topics_raw = result.get("topics", [])
    if isinstance(topics_raw, list):
        topics = json.dumps(topics_raw, ensure_ascii=False)
    else:
        topics = json.dumps(topics_raw, ensure_ascii=False)

    return sentiment, topics, intent, summary


def ensure_table(conn: sqlite3.Connection) -> None:
    """Создаёт таблицу reviews_analysis, если она ещё не существует."""
    conn.execute(CREATE_TABLE_SQL)


def save_results(
    conn: sqlite3.Connection,
    reviews: pd.DataFrame,
    analyses: list[tuple[str, str, str, str]],
) -> None:
    """Сохраняет результаты анализа в SQLite."""
    logger.info("Сохраняем в SQLite ./data/reviews.db...")

    for (_, row), (sentiment, topics, intent, summary) in zip(reviews.iterrows(), analyses):
        conn.execute(
            INSERT_SQL,
            (row["text"], sentiment, topics, intent, summary),
        )


def main() -> None:
    """Точка входа: загрузка CSV, LLM-анализ и сохранение в SQLite."""
    conn: sqlite3.Connection | None = None

    try:
        df = pd.read_csv(CSV_PATH)
        logger.info(f"Загружено {len(df)} строк, колонки: {list(df.columns)}")

        text_column = next(
            (
                col
                for col in df.columns
                if col.lower() in ["text", "review_text", "review", "content", "review_body"]
            ),
            None,
        )
        if text_column is None:
            raise ValueError(
                f"Не найдена колонка с текстом отзыва. Доступные колонки: {list(df.columns)}"
            )

        time_column = next((col for col in df.columns if col.lower() == "time"), None)
        if time_column:
            df["date"] = pd.to_datetime(df[time_column], unit="s")
        else:
            date_column = next(
                (
                    col
                    for col in df.columns
                    if col.lower()
                    in ["date", "review_date", "created_at", "timestamp", "date_added"]
                ),
                None,
            )
            if date_column:
                df = df.rename(columns={date_column: "date"})

        df = df.head(50)
        df = df.rename(columns={text_column: "text"})

        reviews = df
        llm = create_llm_client()

        total = len(reviews)
        analyses: list[tuple[str, str, str, str]] = []

        for index, (_, row) in enumerate(reviews.iterrows(), start=1):
            logger.info("Анализируем отзыв %s/%s...", index, total)
            result = analyze_review(llm, str(row["text"]))
            analyses.append(normalize_analysis(result))

            if index < total:
                time.sleep(API_DELAY_SECONDS)

        conn = sqlite3.connect(DB_PATH)
        ensure_table(conn)
        save_results(conn, reviews, analyses)
        conn.commit()
        conn.close()
        conn = None

        logger.info("✅ Готово. Проанализировано: %s", total)

    except FileNotFoundError:
        logger.error("Файл %s не найден", CSV_PATH)
        raise
    except sqlite3.Error as exc:
        logger.error("Ошибка SQLite: %s", exc)
        raise
    except Exception as exc:
        logger.error("Непредвиденная ошибка: %s", exc)
        raise
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    main()
