# 商脉 BizPulse V1 — 本地启动

## 1. 启动后端

Windows PowerShell / CMD：

```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python scripts\bootstrap.py
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

后端文档：`http://localhost:8000/docs`

## 2. 启动前端

新开一个终端：

```bat
cd frontend
copy .env.example .env
npm install
npm run dev
```

前端：`http://localhost:5173`

默认前端 API 指向：`http://localhost:8000/api/v1`。

## 3. 数据库

SQLite 在首次启动后生成于：`backend/data/bizpulse.db`。

数据库详细设计：`backend/docs/DATABASE_DESIGN.md`。
