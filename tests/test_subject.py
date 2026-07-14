from src.subject_check import check_subject


def test_fertilizer_matches():
    matches, confidence, reason = check_subject("удобрения азотные")
    assert matches is True
    assert confidence > 0.5
    assert "агрохим" in reason.lower()


def test_office_rent_does_not_match():
    matches, confidence, reason = check_subject("аренда офиса")
    assert matches is False
    assert confidence > 0.5


def test_tractor_matches():
    matches, confidence, reason = check_subject("трактор МТЗ-82 с навесным оборудованием")
    assert matches is True


def test_seeds_matches():
    matches, _, _ = check_subject("семена кукурузы гибридные")
    assert matches is True


def test_empty_subject():
    matches, confidence, reason = check_subject("")
    assert matches is False
    assert confidence == 0.0


def test_return_types():
    result = check_subject("дизельное топливо для посевной")
    assert isinstance(result, tuple)
    assert len(result) == 3
    matches, confidence, reason = result
    assert isinstance(matches, bool)
    assert isinstance(confidence, float)
    assert isinstance(reason, str)
