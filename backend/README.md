# 商脉 BizPulse Backend V1

商脉 BizPulse 的本地后端基础系统，对应现有 React 前端 UI。

核心数据链：

`真实来源 → SourceRecord → Company → Signal → PainPoint → Opportunity → Experiment / Interaction → 成交反馈`

## 1. 技术栈

- Python 3.11+
- FastAPI
- SQLAlchemy 2.x
- Pydantic 2.x
- Alembic
- SQLite（V1 本地）
- pytest
- httpx

后续可将 `DATABASE_URL` 切换为 PostgreSQL，业务模型无需重写。

## 2. 数据真实性原则

默认：`NO_FAKE_DATA=true`。

正式数据库初始化只创建表结构和系统配置，不插入假企业、假商机、假招聘或假成交数据。测试数据只存在 pytest 临时测试库，测试结束自动删除。

## 3. Windows 10 快速启动

```bat
cd bizpulse-backend-v1
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python scripts\bootstrap.py
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

也可以双击：

```text
start-backend.bat
```

访问：

- API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/api/v1/health`
- 系统信息：`http://localhost:8000/api/v1/system/info`

前端默认 API：`http://localhost:8000/api/v1`，与现有 BizPulse 前端 `.env.example` 一致。

## 4. 数据库初始化与迁移

推荐：

```bash
python scripts/bootstrap.py
```

或者仅执行迁移：

```bash
alembic upgrade head
```

生成新迁移：

```bash
alembic revision --autogenerate -m "your change"
alembic upgrade head
```

## 5. 自动测试

```bash
pytest -q
```

当前交付版本已实测：`5 passed`。

快速接口校验：

```bash
python scripts/verify_backend.py
```

## 6. 主要目录

```text
app/
  api/v1/endpoints/   REST API
  core/               配置、日志
  db/                 Engine、Session、Base
  models/             SQLAlchemy 数据模型
  schemas/            Pydantic 输入输出结构
  services/           评分、统计、采集、审计
alembic/               数据库迁移
scripts/               初始化/验证工具
tests/                 自动测试
docs/                  数据库和 API 设计文档
data/                  本地 SQLite（运行后生成）
logs/                  运行日志
```

## 7. 当前已实现的 V1 能力

- 系统健康和前端状态接口
- Dashboard / 机会雷达聚合
- 企业库 CRUD 基础能力
- 市场机会数据模型
- 公开联系人模型
- 数据源与原始证据记录
- 单公开 URL 的基础采集执行
- 商业信号
- 痛点推断数据结构
- 机会评分与证据门槛
- 客户机会看板阶段流转
- 商业验证实验
- 联系/回复/会议/报价/成交反馈
- LLM 分析日志数据模型
- 审计日志
- Alembic 完整首版迁移

## 8. 机会评分

代码公式：

`Pain×25% + Budget×20% + Intent×20% + Urgency×10% + AgentFit×10% + Reachability×5% + Evidence×10%`

等级：S ≥ 90，A ≥ 80，B ≥ 70，C ≥ 60，其余 D。

**证据门槛：Evidence < 60 时，即使加权总分很高，最高也只能显示 B。**

这确保“AI 推断”不能在证据不足时伪装成高确定性商业机会。

## 9. 下一步

后端 V1 已具备数据闭环基础。下一阶段建议按顺序加入：

1. 前端 9 个业务页面接真实 API；
2. CompanyResolver 企业去重；
3. SignalExtractor 结构化事实提取；
4. PainAnalyzer；
5. OpportunityGenerator；
6. LLMAdapter；
7. 更多合规公开数据 Adapter；
8. 定时调度。

不要先做多 Agent 编排。
