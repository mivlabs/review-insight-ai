"""Чистая (без I/O) логика, общая для ingest.py и dashboard.py.

Раньше нормализация topics и парсинг ответа LLM были продублированы —
похожий, но не идентичный код жил внутри analyze_review() в ingest.py и
внутри замыкания parse_topics() в dashboard.py. Ни то, ни другое не было
покрыто тестами, потому что обе функции были спрятаны внутри скриптов,
которые дергают сеть/Streamlit/файловую систему на уровне модуля.

Здесь — то же самое, но как чистые функции без побочных эффектов,
которые можно импортировать и тестировать напрямую.
"""
import json
from typing import Iterable, List, Optional, Sequence


def strip_markdown_code_fence(content: str) -> str:
    """LLM иногда оборачивает JSON в ```json ... ``` или просто ``` ... ```.
    Убирает обёртку, если она есть; если её нет — возвращает текст как есть."""
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
    if content.endswith("```"):
        content = content[:-3]
    return content.strip()


def normalize_topics(raw_topics) -> List[str]:
    """Приводит topics из ответа LLM к списку строк длиннее 1 символа.
    Если после фильтрации список пуст — возвращает ["unknown"], а не [],
    т.к. эта версия используется в ingest.py при первичном сохранении
    в БД (пустой topics там не имеет смысла)."""
    topics = raw_topics
    if isinstance(topics, str):
        topics = [topics]
    if not isinstance(topics, list):
        topics = []
    topics = [t for t in topics if isinstance(t, str) and len(t) > 1]
    if not topics:
        topics = ["unknown"]
    return topics


def parse_topics_column(raw: Optional[str]) -> List[str]:
    """Парсит значение колонки `topics` (JSON-строка) при чтении из БД
    в dashboard.py. В отличие от normalize_topics() выше, тут пустой/битый
    результат — это просто [] (нечего показывать на графике), без
    дефолтного "unknown": в БД уже лежит то, что туда положил ingest.py."""
    if not raw or raw == "error" or raw == "[]":
        return []
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [t for t in parsed if isinstance(t, str) and len(t) > 1]


def detect_text_column(columns: Iterable[str], candidates: Sequence[str] = (
    "text", "Text", "review_text", "review", "content", "Review",
)) -> Optional[str]:
    """Ищет в заголовках CSV колонку с текстом отзыва — первую из
    `candidates`, которая реально есть в `columns`. None, если не нашли."""
    columns = list(columns)
    for col in candidates:
        if col in columns:
            return col
    return None
