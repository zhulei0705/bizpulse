# T10-C1 可选采集通道

原有 HTTP、RSS、人工 URL 和 CSV 路径保持原行为。`crawl4ai` 由原 `/api/v1/sources/{id}/run` 入口调度。默认关闭；不自动批准 Signal、不生成 Opportunity，也不自动关联企业。需要人工归属与现有分析/证据/审核流程。

## 安装与浏览器初始化（PowerShell）

```powershell
Set-Location D:\myAI\bizpulse\backend
.venv\Scripts\python.exe -m pip install -r requirements-crawl4ai.txt -c requirements-crawl4ai.lock.txt
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) '.browsers'
$env:CRAWL4_AI_BASE_DIRECTORY = Join-Path (Get-Location) 'data/crawl4ai_cache'
$env:PYTHONIOENCODING = 'utf-8'
.venv\Scripts\python.exe -m playwright install chromium
.venv\Scripts\python.exe -m pip check
```

固定 Crawl4AI 0.9.4、Playwright 1.63.0、psutil 7.2.2；实际安装依赖锁见 `docs/reports/t10_c1/dependencies_after.txt`。SDK 与浏览器均在项目中。正常运行时适配器自行设置子进程浏览器与缓存路径，过滤凭证环境变量，不调用 LLM。

## 站点许可先于启用

管理员在服务器 `backend/data/crawl_permissions.json` 维护许可，Source 配置不能自行批准站点。每个域名必须有明确允许的原始依据、网站条款审查、审查人/时间、带时区的有效期与路径范围。robots 允许、政府/企业官网身份、浏览器能打开，都不能代替条款与采集许可。

许可条目示意（不是有效许可，不能直接启用）：

```json
{
  "REPLACE_WITH_REVIEWED_PUBLIC_DOMAIN": {
    "status": "UNVERIFIED",
    "terms_url": "UNKNOWN",
    "permission_url": "UNKNOWN",
    "permission_quote": "UNKNOWN",
    "reviewed_by": "UNKNOWN",
    "reviewed_at": "UNKNOWN",
    "expires_at": "UNKNOWN",
    "allowed_path_prefixes": ["/public/news/"],
    "interval_seconds": 2
  }
}
```

`CRAWL4AI_PERMISSION_FILE` 可由可信服务器环境配置改为其他绝对路径，不能通过 API 请求设置。核实许可后设置 `CRAWL4AI_ENABLED=true` 并重启后端。测试报告中的沙盒许可仅覆盖采集技术测试，不能用于商业数据源。

Source 的 `collector_type="crawl4ai"`，`config_json` 例如：

```json
{
  "url": "https://REVIEWED_DOMAIN/public/news/1",
  "mode": "http",
  "css_selector": "article",
  "field_css": {"published_at": ".published-date"}
}
```

默认 HTTP 模式不启动 Chromium。只有经诊断的 JS 页面才配置 `mode="js"`，同时记录 `js_diagnosis` 的 `marker`（原始 HTML 中实际存在的标记）、`reason` 与 `http_failure`（`PARSE_EMPTY` 或 `JS_RENDER_REQUIRED`）；不是空正文就自动开浏览器。禁止配置 JS 代码、Cookie、请求头凭证、代理、CDP、扩展参数或 SDK hook。

## 有界采集与停止

- 强制检查 robots；404/410 按 RFC 9309 未配置 robots 处理；其他失败、拒绝与 robots 重定向都停止。
- 仅许可域名/路径及标准 80/443 端口；禁止登录、验证码、付费墙、凭证 URL、私网、回环与元数据。
- 每次连接验证所有 DNS 地址，DNS 集变化停止；连已验证数字 IP，HTTPS 按原域名校验证书；每跳重新检查许可/robots。
- 单进程 HTTP 并发 1、浏览器并发 1；域名请求间隔至少 2 秒，遵从更严格 robots 延迟/速率；最多 30 次请求。
- 单响应 2 MB、单任务总响应 8 MB、HTTP 请求超时 10 秒、HTTP 阶段最多 60 秒；浏览器进程树 50 秒/累计 CPU 35 秒/采样 RSS 800 MiB，超限终止进程树。RSS 为 50ms 采样监视，存在采样窗口，不是 OS 硬配额。
- 浏览器所有请求通过 context route 桥接到上述 HTTP 校验通道，背景直连使用不监听的保留本地代理端口而失败；阻断外域、下载、WebSocket、图片、字体、视频及 Service Worker 接口。需要外域 CDN 的站点会缺内容，禁止为成功率静默放宽。
- 原文/Evidence 不一致、安全异常、访问控制与资源异常立即停止，不退回旧的不受保护通道。只有 SDK 运行失败且已有合法有效正文，才可退回本次安全 HTTP 正文并记录原因。
- PDF 策略当前未配置，一律拒绝；单响应大小限制先执行，不下载附件、不调用 SDK 的默认 PDF 占位/解析策略。**尚未实现 PDF 页数受控解析，属于验收缺口。**

## 证据与业务审核

无新表/迁移。SourceRecord.raw_text 保存 `CLEANED_DOM_TEXT`，metadata 明确文本基准、Unicode 字符偏移、清洗正文 SHA256、原始响应字节/HTML/可见文本路径、渲染快照路径及哈希、原始/最终 URL、采集时间、状态、解析版本、许可和资源统计。快照用内容寻址路径，不覆盖旧版本。入库前重算快照哈希并复现 DOM 提取；不一致在写入之前停止。

字段只从显式 CSS 节点确定性提取；金额必须含明确人民币单位，日期必须有完整年月日，采购人/供应商/代理需明确角色标签。格式错误/缺失/多节点保持 UNKNOWN；时区不能推断。字段仅 `EXTRACTED_UNVERIFIED`，不会变成投标资格或已批准事实。现有 Reliability、EvidenceQualityGate、主体归属与 Actionability/人工审核代码未替换。

当前仅适合单 FastAPI worker。本地限流不能保证多个 worker/主机的全局域名限流；未做生产级浏览器操作系统隔离。PDF、跨域 JS 和商业样本质量验收完成前，不建议扩量。
