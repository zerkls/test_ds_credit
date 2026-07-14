"""
Извлечение ключевых полей из текста документа: сумма, дата, ИНН,
контрагент, предмет оплаты.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

RU_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

CURRENCY_TOKEN = r"(?:руб(?:лей|\.)?|₽|RUB|р\.)"

NUMBER_CORE = r"\d[\d\s.,]*\d|\d"

"""
Порядок важен: сначала ищем суммы с явным маркером "итог"/"к оплате"/
"сумма" (это почти всегда полная сумма документа, а не цена за
единицу товара), и только если такого маркера нет - берём первое число рядом с валютой.
"""
AMOUNT_PATTERNS = [
    # маркер суммы перед числом: "Итого к оплате: 1250000.00 ₽", "Сумма: ..."
    re.compile(
        rf"(?:итого\s*(?:к\s*оплате|стоимость\s+работ|с\s+ндс)?|"
        rf"общая\s+стоимость[^.\n]*составляет|"
        rf"всего\s+на\s+сумму|"
        rf"итого\s*к\s*оплате|итого|к\s*оплате|сумма)\s*[:\-]?\s*"
        rf"(?P<num>{NUMBER_CORE})\s*{CURRENCY_TOKEN}?",
        re.IGNORECASE,
    ),
    # сумма перед валютой:  "1 250 000,00 руб." / "1250000.00 ₽" / "1,250,000.00 RUB"
    re.compile(rf"(?P<num>{NUMBER_CORE})\s*{CURRENCY_TOKEN}", re.IGNORECASE),
]

TEXT_AMOUNT_PATTERN = re.compile(
    r"(?:стоимость|сумма)[^\n.]*составляет\s+"
    r"((?:[а-яёa-z\-]+\s+)+)"
    r"(?:руб|₽)",
    re.IGNORECASE,
)

RU_NUMBER_WORDS = {
    "ноль": 0, "один": 1, "одна": 1, "два": 2, "две": 2, "три": 3, "четыре": 4,
    "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9, "десять": 10,
    "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13, "четырнадцать": 14,
    "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17, "восемнадцать": 18,
    "девятнадцать": 19, "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50,
    "шестьдесят": 60, "семьдесят": 70, "восемьдесят": 80, "девяносто": 90,
    "сто": 100, "двести": 200, "триста": 300, "четыреста": 400, "пятьсот": 500,
    "шестьсот": 600, "семьсот": 700, "восемьсот": 800, "девятьсот": 900,
}

RU_NUMBER_SCALES = {
    "тысяч": 1_000, "тысяча": 1_000, "тысячи": 1_000,
    "миллион": 1_000_000, "миллиона": 1_000_000, "миллионов": 1_000_000,
}

DATE_PATTERNS = [
    # 01.03.2025  или  01-03-2025
    re.compile(r"\b(?P<d>\d{1,2})[.\-](?P<m>\d{1,2})[.\-](?P<y>\d{4})\b"),
    # 03/01/25   или   03/01/2025   (слэш трактуем как ДД/ММ/ГГ(ГГ), т.к. документы русскоязычные)
    re.compile(r"\b(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>\d{2,4})\b"),
    # 1 марта 2025 г.
    re.compile(
        r"\b(?P<d>\d{1,2})\s+(?P<mon>"
        + "|".join(RU_MONTHS.keys())
        + r")\s+(?P<y>\d{4})",
        re.IGNORECASE,
    ),
]

INN_PATTERN = re.compile(
    r"ИНН(?:\s*/\s*КПП)?\s*[:№]?\s*(\d{10}|\d{12})",
    re.IGNORECASE,
)

CONTRACTOR_PATTERNS = [
    re.compile(r"(?:контрагент|поставщик|исполнитель|подрядчик)\s*[:\-]\s*([^\n,;]+)", re.IGNORECASE),
    re.compile(r"((?:ООО|АО|ПАО|ЗАО|ИП)\s*[«\"][^»\"]+[»\"])"),
]

SUBJECT_PATTERNS = [
    # захватываем до конца строки/точки с запятой, либо до точки, за
    # которой следует пробел (конец предложения) - точка внутри номера
    # версии/артикула типа "МТЗ-82.1" пробелом не сопровождается и не
    # обрывает захват
    re.compile(
        r"(?:предмет оплаты|предмет закупки|предмет договора|назначение платежа|предмет)"
        r"\s*[:\-]\s*(?P<subj>.+?)(?:\.\s|\n|;|$)",
        re.IGNORECASE,
    ),
]


# Вспомогательные парсеры

def _parse_number(raw: str) -> Optional[float]:
    """Разбирает число из текста с учётом смешанных разделителей.
    Правило:
    - если есть и ',' и '.', десятичным считается тот, что встречается
      последним (правее); второй - разделитель тысяч и удаляется;
    - если есть только ',', и после последней запятой ровно 2 цифры -
      это десятичный разделитель (русский формат), иначе - разделитель
      тысяч;
    - аналогично для '.';
    - пробелы всегда трактуются как разделитель тысяч и удаляются.
    """
    s = raw.strip()
    s = re.sub(r"\s+", "", s)
    if not s:
        return None

    has_comma = "," in s
    has_dot = "." in s

    try:
        if has_comma and has_dot:
            last_comma = s.rfind(",")
            last_dot = s.rfind(".")
            if last_comma > last_dot:
                decimal_sep, thousand_sep = ",", "."
            else:
                decimal_sep, thousand_sep = ".", ","
            s = s.replace(thousand_sep, "")
            s = s.replace(decimal_sep, ".")
        elif has_comma:
            parts = s.split(",")
            if len(parts[-1]) == 2:
                s = "".join(parts[:-1]) + "." + parts[-1]
            else:
                s = s.replace(",", "")
        elif has_dot:
            parts = s.split(".")
            if len(parts[-1]) == 2:
                s = "".join(parts[:-1]) + "." + parts[-1]
            else:
                s = s.replace(".", "")
        return float(s)
    except ValueError:
        return None


def _parse_date(text: str) -> Optional[str]:
    if re.search(r"акт|упд|универсальный передаточный", text, re.IGNORECASE):
        match = re.search(
            r"№\s*\d+\s+от\s+(?P<d>\d{1,2})\s+(?P<mon>" + "|".join(RU_MONTHS.keys()) + r")\s+(?P<y>\d{4})",
            text, re.IGNORECASE
        )
        if match:
            try:
                day = int(match.group("d"))
                month = RU_MONTHS[match.group("mon").lower()]
                year = int(match.group("y"))
                return date(year, month, day).isoformat()
            except (ValueError, KeyError):
                pass
        match = re.search(
            r"№\s*\d+\s+от\s+(?P<d>\d{1,2})[.\-](?P<m>\d{1,2})[.\-](?P<y>\d{4})",
            text, re.IGNORECASE
        )
        if match:
            try:
                day = int(match.group("d"))
                month = int(match.group("m"))
                year = int(match.group("y"))
                return date(year, month, day).isoformat()
            except ValueError:
                pass

    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        groups = match.groupdict()
        try:
            day = int(groups["d"])
            if "mon" in groups and groups.get("mon"):
                month = RU_MONTHS[groups["mon"].lower()]
            else:
                month = int(groups["m"])
            year = int(groups["y"])
            if year < 100: 
                year += 2000
            return date(year, month, day).isoformat()
        except (ValueError, KeyError):
            continue
    return None


def _normalize_ocr_text(text: str) -> str:
    """Лёгкая нормализация типичных OCR-замен перед извлечением полей."""
    normalized = text

    normalized = normalized.replace('"', '«').replace('"', '«')

    for src, dst in (
        ("ИHH", "ИНН"),
        ("ИНH", "ИНН"),
        ("N9", "№"),
        ("pyб", "руб"),
        ("py6", "руб"),
        ("Cyммa", "Сумма"),
        ("Сyммa", "Сумма"),
    ):
        normalized = normalized.replace(src, dst)
    normalized = re.sub(
        r"(?<=\d)[lI](?=\d)|(?<=\d)[lI](?=\s)|(?<=\s)[lI](?=\d)",
        "1",
        normalized,
    )
    normalized = re.sub(
        r"(?<=\d)O(?=\d)|(?<=\d)O(?=\s)|(?<=\s)O(?=\d)",
        "0",
        normalized,
    )
    normalized = re.sub(
        r"(?<=[\d\s])O+(?=[\s\d]|руб)",
        lambda match: "0" * len(match.group(0)),
        normalized,
    )
    normalized = re.sub(r"(?:^|[\s:])l\s+(\d)", r" 1 \1", normalized)

    return normalized


def _parse_textual_amount(text: str) -> Optional[float]:
    match = TEXT_AMOUNT_PATTERN.search(text)
    if not match:
        return None

    words = re.findall(r"[а-яёa-z\-]+", match.group(1).lower())
    if not words:
        return None

    total = 0
    current = 0
    for word in words:
        if word in RU_NUMBER_SCALES:
            chunk = current or 1
            total += chunk * RU_NUMBER_SCALES[word]
            current = 0
        elif word in RU_NUMBER_WORDS:
            current += RU_NUMBER_WORDS[word]
        else:
            return None

    return float(total + current) if total or current else None


def _parse_amount(text: str) -> Optional[float]:
    for pattern in AMOUNT_PATTERNS[:-1]:
        match = pattern.search(text)
        if match:
            value = _parse_number(match.group("num"))
            if value is not None:
                return value

    textual = _parse_textual_amount(text)
    if textual is not None:
        return textual

    generic_pattern = AMOUNT_PATTERNS[-1]
    candidates: list[float] = []
    for match in generic_pattern.finditer(text):
        start = max(0, match.start() - 50)
        context = text[start:match.start()].lower()
        if "ндс" in context and "итого" not in context:
            continue
        value = _parse_number(match.group("num"))
        if value is not None:
            candidates.append(value)

    return max(candidates) if candidates else None


def _parse_inn(text: str) -> Optional[str]:
    matches = re.findall(r"ИНН(?:\s*/\s*КПП)?\s*[:№]?\s*([\d\s\-\./]+)", text, re.IGNORECASE)
    if not matches:
        return None
    for group in matches:
        # Разбиваем по пробелам, слешам, дефисам, точкам
        parts = re.split(r"[\s\-\./]+", group.strip())
        for part in parts:
            part = part.strip()
            if len(part) in (10, 12, 14):
                return part  # первый подходящий ИНН
    return None

def _parse_contractor(text: str) -> Optional[str]:
    for pattern in CONTRACTOR_PATTERNS[::-1]:
        match = pattern.search(text)
        if match:
            contractor = match.group(1).strip()
            return _normalize_ocr_text(contractor)
    return None


def _parse_subject(text: str) -> Optional[str]:
    for pattern in SUBJECT_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group("subj").strip()
    return None


# Публичный интерфейс

def extract(text: str) -> dict:
    """Извлекает ключевые поля документа.

    Args:
        text: сырой текст документа (результат OCR или из pdf).

    Returns:
        dict с полями amount (float|None), date (str ISO|None),
        inn (str|None), contractor (str|None), subject (str|None).
    """
    if not text or not text.strip():
        return {"amount": None, "date": None, "inn": None, "contractor": None, "subject": None}

    normalized_text = _normalize_ocr_text(text)

    result = {
        "amount": _parse_amount(normalized_text),
        "date": _parse_date(normalized_text),
        "inn": _parse_inn(normalized_text),
        "contractor": _parse_contractor(normalized_text),
        "subject": _parse_subject(normalized_text),
    }

    if result["contractor"] is None:
        result["inn"] = None

    return result


