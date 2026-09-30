# BizPulse 前端页面与后端 API 对照

| 前端页面 | 后端接口 |
|---|---|
| 首页 | `/system/info`, `/dashboard` |
| 机会雷达 | `/radar/summary`, `/opportunities` |
| 市场机会 | `/markets` |
| 企业库 | `/companies`, `/companies/{id}`, `/companies/{id}/contacts` |
| 商业信号 | `/signals`, `/signals/{id}` |
| 客户机会 | `/opportunities`, `/opportunities/{id}/stage` |
| 验证实验 | `/experiments`, `/experiments/{id}`, `/experiments/{id}/interactions` |
| 数据源 | `/sources`, `/sources/{id}`, `/sources/{id}/records` |
| 采集任务 | `/jobs`, `/jobs/{id}/run` |
| 分析日志 | `/logs/llm-runs`, `/logs/audit` |
| 系统设置 | `/system/info`；后续可扩展 `/system/configs` |

## 当前前端兼容性

现有前端 `src/api/system.ts` 的 `/health` 与 `/system/info` 已直接兼容本后端。

其余页面当前还是空态 UI，需要继续增加 `companies.ts / signals.ts / opportunities.ts ...` API Client 后即可接入本后端，无需修改后端路由结构。
