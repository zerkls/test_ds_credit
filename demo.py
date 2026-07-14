"""
CLI-демонстрация пайплайна: прогоняет extract() и classify() на всех
файлах dataset/, а check_subject() - на dataset/subjects_test.txt.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.classify import classify 
from src.extract import extract  
from src.subject_check import check_subject  

DATASET_DIR = Path(__file__).parent / "dataset"


def run_extract_and_classify() -> None:
    print("=" * 100)
    print("Извлечение полей и классификация по документам из dataset/")
    print("=" * 100)

    txt_files = sorted(
        p for p in DATASET_DIR.glob("*.txt") if p.name != "subjects_test.txt"
    )
    header = f"{'файл':<32}{'тип':<10}{'увер.':<8}{'сумма':<14}{'дата':<12}{'ИНН':<14}{'предмет':<30}"
    print(header)
    print("-" * len(header))

    for path in txt_files:
        text = path.read_text(encoding="utf-8")
        doc_type, confidence = classify(text)
        fields = extract(text)
        amount = f"{fields['amount']:.2f}" if fields["amount"] is not None else "—"
        row = (
            f"{path.name:<32}{doc_type:<10}{confidence:<8}{amount:<14}"
            f"{str(fields['date']):<12}{str(fields['inn']):<14}{str(fields['subject'])[:28]:<30}"
        )
        print(row)


def run_subject_check() -> None:
    print()
    print("=" * 100)
    print("Проверка предмета оплаты по dataset/subjects_test.txt")
    print("=" * 100)

    lines = (DATASET_DIR / "subjects_test.txt").read_text(encoding="utf-8").splitlines()
    header = f"{'предмет оплаты':<55}{'ожидание':<10}{'matches':<10}{'conf.':<8}{'причина'}"
    print(header)
    print("-" * len(header))

    correct = 0
    scored = 0  
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        expected, subject = [part.strip() for part in line.split("|", 1)]
        matches, confidence, reason = check_subject(subject, use_llm=True)
        if expected != "EDGE":
            scored += 1
            expected_bool = expected == "PASS"
            if matches == expected_bool:
                correct += 1
        print(f"{subject[:53]:<55}{expected:<10}{str(matches):<10}{confidence:<8}{reason}")

    print(f"\nСовпадений с ожиданием (без учёта EDGE): {correct} из {scored}")


if __name__ == "__main__":
    run_extract_and_classify()
    run_subject_check()
