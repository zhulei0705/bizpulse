"""T08.0 P0-4 Reliability 统一：来源等级唯一可信传递规则。

原则（任务书 P0-4）：
- Source 配置为基础等级；
- 下游（SourceRecord / Evidence / Signal）默认继承 Source；
- 下游可以因为验证失败显式降级；
- 下游禁止无理由升级（effective_grade 取 min(源, 下游声明)）。
"""
from __future__ import annotations

_GRADE_ORDER = {"A": 4, "B": 3, "C": 2, "D": 1}
_DEFAULT_SCORE = {"A": 95, "B": 80, "C": 60, "D": 40}


def effective_grade(source_grade: str | None, downstream_grade: str | None = None) -> str:
    """生效等级：下游声明不得高于 Source（无理由升级被压制为 Source 等级）。"""
    source = (source_grade or "C").upper()
    if source not in _GRADE_ORDER:
        source = "C"
    if not downstream_grade:
        return source
    downstream = downstream_grade.upper()
    if downstream not in _GRADE_ORDER:
        return source
    # 下游比源高 → 无理由升级，压制回源等级
    return source if _GRADE_ORDER[downstream] > _GRADE_ORDER[source] else downstream


def effective_score(source_grade: str | None, source_score: int | None = None, downstream_grade: str | None = None) -> int:
    """生效分数：按生效等级映射；Source 自带分数优先（同等级时）。"""
    grade = effective_grade(source_grade, downstream_grade)
    if source_score is not None and grade == effective_grade(source_grade):
        return int(source_score)
    return _DEFAULT_SCORE.get(grade, 50)


def propagate_record_grade(source_grade: str | None) -> str:
    """SourceRecord 采集快照：默认继承 Source 等级（除非后续显式降级）。"""
    return effective_grade(source_grade)
