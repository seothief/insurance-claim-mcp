"""Infer the Korean silson (indemnity medical insurance) generation when a policy omits it.

Generation switch years: 1세대 ~2009.9, 2세대 2009.10~2017.3, 3세대 2017.4~2021.6, 4세대 2021.7~.
Years 2009, 2017 and 2021 contain a switch, so the year alone cannot decide the generation.
Inferred values are estimates; the stored policy is never changed.
"""

ANNUAL_RANGES: tuple[tuple[int, int, int], ...] = (
    (1980, 2008, 1),
    (2010, 2016, 2),
    (2018, 2020, 3),
    (2022, 2100, 4),
)
BOUNDARY_YEARS = frozenset({2009, 2017, 2021})


def resolve_silson_generation(
    explicit: int | None, enrolled_year: int | None
) -> tuple[int | None, str]:
    """Return (generation, note). generation is None when it cannot be determined safely."""
    if explicit is not None:
        return explicit, ""
    if enrolled_year is None:
        return None, (
            "실손보험 세대(1~4세대)와 가입연도가 모두 없어 계산하지 않았습니다. "
            "증권에서 세대를 확인해 지정해 주세요."
        )
    if enrolled_year in BOUNDARY_YEARS:
        return None, (
            f"{enrolled_year}년은 실손 세대가 바뀐 해라 연도만으로 세대를 정할 수 없어 "
            "계산하지 않았습니다. 증권의 세대 또는 가입일을 지정해 주세요."
        )
    for start, end, generation in ANNUAL_RANGES:
        if start <= enrolled_year <= end:
            return generation, (
                f"세대가 지정되지 않아 가입연도 {enrolled_year}년 기준 "
                f"{generation}세대로 추정했습니다."
            )
    return None, f"가입연도 {enrolled_year}년은 실손 세대 기준에 해당하지 않아 계산하지 않았습니다."
