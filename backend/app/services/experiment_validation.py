"""T08.0 P1-1 ExperimentValidationService：启动前一致性校验（不自动修改数据）。

检查目标数量与成功标准的逻辑冲突，输出数据质量警告。
"""
from __future__ import annotations

import re

from app.models.experiment import Experiment


def validate_experiment_consistency(experiment: Experiment) -> list[dict]:
    """一致性检查：返回 warnings 列表（severity/info + message）。不修改任何数据。"""
    warnings: list[dict] = []
    targets = experiment.targets or []
    target_count = experiment.target_company_count or 0
    sum_targets = (experiment.target_contacts or 0)

    # 1) 目标企业数 vs 目标联系数矛盾（真实案例：target_company_count=1 但 target_contacts=30）
    if target_count > 0 and experiment.target_contacts and experiment.target_contacts > target_count * 3:
        warnings.append({
            "severity": "HIGH",
            "code": "TARGET_COUNT_MISMATCH",
            "message": f"target_company_count={target_count} 但 target_contacts={experiment.target_contacts}：联系目标远超企业目标，疑似配置错误",
        })

    # 2) 成功标准中的数字 vs 目标值冲突
    criteria = experiment.success_criteria or ""
    numbers_in_criteria = [int(n) for n in re.findall(r"(\d+)\s*家", criteria)]
    if numbers_in_criteria:
        max_companies = max(numbers_in_criteria)
        if target_count and max_companies > target_count:
            warnings.append({
                "severity": "HIGH",
                "code": "CRITERIA_EXCEEDS_TARGETS",
                "message": f"成功标准要求「{max_companies} 家」，但实验目标企业只有 {target_count} 家：标准无法达成",
            })

    # 3) 成功标准含糊（任务书九：不能只有"测试AI销售Agent"）
    if not criteria or len(criteria.strip()) < 8:
        warnings.append({
            "severity": "MEDIUM",
            "code": "SUCCESS_CRITERIA_TOO_VAGUE",
            "message": "成功标准缺失或过于含糊：应写明可量化的达成条件（回复率/会议数/试点数）",
        })

    # 4) 报价假设缺失（Offer 不完整）
    if experiment.price_amount is None and not experiment.pricing_hypothesis:
        warnings.append({
            "severity": "MEDIUM",
            "code": "PRICE_HYPOTHESIS_MISSING",
            "message": "报价假设缺失：Experiment 必须明确价格假设（PRICE_HYPOTHESIS，不代表市场接受价）",
        })

    # 5) RUNNING 但无目标企业
    if experiment.status == "RUNNING" and not targets:
        warnings.append({
            "severity": "MEDIUM",
            "code": "RUNNING_WITHOUT_TARGETS",
            "message": "实验已开始（RUNNING）但没有任何验证目标企业：请通过 targets/select 或加入机会补充",
        })

    # 6) 快照缺失
    if experiment.status == "RUNNING" and not experiment.snapshot_json:
        warnings.append({
            "severity": "LOW",
            "code": "SNAPSHOT_MISSING",
            "message": "实验进行中但缺少 Experiment Snapshot：历史结果将难以解释（建议结束本实验并新建）",
        })
    return warnings
