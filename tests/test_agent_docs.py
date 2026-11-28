import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GUIDES = [ROOT / "AGENTS.md", *sorted((ROOT / "docs" / "agents").rglob("*.md"))]
PATH_PREFIXES = ("src/", "tests/", "docs/", ".claude/", ".github/")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
CODE_SPAN = re.compile(r"`([^`\s]+)`")


def _references(guide: Path) -> list[tuple[str, Path]]:
    text = guide.read_text(encoding="utf-8")
    references: list[tuple[str, Path]] = []

    for target in LINK.findall(text):
        if re.match(r"[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
            continue
        references.append((target, (guide.parent / target.split("#")[0]).resolve()))

    references.extend(
        (span, ROOT / span.split("#")[0].rstrip(".,:;"))
        for span in CODE_SPAN.findall(text)
        if span.startswith(PATH_PREFIXES) and not any(c in span for c in "*<>{}$")
    )

    return references


@pytest.mark.parametrize("guide", GUIDES, ids=lambda path: str(path.relative_to(ROOT)))
def test_guide_references_exist(guide: Path) -> None:
    missing = [target for target, path in _references(guide) if not path.exists()]

    assert not missing
