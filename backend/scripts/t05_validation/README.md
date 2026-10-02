# T05 真实数据验证脚本

按顺序在本地服务运行时执行（后端 `http://127.0.0.1:8000`），用于复现 T05 验收中的
"真实数据验证"（ccgp.gov.cn 真实招标公告 → 信号 → 机会候选 → 人工审核闭环）：

1. `step1_ingest_and_approve.py`   创建 3 家真实采购单位、采集真实招标公告、信号分析并人工批准
2. `step2_analyze_and_inspect.py`  强制重新运行机会分析，输出候选分数明细（含 evidence 分与 score_breakdown，验证来源等级修复 C→A 对评分的影响）
3. `step3_grade_fix_and_reanalyze.py` 人工修正来源等级、驳回误报信号、强制重新分析
4. `step4_review_and_batch_job.py` 候选审核转正式机会、批量分析 job（输入 hash 跳过）与审计检查

注意：脚本内企业与 URL 为 T05 验收时使用的真实样例，可按需替换。
