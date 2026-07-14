"""
Проверка, подходит ли предмет оплаты под льготную сельхоз-программу.

Реализованы оба варианта из ТЗ:
- keyword/fuzzy-matching без внешних API (используется по умолчанию,
  всегда доступен локально);
- опциональный LLM-режим через LangChain (используется, только если
  установлен пакет и задан ключ API; иначе - автоматический fallback
  на keyword-подход, чтобы код запускался без ключей).
"""
from __future__ import annotations

import difflib
import os
import re
from typing import Dict, List, Tuple

# Категории, разрешённые в рамках льготной программы "сельхоз-нужды",
# и ключевые слова/фразы, характерные для каждой.
ALLOWED_CATEGORIES: Dict[str, List[str]] = {
    "агрохимия": [
        "удобрение", "удобрения", "пестицид", "гербицид", "фунгицид",
        "инсектицид", "средства защиты растений", "агрохимия", "агрохимическ",
        "селитра", "кас-32",
    ],
    "семена и посадочный материал": [
        "семена", "семян", "посадочный материал", "рассада", "саженцы", "гибрид",
    ],
    "сельхозтехника и запчасти": [
        "трактор", "комбайн", "сеялка", "культиватор", "плуг", "борона",
        "сельхозтехника", "запчасти для трактора", "запасные части",
        "навесное оборудование",
    ],
    "топливо и ГСМ": [
        "дизельное топливо", "дизтопливо", "дизельн", "топлив", "гсм", "бензин",
        "смазочные материалы",
    ],
    "полевые работы": [
        "вспашка", "посев", "уборка урожая", "боронование", "опрыскивание",
        "полевые работы", "обработка полей", "агрохимическ", "урожа", "страхован",
    ],
    "животноводство и корма": [
        "корма", "комбикорм", "ветеринарные препараты", "животноводство",
        "содержание скота",
    ],
    "мелиорация и ирригация": [
        "орошение", "мелиорация", "полив", "ирригац",
    ],
}

# Явно не относящиеся к сельхоз-деятельности категории - используются,
# чтобы сформулировать понятное объяснение отказа, а не просто "не найдено".
DISALLOWED_HINTS: Dict[str, List[str]] = {
    "аренда офиса/помещений": [
        "аренда офиса", "аренда офисного", "аренда помещения", "аренда склада под офис",
    ],
    "маркетинг/реклама": ["реклама", "маркетинг", "smm", "продвижение сайта", "продвижен", "seo"],
    "оргтехника/IT не для производства": [
        "ноутбук", "оргтехника", "принтер", "программное обеспечение офисное",
        "офисной мебели",
    ],
    "консалтинг/юридические услуги": [
        "консалтинг", "юридические услуги", "юридическ", "аудит",
    ],
    "клининг и офисное обслуживание": ["клининг", "уборка административного", "канцелярских"],
    "транспорт не сельхоз-назначения": [
        "легковой автомобиль", "аренда автомобиля представительского класса",
    ],
}

MATCH_THRESHOLD = 0.55
TOKEN_FUZZY_THRESHOLD = 0.84
MIN_TOKEN_LEN_FOR_FUZZY = 5
MAX_TOKEN_LEN_DIFF_FOR_FUZZY = 2


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _token_similarity(token_a: str, token_b: str) -> float:
    """Fuzzy-схожесть двух отдельных слов с защитой от ложных срабатываний
    на коротких словах и словах сильно разной длины (TOKEN_FUZZY_THRESHOLD)."""
    if min(len(token_a), len(token_b)) < MIN_TOKEN_LEN_FOR_FUZZY:
        return 0.0
    if abs(len(token_a) - len(token_b)) > MAX_TOKEN_LEN_DIFF_FOR_FUZZY:
        return 0.0
    return difflib.SequenceMatcher(None, token_a, token_b).ratio()


def _keyword_fuzzy_score(subject: str, keywords: List[str]) -> float:
    """Максимальный скор совпадения предмета с одним из ключевых слов
    категории: точное вхождение подстроки/словосочетания даёт 1.0,
    иначе - оценка похожести отдельных токенов (защита от опечаток),
    учитывается только при высокой схожести (TOKEN_FUZZY_THRESHOLD)."""
    subject_tokens = subject.split()
    best = 0.0
    for kw in keywords:
        kw_tokens = kw.split()
        if len(kw_tokens) > 1:
            if kw in subject:
                return 1.0
        else:
            kw_token = kw_tokens[0]
            for subj_token in subject_tokens:
                if subj_token == kw_token:
                    return 1.0
                sim = _token_similarity(subj_token, kw_token)
                if sim >= TOKEN_FUZZY_THRESHOLD:
                    best = max(best, sim)
            continue

        matched = 0
        for kw_token in kw_tokens:
            if kw_token in subject:
                matched += 1
                continue
            if any(
                subj_token == kw_token
                or _token_similarity(subj_token, kw_token) >= TOKEN_FUZZY_THRESHOLD
                for subj_token in subject_tokens
            ):
                matched += 1
        if matched == len(kw_tokens):
            best = max(best, 0.95)
    return best


def _check_keyword(subject: str) -> Tuple[bool, float, str]:
    norm = _normalize(subject)

    best_category, best_score = None, 0.0
    for category, keywords in ALLOWED_CATEGORIES.items():
        score = _keyword_fuzzy_score(norm, keywords)
        if score > best_score:
            best_category, best_score = category, score

    if best_score >= MATCH_THRESHOLD:
        return (
            True,
            round(best_score, 2),
            f"предмет '{subject.strip()}' относится к категории «{best_category}», "
            f"разрешённой в рамках льготной сельхоз-программы",
        )

    for category, keywords in DISALLOWED_HINTS.items():
        score = _keyword_fuzzy_score(norm, keywords)
        if score >= MATCH_THRESHOLD:
            return (
                False,
                round(score, 2),
                f"предмет '{subject.strip()}' относится к категории «{category}» "
                f"и не связан с сельхоз-деятельностью",
            )

    return (
        False,
        round(1 - best_score, 2) if best_score > 0 else 0.5,
        f"предмет '{subject.strip()}' не удалось однозначно сопоставить ни с одной "
        f"из разрешённых категорий сельхоз-программы",
    )


def _check_llm(subject: str) -> Tuple[bool, float, str]:
    """LLM-режим через LangChain. Используется только если библиотека
    установлена и задан OPENAI_API_KEY; в остальных случаях выбрасывает
    исключение, которое ловится в check_subject() и приводит к fallback."""
    from langchain_openai import ChatOpenAI  
    import json

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    few_shot = (
        "Ты - эксперт по льготным сельскохозяйственным кредитам. "
        "Определи, относится ли предмет оплаты к сельхоз-деятельности "
        "(агрохимия, семена, сельхозтехника, топливо для полевых работ, "
        "полевые работы, животноводство, мелиорация).\n"
        "Ответь СТРОГО в формате JSON: "
        '{"matches": bool, "confidence": float, "reason": str}.\n\n'
        'Пример 1. Предмет: "удобрения азотные". '
        'Ответ: {"matches": true, "confidence": 0.95, '
        '"reason": "удобрения относятся к агрохимии"}\n'
        'Пример 2. Предмет: "аренда офиса". '
        'Ответ: {"matches": false, "confidence": 0.93, '
        '"reason": "аренда офиса не относится к сельхоз-деятельности"}\n\n'
        f'Предмет: "{subject}"\nОтвет:'
    )
    response = llm.invoke(few_shot)
    data = json.loads(response.content)
    return bool(data["matches"]), float(data["confidence"]), str(data["reason"])


def check_subject(subject: str, use_llm: bool = False) -> Tuple[bool, float, str]:
    """Проверяет соответствие предмета оплаты льготной сельхоз-программе.

    Args:
        subject: текст предмета оплаты/назначения платежа.
        use_llm: если True - пробует LLM-режим (LangChain), при
            отсутствии ключа/пакета автоматически откатывается на
            keyword-режим.

    Returns:
        (matches, confidence, reason).
    """
    if not subject or not subject.strip():
        return False, 0.0, "предмет оплаты не указан"

    if use_llm and os.environ.get("OPENAI_API_KEY"):
        try:
            return _check_llm(subject)
        except Exception:  
            return _check_keyword(subject)

    return _check_keyword(subject)
