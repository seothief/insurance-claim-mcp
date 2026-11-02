"""Package skills/insurance-claim-mcp into dist/insurance-claim-mcp-skill.zip for Agensi upload.

The zip holds a single top-level folder with SKILL.md at its root, as Agensi requires.
"""

import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = PROJECT_ROOT / "skills" / "insurance-claim-mcp"
OUT = PROJECT_ROOT / "dist" / "insurance-claim-mcp-skill.zip"


def main() -> None:
    OUT.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(SKILL_DIR.rglob("*")):
            if path.is_file():
                zf.write(path, Path(SKILL_DIR.name) / path.relative_to(SKILL_DIR))
    print(OUT)


if __name__ == "__main__":
    main()
