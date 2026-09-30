# 商脉 BizPulse 前端

基于 React + TypeScript + Vite 的 BizPulse V1 前端骨架，视觉风格对齐“未来商业情报中枢”。

## 页面
- 首页
- 机会雷达
- 市场机会
- 企业库
- 商业信号
- 客户机会
- 验证实验
- 数据源
- 采集任务
- 分析日志
- 系统设置

## 数据原则
默认不内置任何假企业、假商机、假招聘或假成交数据。所有业务数值均显示为 `—` 或空状态，直到后端返回真实数据。

## 运行
```bash
npm install
npm run dev
```

默认地址：`http://localhost:5173`

## 后端
复制 `.env.example` 为 `.env`，默认 API：

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

首页会调用：
- `GET /health`
- `GET /system/info`

## 构建
```bash
npm run build
```

## UI 参考图
`docs/ui-reference/` 内已包含本次生成的 10 张核心页面视觉参考图。代码没有把这些图片当作页面背景，而是将视觉语言重新实现为可维护的 React/CSS 组件，避免把假数据或图片文字直接带入产品。
