from src.extract import extract


def test_amount_ru_comma_space_thousands():
    assert extract("Сумма: 1 250 000,00 руб.")["amount"] == 1_250_000.0


def test_amount_dot_decimal_symbol():
    assert extract("Итого к оплате: 1250000.00 ₽")["amount"] == 1_250_000.0


def test_amount_comma_thousands_dot_decimal():
    assert extract("Total: 1,250,000.00 RUB")["amount"] == 1_250_000.0


def test_amount_missing():
    assert extract("без цифр")["amount"] is None


def test_inn():
    assert extract("ИНН 7701234567")["inn"] == "7701234567"


def test_inn_missing():
    assert extract("реквизиты не указаны")["inn"] is None


def test_date_dot_format():
    assert extract("Дата: 01.03.2025")["date"] == "2025-03-01"


def test_date_ru_month_name():
    assert extract("составлен 1 марта 2025 г.")["date"] == "2025-03-01"


def test_date_slash_format():
    assert extract("от 03/01/25")["date"] == "2025-01-03"


def test_contractor_ooo():
    result = extract('Поставщик: ООО «Агрохолдинг Юг»')
    assert result["contractor"] is not None
    assert "Агрохолдинг" in result["contractor"]


def test_subject_field():
    result = extract("Предмет оплаты: минеральные удобрения")
    assert result["subject"] == "минеральные удобрения"


def test_empty_text_returns_all_none():
    result = extract("")
    assert all(v is None for v in result.values())


def test_full_document_all_fields():
    text = (
        'Договор поставки № 45. Поставщик: ООО «АгроСнаб», ИНН 7701234567. '
        'Дата: 15.04.2025. Предмет оплаты: семена подсолнечника. '
        'Сумма: 850 000,50 руб.'
    )
    result = extract(text)
    assert result["amount"] == 850_000.50
    assert result["date"] == "2025-04-15"
    assert result["inn"] == "7701234567"
    assert result["contractor"] is not None
    assert result["subject"] == "семена подсолнечника"
