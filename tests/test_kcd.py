"""Tests for the KCD official code master: parsing, repository, and catalog validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from claim_service.db.engine import create_db_engine, init_schema
from claim_service.db.repository import PolicyRepository
from claim_service.domain import kcd
from claim_service.domain.catalog import STANDARD_RULES
from tests.dbutil import database_url_for


class TestKcdParsing:
    def test_normalize_code_to_dotless_line_format(self) -> None:
        assert kcd.normalize_code(" s72.0 ") == "S720"
        assert kcd.normalize_code("t30") == "T30"
        assert kcd.normalize_code("A00.01") == "A0001"
        assert kcd.normalize_code("a000") == "A000"

    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            ("A", ("A", 1)),  # 대분류(장)
            ("S72", ("S", 3)),  # 소분류(3단, 숫자2)
            ("S720", ("S", 4)),  # 세분류(4단, 숫자3)
            ("S72.0", ("S", 4)),  # 점 표기는 점 제거 후 동일
            ("S7200", ("S", 5)),  # 세세분류(5단, 숫자4)
            ("H26000", ("H", 5)),  # 한국 특수/한방 확장(숫자5)
            ("J10", ("J", 3)),
            ("T30", ("T", 3)),
        ],
    )
    def test_classify_code(self, code: str, expected: tuple[str, int]) -> None:
        assert kcd.classify_code(code) == expected

    def test_large_category_letter_is_valid(self) -> None:
        # A bare A..Z letter is a valid KCD 대분류(장) code, not an error.
        assert kcd.normalize_code("S") == "S"
        assert kcd.classify_code("S") == ("S", 1)

    @pytest.mark.parametrize("bad", ["", "72", "..", "A0", "S72.X", "S7200X"])
    def test_invalid_codes_raise(self, bad: str) -> None:
        with pytest.raises(ValueError):
            kcd.normalize_code(bad)

    def test_match_kcd_code_is_dot_agnostic(self) -> None:
        prefixes = ["S02", "S12", "S72"]
        # Dot-less (master line format) input
        assert kcd.match_kcd_code("S720", prefixes)
        # Dotted official notation input
        assert kcd.match_kcd_code("S72.0", prefixes)
        assert kcd.match_kcd_code("S02.5", prefixes)  # target 에는 매칭됨 (exclusion 없음)
        assert not kcd.match_kcd_code("J00", prefixes)
        assert not kcd.match_kcd_code("", prefixes)
        assert not kcd.match_kcd_code(None, prefixes)

    def test_match_kcd_code_exclusion_takes_priority(self) -> None:
        prefixes = ["S02", "S12", "S72"]
        excluded = ["S02.5"]  # 치아파절
        assert not kcd.match_kcd_code("S025", prefixes, excluded)
        assert not kcd.match_kcd_code("S02.5", prefixes, excluded)
        assert kcd.match_kcd_code("S020", prefixes, excluded)  # 두개골절은 계속 보장

    def test_missing_prefixes(self) -> None:
        codes = {"S72.0": {}, "S72.1": {}, "T30": {}}
        assert kcd.missing_prefixes(["S72", "T3"], codes) == []
        assert kcd.missing_prefixes(["S72", "Z99"], codes) == ["Z99"]


class TestKcdRepository:
    def _repo(self, tmp_path: Path) -> PolicyRepository:
        engine = create_db_engine(database_url_for(tmp_path, "kcd_test.db"))
        init_schema(engine)
        return PolicyRepository(engine)

    def test_upsert_and_query(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        rows = [
            {
                "code": "S720",
                "category": "S",
                "level": 4,
                "ko_name": "대퇴골의 골절",
                "en_name": "Fracture of femur",
                "source_version": "KCD-9",
                "verified": True,
                "source_reference": "table",
            },
            {
                "code": "T30",
                "category": "T",
                "level": 3,
                "ko_name": "화상",
                "en_name": "Burn",
                "source_version": "KCD-9",
                "verified": True,
                "source_reference": "table",
            },
        ]
        written = repo.upsert_kcd_codes(rows)
        assert written == 2
        assert repo.count_kcd_codes() == 2
        all_codes = repo.get_kcd_codes()
        assert set(all_codes) == {"S720", "T30"}
        assert all_codes["S720"]["ko_name"] == "대퇴골의 골절"

    def test_upsert_replaces_existing(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        row = {
            "code": "J10",
            "category": "J",
            "level": 3,
            "ko_name": "인플루엔자 바이러스가 확인된 인플루엔자",
            "en_name": None,
            "source_version": "KCD-9",
            "verified": True,
            "source_reference": "table",
        }
        assert repo.upsert_kcd_codes([row]) == 1
        row["ko_name"] = "독감(변경)"
        assert repo.upsert_kcd_codes([row]) == 1
        assert repo.count_kcd_codes() == 1
        assert repo.get_kcd_codes()["J10"]["ko_name"] == "독감(변경)"


class TestCatalogKcdReferences:
    def test_target_kcd_prefixes_are_catalog_standard(self) -> None:
        """Every rule_config KCD reference must be a valid KCD prefix shape."""
        for rule in STANDARD_RULES:
            for prefix in rule.rule_config.get("target_kcd_prefixes", []):
                assert kcd.normalize_code(prefix) == prefix, (
                    f"{rule.rule_id}: {prefix!r}는 KCD 코드 형식이 아닙니다"
                )

    def test_rule_config_codes_are_referenced_by_master_after_seed(self, tmp_path: Path) -> None:
        """After seeding representative codes, each catalog prefix must match some code."""
        engine = create_db_engine(database_url_for(tmp_path, "kcd_catalog_test.db"))
        init_schema(engine)
        repo = PolicyRepository(engine)

        # Representative KCD rows for every prefix referenced by the catalog rules.
        rows: list[dict[str, object]] = []
        for rule in STANDARD_RULES:
            for prefix in rule.rule_config.get("target_kcd_prefixes", []):
                if prefix not in {str(r["code"]) for r in rows}:
                    rows.append(
                        {
                            "code": prefix,
                            "category": prefix[0],
                            "level": 3,
                            "ko_name": f"{prefix} 참조 코드",
                            "en_name": None,
                            "source_version": "KCD-9",
                            "verified": True,
                            "source_reference": "test",
                        }
                    )
        assert rows, "catalog에 KCD 참조 규칙이 없습니다"
        repo.upsert_kcd_codes(rows)

        codes = repo.get_kcd_codes()
        missing = {
            rule.rule_id: p
            for rule in STANDARD_RULES
            for p in rule.rule_config.get("target_kcd_prefixes", [])  # type: ignore[attr-defined]
            if p not in codes
        }
        assert missing == {}, f"catalog의 KCD 참조가 마스터에 없습니다: {missing}"