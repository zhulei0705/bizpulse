# 商脉 BizPulse V1 API

统一前缀：`/api/v1`

所有主业务接口采用：

```json
{"success": true, "data": {}, "message": null}
```

## 系统与首页

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/health` | 健康检查 |
| GET | `/system/info` | 前端系统状态 |
| GET | `/dashboard` | 首页统计与占位聚合数据 |
| GET | `/radar/summary` | 机会雷达汇总 |

## 市场与企业

| 方法 | 路径 | 用途 |
|---|---|---|
| GET/POST | `/markets` | 市场清单 / 新建市场 |
| GET | `/markets/{id}` | 市场详情 |
| GET/POST | `/companies` | 企业分页搜索 / 新建企业 |
| GET/PATCH | `/companies/{id}` | 企业详情 / 更新企业 |
| GET/POST | `/companies/{id}/contacts` | 企业公开联系人 |

## 数据源与采集

| 方法 | 路径 | 用途 |
|---|---|---|
| GET/POST | `/sources` | 数据源管理 |
| GET/PATCH | `/sources/{id}` | 数据源详情 / 修改 |
| POST | `/sources/{id}/records` | 写入真实原始证据记录 |
| GET/POST | `/jobs` | 采集任务 |
| POST | `/jobs/{id}/run` | 执行一个公开网页采集任务 |

`/jobs/{id}/run` 仅做普通公开 HTTP/HTTPS 请求，不绕过登录、验证码或访问控制。

## 信号、痛点、机会

| 方法 | 路径 | 用途 |
|---|---|---|
| GET/POST | `/signals` | 商业信号列表 / 新建 |
| GET | `/signals/{id}` | 信号详情与来源证据 |
| GET/POST | `/pain-points` | 痛点推断数据 |
| GET/POST | `/opportunities` | 商业机会列表 / 新建并由代码评分 |
| GET | `/opportunities/{id}` | 机会详情 + 证据链 |
| PATCH | `/opportunities/{id}/stage` | 看板阶段流转 |
| POST | `/opportunities/{id}/evidences` | 追加机会证据 |

机会阶段：`NEW / PENDING_REVIEW / READY / CONTACTED / REPLIED / MEETING / QUOTED / WON / REJECTED`。

## 验证实验

| 方法 | 路径 | 用途 |
|---|---|---|
| GET/POST | `/experiments` | 验证实验清单 / 新建 |
| GET | `/experiments/{id}` | 实验详情 + 自动转化指标 |
| POST | `/experiments/{id}/interactions` | 记录联系、回复、会议、报价、成交 |

## 日志

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/logs/llm-runs` | AI 分析运行记录 |
| GET | `/logs/audit` | 关键业务操作审计 |

完整 Swagger：启动后访问 `http://localhost:8000/docs`。
