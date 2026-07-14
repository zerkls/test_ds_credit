"""
Классификация типа документа по содержимому (без ML-модели -
взвешенное совпадение по ключевым словам/фразам с явным порогом
уверенности отказа в ответ "unknown").
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

DOC_TYPES = ("contract", "spec", "invoice", "act")

# Порог разрыва между top-1 и top-2 скором. Ниже него ответ ненадёжен.
# Подбирался эмпирически на dataset/
CONFIDENCE_GAP_THRESHOLD = 0.15

# (фраза, вес) - более специфичные фразы получают больший вес,
# чтобы не путать, например, "акт" внутри "фактически"
KEYWORDS: Dict[str, List[Tuple[str, float]]] = {
    "contract": [
        (r"настоящий договор", 3.0),
        (r"договор\s*№", 2.5),
        (r"именуем(ый|ое|ая)\s+в\s+дальнейшем", 2.5),
        (r"заказчик и исполнитель", 2.0),
        (r"предмет договора", 2.0),
        (r"стороны договорились", 1.5),
        (r"\bдоговор\b", 1.0),
    ],
    "spec": [
        (r"спецификация\s*№", 3.0),
        (r"приложение\s*№?\s*\d*\s*к договору", 2.5),
        (r"номенклатура", 2.0),
        (r"цена за единицу", 2.0),
        (r"\bспецификация\b", 1.5),
        (r"количество", 0.5),
    ],
    "invoice": [
        (r"счет на оплату", 3.0),
        (r"счёт на оплату", 3.0),
        (r"счет\s*№", 2.5),
        (r"счёт\s*№", 2.5),
        (r"оплатить до", 2.0),
        (r"банковские реквизиты", 1.5),
        (r"к оплате", 1.0),
        (r"\bсчет\b|\bсчёт\b", 1.0),
        (r"сумма\s*:", 1.0),
    ],
    "act": [
        (r"универсальный передаточный документ|\bупд\b", 3.0),
        (r"акт приема-передачи", 3.0),
        (r"акт сдачи-приемки", 3.0),
        (r"акт выполненных работ", 3.0),
        (r"товар передан", 2.0),
        (r"работы выполнены полностью", 2.0),
        (r"претензий не имеет", 1.5),
        (r"\bакт\s*№", 2.0),
        (r"\bакт\b", 1.0),
    ],
}


def _score(text: str) -> Dict[str, float]:
    scores = {doc_type: 0.0 for doc_type in DOC_TYPES}
    for doc_type, patterns in KEYWORDS.items():
        for phrase, weight in patterns:
            hits = len(re.findall(phrase, text, re.IGNORECASE))
            scores[doc_type] += hits * weight
    return scores


def classify(text: str) -> Tuple[str, float]:
    """Классифицирует тип документа.

    Args:
        text: текст документа.

    Returns:
        (doc_type, confidence). doc_type - один из
        contract/spec/invoice/act/unknown. confidence - доля скора
        топ-1 категории от суммы всех скоров (0..1).
        Если разрыв между топ-1 и топ-2 меньше CONFIDENCE_GAP_THRESHOLD,
        возвращается ("unknown", confidence_top1) - намеренно не
        придумываем уверенный ответ там, где сигнала недостаточно.
    """
    if not text or not text.strip():
        return "unknown", 0.0

    raw_scores = _score(text)
    total = sum(raw_scores.values())

    if total == 0:
        return "unknown", 0.0

    normalized = {k: v / total for k, v in raw_scores.items()}
    ranked = sorted(normalized.items(), key=lambda kv: kv[1], reverse=True)

    top_type, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    gap = top_score - second_score

    if gap < CONFIDENCE_GAP_THRESHOLD:
        return "unknown", round(top_score, 4)

    return top_type, round(top_score, 4)
