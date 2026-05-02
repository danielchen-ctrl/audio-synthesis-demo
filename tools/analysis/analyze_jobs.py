import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_FILE = PROJECT_ROOT / "output" / "training" / "unified" / "_index.jsonl"


def main() -> None:
    if not INDEX_FILE.exists():
        print(f"索引文件不存在: {INDEX_FILE}")
        return

    rows = [json.loads(line) for line in INDEX_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    total = len(rows)
    passed = sum(1 for row in rows if row.get("passed"))
    failed = total - passed
    avg_score = round(sum(float(row.get("score", 0.0)) for row in rows) / max(total, 1), 2)

    print(f"统一索引记录数: {total}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"平均分: {avg_score}")


if __name__ == "__main__":
    main()
