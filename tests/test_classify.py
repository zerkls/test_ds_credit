from src.classify import classify


def test_invoice():
    doc_type, confidence = classify(
        "Счёт на оплату №12 от 01.03.2025. Банковские реквизиты указаны ниже. Оплатить до 10.03.2025."
    )
    assert doc_type == "invoice"
    assert confidence > 0.5


def test_contract():
    doc_type, confidence = classify(
        "Настоящий договор № 7 заключен между Заказчиком и Исполнителем, "
        "именуемые в дальнейшем Стороны, о нижеследующем: предмет договора..."
    )
    assert doc_type == "contract"
    assert confidence > 0.5


def test_spec():
    doc_type, confidence = classify(
        "Спецификация № 3 к договору поставки. Номенклатура, количество и цена за единицу указаны в таблице."
    )
    assert doc_type == "spec"
    assert confidence > 0.5


def test_act():
    doc_type, confidence = classify(
        "Акт приема-передачи выполненных работ № 5. Работы выполнены полностью, заказчик претензий не имеет."
    )
    assert doc_type == "act"
    assert confidence > 0.5


def test_unknown_for_ambiguous_text():
    doc_type, _ = classify("Прочий текст без явных признаков какого-либо документа сельхоз-профиля.")
    assert doc_type == "unknown"


def test_empty_text():
    doc_type, confidence = classify("")
    assert doc_type == "unknown"
    assert confidence == 0.0
