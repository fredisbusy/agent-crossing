"""코드 구조 정책(AGENTS.md §10)을 검사한다.

- 소스 파일 줄 수 상한, 테스트 파일 줄 수 상한
- 한 폴더의 코드 파일 수 상한
- 기준선(structure_baseline.json)에 오른 기존 위반은 지금 크기보다 커지지 못한다(래칫)

사용: python scripts/check_structure.py [--update-baseline]
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "scripts" / "structure_baseline.json"
SCAN_ROOTS = ("packages",)
CODE_SUFFIXES = {".py", ".ts", ".tsx"}
SKIP_DIRS = {"node_modules", ".venv", "dist", "build", "__pycache__", ".vite"}
SKIP_FILES = {"__init__.py", "vite-env.d.ts"}

MAX_SOURCE_LINES = 400
MAX_TEST_LINES = 500
MAX_FILES_PER_DIR = 10


def is_test_file(path: Path) -> bool:
    return (
        "tests" in path.parts
        or path.name.startswith("test_")
        or ".test." in path.name
        or ".spec." in path.name
    )


def iter_code_files() -> list[Path]:
    files: list[Path] = []
    for scan_root in SCAN_ROOTS:
        for path in (ROOT / scan_root).rglob("*"):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.is_file() and path.suffix in CODE_SUFFIXES:
                files.append(path)
    return sorted(files)


def count_lines(path: Path) -> int:
    with path.open(encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def collect_violations() -> dict[str, int]:
    """위반 항목 → 현재 값. 키는 'file:<경로>' 또는 'dir:<경로>'."""
    violations: dict[str, int] = {}
    dir_counts: Counter[Path] = Counter()
    for path in iter_code_files():
        rel = path.relative_to(ROOT)
        if path.name not in SKIP_FILES:
            dir_counts[rel.parent] += 1
        limit = MAX_TEST_LINES if is_test_file(rel) else MAX_SOURCE_LINES
        lines = count_lines(path)
        if lines > limit:
            violations[f"file:{rel.as_posix()}"] = lines
    for directory, count in dir_counts.items():
        if count > MAX_FILES_PER_DIR:
            violations[f"dir:{directory.as_posix()}"] = count
    return violations


def load_baseline() -> dict[str, int]:
    if not BASELINE_PATH.exists():
        return {}
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="현재 위반을 기준선으로 기록한다(줄이는 방향으로만 쓴다)",
    )
    args = parser.parse_args()

    violations = collect_violations()
    if args.update_baseline:
        baseline = load_baseline()
        grown = [k for k, v in violations.items() if v > baseline.get(k, v)]
        new = [k for k in violations if k not in baseline]
        if BASELINE_PATH.exists() and (grown or new):
            print("기준선은 줄이는 방향으로만 갱신한다. 새로 생기거나 커진 위반:")
            for key in new + grown:
                print(f"  {key} = {violations[key]}")
            return 1
        BASELINE_PATH.write_text(
            json.dumps(violations, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        print(f"기준선 갱신: {len(violations)}건")
        return 0

    baseline = load_baseline()
    failures: list[str] = []
    for key, value in sorted(violations.items()):
        allowed = baseline.get(key)
        if allowed is None:
            failures.append(f"{key} = {value} (새 위반)")
        elif value > allowed:
            failures.append(f"{key} = {value} (기준선 {allowed}보다 커짐)")

    if failures:
        print(
            f"코드 구조 정책 위반 (소스 {MAX_SOURCE_LINES}줄, 테스트 {MAX_TEST_LINES}줄, "
            f"폴더당 {MAX_FILES_PER_DIR}파일). AGENTS.md §10 참고:"
        )
        for failure in failures:
            print(f"  {failure}")
        return 1

    stale = [k for k in baseline if k not in violations]
    print(f"코드 구조 정책 통과 (기준선 위반 {len(baseline)}건 남음)")
    if stale:
        print("해소된 기준선 항목이 있다. --update-baseline으로 지운다:")
        for key in stale:
            print(f"  {key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
