"""Package each folder under skills/ into dist/<skill>-skill.zip for Agensi upload.

Each zip holds a single top-level folder with SKILL.md at its root, as Agensi requires.
"""

import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = PROJECT_ROOT / "skills"
DIST = PROJECT_ROOT / "dist"


def build(skill_dir: Path) -> Path:
    out = DIST / f"{skill_dir.name}-skill.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(skill_dir.rglob("*")):
            if path.is_file():
                zf.write(path, Path(skill_dir.name) / path.relative_to(skill_dir))
    return out


def main() -> None:
    DIST.mkdir(exist_ok=True)
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if (skill_dir / "SKILL.md").is_file():
            print(build(skill_dir))


if __name__ == "__main__":
    main()
