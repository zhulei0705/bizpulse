"""T05 商业机会判断引擎 —— 分析器包。

流程：Approved Signals → Signal Bundles → Pain/Intent/Budget/Urgency/AgentFit/
Reachability/Evidence 分析（全部代码计算、可解释）→ ScoreEngine → EvidenceGate
→ OpportunityCandidate（默认 REVIEW，V1 不自动批准）。

铁律：
- 分数由代码计算，LLM 只产出结构化解释；
- 没有真实 Signal + Evidence 不产生任何候选；
- 事实不足时保持低分/UNKNOWN，禁止编造金额、联系人、ROI。
"""
