    运行uvicorn app.app:app --reload

  打开http://127.0.0.1:8000/
下面我直接帮你写一份**可以用于毕设 + GitHub展示的完整 README（专业版）**，你可以直接复制到项目里用（我已经帮你按“答辩级别”优化好了结构）。

---

# 🎮 Game Intel Agent（游戏行业智能分析系统）

> 基于 **FastAPI + Vue3 + MySQL + ChromaDB + LangGraph + LLM** 构建的
> **游戏行业招聘与资讯智能分析平台**

---

## 📌 一、项目简介

本项目是一个面向游戏行业的数据分析与智能问答系统，融合了**招聘数据 + 行业资讯数据**，通过 **结构化查询（SQL）+ 语义检索（RAG）+ 多智能体协作（Agent）** 的方式，实现对企业招聘趋势、岗位需求、技术方向等问题的智能分析。

系统支持用户通过自然语言提问，自动完成：

* 查询数据库（岗位、公司、城市分布）
* 检索语义信息（招聘描述、行业新闻）
* 生成图表分析结果
* 输出综合分析结论

👉 本项目适用于：

* 游戏行业分析
* 招聘趋势分析
* 技术方向洞察
* AI 数据分析系统实践

---

## 🧠 二、核心特性

### ✨ 1. 多 Agent 协作架构

系统采用多智能体设计：

* RouterAgent：问题分类与路由
* PlannerAgent：任务规划
* SQLAgent：结构化查询
* RAGAgent：语义检索（招聘 / 新闻）
* ChartAgent：图表生成
* AnalysisAgent：综合分析

---

### ✨ 2. 双数据源 RAG（创新点⭐）

系统构建了两个独立向量库：

* 📊 招聘岗位向量库（Job RAG）
* 📰 行业资讯向量库（News RAG）

支持：

* 单源检索
* 跨源融合分析（招聘 + 新闻）

---

### ✨ 3. SQL + RAG 混合检索

支持多种问题类型：

* 结构化问题 → SQL 查询
* 语义问题 → 向量检索
* 复杂问题 → SQL + RAG + 分析融合

---

### ✨ 4. LangGraph 工作流编排（核心亮点🔥）

完整处理流程：

```
用户问题
   ↓
RouterAgent（分类）
   ↓
PlannerAgent（规划）
   ↓
┌───────────────┬───────────────┐
│   SQL 查询     │   RAG 检索     │
│               │  (Job + News) │
└───────────────┴───────────────┘
   ↓
ChartAgent（可选）
   ↓
AnalysisAgent
   ↓
Final Answer
```

---

### ✨ 5. 可解释 AI（Explainable AI）

前端支持展示：

* SQL 查询结果
* 检索文档片段
* 分析过程
* 图表结果

---

## 🏗️ 三、系统架构

### 📌 总体架构

```
前端（Vue3）
   ↓
FastAPI 后端
   ↓
Agent 工作流（LangGraph）
   ↓
├── MySQL（结构化数据）
├── ChromaDB（向量库）
└── 爬虫数据源（招聘 + 新闻）
```

---

### 📌 技术栈

| 层级    | 技术                      |
| ----- | ----------------------- |
| 前端    | Vue3 + Vite             |
| 后端    | FastAPI                 |
| 数据库   | MySQL                   |
| 向量数据库 | ChromaDB                |
| 大模型   | LLM（可接 OpenAI / 本地模型）   |
| 工作流   | LangGraph               |
| 嵌入模型  | BGE (bge-small-zh-v1.5) |

---

## 🗂️ 四、项目结构

```
code/
├── app/                    # 后端核心
│   ├── api/                # 接口层
│   ├── agents/             # 多 Agent 实现
│   ├── core/               # 配置/数据库/模型
│   ├── services/           # 数据查询与向量服务
│   ├── workflows/          # LangGraph 工作流
│   ├── prompts/            # Prompt 模板
│   └── schemas/            # 数据结构定义
│
├── frontend/               # 前端 Vue 项目
│   ├── src/components/
│   └── dist/               # 构建产物
│
├── crawl/                  # 数据采集（招聘 + 新闻）
│
├── sql/                    # 数据库初始化脚本
│
├── chroma_jobs/            # 招聘向量库
├── chroma_yxrb/            # 新闻向量库
│
└── README.md
```

---

## 🗄️ 五、数据库设计

核心表结构：

| 表名             | 说明          |
| -------------- | ----------- |
| company        | 企业信息        |
| job_post       | 岗位信息        |
| job_text       | 岗位文本（职责/要求） |
| raw_document   | 原始抓取数据      |
| vector_mapping | 向量与岗位映射     |

👉 数据分层：

```
原始数据 → 清洗数据 → 结构化数据 → 向量数据
```

---

## 🔍 六、核心功能

### ✅ 1. 招聘数据分析

示例：

* 腾讯游戏招聘最多的岗位是什么？
* 上海游戏公司岗位分布如何？

---

### ✅ 2. 技能需求分析

* 游戏行业最热门技术栈
* AI / 后端 / 客户端需求对比

---

### ✅ 3. 行业趋势分析

* 某公司研发方向
* 技术发展趋势

---

### ✅ 4. 图表生成

支持：

* 柱状图
* 饼图
* 分布图

---

### ✅ 5. 智能问答

支持：

* SQL + RAG + 分析融合问答
* 多轮对话（前端支持）

---

## ⚙️ 七、环境配置

### 1️⃣ 安装依赖

```bash
pip install -r requirements.txt
```

前端：

```bash
cd frontend
npm install
```

---

### 2️⃣ 配置数据库

创建数据库：

```sql
CREATE DATABASE game_intel;
```

执行：

```bash
sql/init_schema.sql
```

---

### 3️⃣ 配置环境变量

编辑 `app/core/config.py` 或 `.env`：

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=xxx
DB_NAME=game_intel

OPENAI_API_KEY=your_key
```

---

### 4️⃣ 启动项目

后端：

```bash
uvicorn app.app:app --reload
```

前端：

```bash
cd frontend
npm run dev
```

访问：

```
http://localhost:5173
```

---

## 🚀 八、数据准备

### 1️⃣ 爬虫数据

```bash
python crawl/tencent_all.py
python crawl/wangyi_all.py
```

---

### 2️⃣ 构建向量库

```bash
python crawl/crawl_news_chromadb_all.py
```

---

## 📊 九、系统流程（数据流）

```
爬虫数据
   ↓
数据清洗
   ↓
MySQL 入库
   ↓
向量化（Embedding）
   ↓
ChromaDB
   ↓
用户提问
   ↓
Agent 工作流
   ↓
SQL / RAG / 分析
   ↓
返回结果
```

---

## 💡 十、创新点（答辩重点⭐）

1. **多 Agent 协作架构**
2. **SQL + RAG 混合检索**
3. **双向量库（招聘 + 新闻）**
4. **LangGraph 工作流编排**
5. **可解释 AI（证据展示）**
6. **行业垂直分析（游戏领域）**

---

## 🧪 十一、示例问题

* 腾讯游戏在哪些城市招聘最多？
* 游戏行业最需要哪些技术？
* 米哈游未来研发方向是什么？
* 游戏公司是否在加大 AI 投入？

---

## ⚠️ 十二、注意事项

* 需提前准备数据库和向量库数据
* LLM 接口需配置 API Key
* 首次运行可能较慢（需加载 embedding 模型）

---

## 📌 十三、后续优化方向

* 接入更多数据源（BOSS / 拉勾 / Steam）
* 引入实时数据流（Kafka）
* 优化 Agent 决策策略
* 增加推荐系统

---

## 👨‍🎓 十四、作者说明

本项目为本科毕业设计项目，主要研究方向：

* AI Agent 系统设计
* RAG 检索增强生成
* 数据分析与可视化

---

## ⭐ 如果对你有帮助，欢迎 Star！

---


