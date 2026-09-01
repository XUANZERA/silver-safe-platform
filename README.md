# 听见北斗，看见安心 —— 文旅街区银发独游安心服务协同平台

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Vue.js-3.x-4FC08D?style=flat-square&logo=vue.js&logoColor=white" alt="Vue3" />
  <img src="https://img.shields.io/badge/Vite-5.x-646CFF?style=flat-square&logo=vite&logoColor=white" alt="Vite" />
  <img src="https://img.shields.io/badge/pnpm-8.x+-F69220?style=flat-square&logo=pnpm&logoColor=white" alt="pnpm" />
  <img src="https://img.shields.io/badge/DeepSeek-V3%20%2F%20R1-blue?style=flat-square" alt="DeepSeek" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg?style=flat-square" alt="License" />
</p>

> **面向文旅街区（如广州永庆坊）的老年人独立出游协同保障平台。**  
> 依托**旅游制约理论**（Leisure Constraints Theory），深度融合**北斗亚米级高精度定位**、**大语言模型（DeepSeek）适老语音护航**与**多方协同应急响应机制**，打破“想游却不敢游”的现实困境，赋能银发群体重获独立出游的底气与自由。

---

## 目录

- [听见北斗，看见安心 —— 文旅街区银发独游安心服务协同平台](#听见北斗看见安心--文旅街区银发独游安心服务协同平台)
  - [目录](#目录)
  - [一、项目背景与痛点](#一项目背景与痛点)
  - [二、核心设计理念与学科支撑](#二核心设计理念与学科支撑)
  - [三、系统架构与多方协同](#三系统架构与多方协同)
  - [四、核心功能模块](#四核心功能模块)
    - [1. 👴 老人端：零学习成本的智能伴游](#1--老人端零学习成本的智能伴游)
    - [2. 📱 子女端：无感静默守护看板](#2--子女端无感静默守护看板)
    - [3. 🗺️ 街区运营与仿真中台](#3-️-街区运营与仿真中台)
  - [五、技术栈](#五技术栈)
  - [六、项目目录结构](#六项目目录结构)
  - [七、快速开始与本地启动](#七快速开始与本地启动)
    - [1. 环境准备](#1-环境准备)
    - [2. 后端服务启动](#2-后端服务启动)
    - [3. 前端服务启动](#3-前端服务启动)
  - [八、核心 API 调用说明](#八核心-api-调用说明)
    - [DeepSeek 适老行程伴游对话](#deepseek-适老行程伴游对话)
      - [请求示例 (Request)](#请求示例-request)
      - [响应示例 (Response)](#响应示例-response)
  - [九、自动化测试与代码规范](#九自动化测试与代码规范)
    - [后端代码规范与测试](#后端代码规范与测试)
    - [前端单元测试与打包验证](#前端单元测试与打包验证)
  - [十、界面展示 (Screenshots)](#十界面展示-screenshots)
  - [十一、参考文献](#十一参考文献)
  - [开源协议](#开源协议)

---

## 一、项目背景与痛点

我国已步入中度老龄化社会（60 岁及以上人口超 3.1 亿，占比达 22%）。庞大的银发旅游市场需求持续旺盛，但老年人在独立出游时面临三大核心痛点：

1. **老人端（个人心理与生理障碍）**：害怕迷路、突发疾病无人知晓，对复杂智能手机界面产生“数字鸿沟”排斥心理。
2. **家庭端（子女心理负担）**：子女担忧出行安全而劝阻或强制陪同，缺乏低干扰、高可靠的远程守护手段。
3. **街区端（服务资源碎片化）**：商户适老资源、志愿者、医疗应急站各自割裂，缺乏统一调度机制与亚米级精准应急闭环。

---

## 二、核心设计理念与学科支撑

平台以**旅游制约理论**为根基，构建“行前-行中-异常-行后”全流程服务闭环：

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                          旅游制约理论与系统映射                           │
├──────────────────┬───────────────────┬──────────────────────────────────┤
│ 制约维度 (Theory) │ 平台解决系统 (System)│ 核心功能与技术支撑                 │
├──────────────────┼───────────────────┼──────────────────────────────────┤
│ 内在制约 (Intra)  │ VR 实景慢速云踩点  │ 1:1 老人视角还原、大屏适配、环境脱敏 │
├──────────────────┼───────────────────┼──────────────────────────────────┤
│ 结构制约 (Struct) │ 语音护航 & 电子围栏│ 极简大字交互、北斗高精度轨迹、异常预警│
├──────────────────┼───────────────────┼──────────────────────────────────┤
│ 人际制约 (Inter) │ 子女端安心看板    │ 静默安全围栏、实时足迹、一键联动确认  │
├──────────────────┼───────────────────┼──────────────────────────────────┤
│ 协同制约 (System)│ 街区适老一张图    │ 志愿者/商户/运营方统一调度与评价闭环 │
└──────────────────┴───────────────────┴──────────────────────────────────┘
```

---

## 三、系统架构与多方协同

平台贯通**老年人、子女、文旅街区运营方、银发商户、志愿组织、北斗/VR技术方、文旅监管部门**七大主体：

```text
                     ┌───────────────────────────┐
                     │   文旅部门 / 街区运营后台   │
                     │ (态势感知 / 适老调度一张图) │
                     └─────────────┬─────────────┘
                                   │ 统一派单/资源调度
    ┌──────────────────────┬───────┴───────┬──────────────────────┐
    ▼                      ▼               ▼                      ▼
┌──────────────┐   ┌──────────────┐  ┌──────────────┐   ┌───────────────────┐
│ 老人移动端    │   │ 子女微信小程序│  │ 志愿者 / 商户 │   │   北斗 / AI 中台   │
│ (极简大字语音)│   │ (静默守护看板)│  │ (就近接单响应)│   │(DeepSeek/轨迹/围栏)│
└──────────────┘   └──────────────┘  └──────────────┘   └───────────────────┘
```

---

## 四、核心功能模块

### 1. 👴 老人端：零学习成本的智能伴游
* **极简语音护航**：全语音驱动 + 关键词唤醒，搭配高对比度大字体。
* **DeepSeek 智能行程助聊**：集成 DeepSeek 适老对话模型，口语化解答“洗手间在哪”、“如何回游客中心”并推荐平缓路线。
* **一键 SOS 与自动跌倒报警**：传感器/长按一键求助，亚米级坐标秒级广播。

### 2. 📱 子女端：无感静默守护看板
* **自定义电子安全区**：老人在安全围栏内活动不打扰；偏离规划路线或越界时触发提醒。
* **当日足迹生成**：自动汇总行程打卡点与运动轨迹，便于寻物与回顾。

### 3. 🗺️ 街区运营与仿真中台
* **适老一张图（MapCanvas）**：沉浸式渲染无障碍坡道、适老卫生间、爱心饮水点、志愿岗亭。
* **动态轨迹与仿真推演**：支持真实北斗经纬度接入与虚拟仿真推演（`locationSimulator`），用于应急演练。

---

## 五、技术栈

| 层次 | 技术选型 | 说明 |
| :--- | :--- | :--- |
| **前端架构** | Vue 3 + Vite + Vue Router + Pinia | 响应式组件化架构，构建极简适老化界面 |
| **包管理** | Corepack + pnpm | 严格的锁版本管理与依赖安全 |
| **地图与仿真** | Canvas / Map Canvas 渲染 + 坐标算法 | 街区适老点位与动态轨迹插值渲染 |
| **后端架构** | Python 3.10+ / FastAPI / Pydantic | 高性能异步 RESTful API 与严格数据校验 |
| **AI 大模型** | DeepSeek API (Chat & Function Calling) | 适老语义理解、口语化路线生成与意图识别 |
| **测试与质量** | Pytest / Ruff / Vitest | 单元测试、代码规范与自动化 Lint/Format |

---

## 六、项目目录结构

```text
silver-safe-platform/
├── backend/                  # 后端服务 (FastAPI)
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/       # 业务路由 (ai.py, elder.py, trip.py, etc.)
│   │   ├── core/             # 配置中心与安全认证
│   │   ├── models/           # 数据模型定义
│   │   └── services/         # 核心服务 (DeepSeek 客户端、电子围栏判定)
│   ├── tests/                # Pytest 单元与集成测试用例
│   ├── requirements.txt      # 运行依赖
│   └── requirements-dev.txt  # 开发与测试依赖 (pytest, ruff)
├── frontend/                 # 前端服务 (Vue 3)
│   ├── src/
│   │   ├── components/       # 公共组件 (MapCanvas.vue, etc.)
│   │   ├── views/            # 视图页面 (ElderHome, ChildHome, OperatorDashboard)
│   │   ├── services/         # 前端 API 封装与仿真器 (locationSimulator.js)
│   │   └── router/           # 路由配置 (routes.js)
│   ├── package.json
│   └── pnpm-lock.yaml
├── docs/                     # 架构文档与接口设计说明
└── README.md
```

---

## 七、快速开始与本地启动

### 1. 环境准备

* **Node.js**: `v18.0.0+`
* **Python**: `v3.10+`
* **Corepack**: 启用（`corepack enable`）

### 2. 后端服务启动

```powershell
# 1. 进入项目根目录并激活虚拟环境
cd silver-safe-platform
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. 安装开发依赖
pip install -r backend/requirements-dev.txt

# 3. 配置环境变量 (创建 backend/.env 文件)
# DEEPSEEK_API_KEY=your_deepseek_api_key_here

# 4. 启动 FastAPI 后端服务
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

后端服务将在 `http://127.0.0.1:8000` 启动，Swagger 交互式文档可访问 `http://127.0.0.1:8000/docs`。

### 3. 前端服务启动

```powershell
# 1. 进入前端目录
cd frontend

# 2. 安装前端依赖
corepack pnpm install --frozen-lockfile

# 3. 启动 Vite 开发服务器
corepack pnpm dev
```

浏览器访问 `http://127.0.0.1:5173` 即可进入系统。

---

## 八、核心 API 调用说明

### DeepSeek 适老行程伴游对话

* **Endpoint**: `POST /api/v1/ai/chat`
* **Description**: 接收老人语音转换后的文本，结合当前老人状态与街区地理位置，生成简短、友善、口语化的指引。

#### 请求示例 (Request)
```json
{
  "elder_id": "ELDER_1002",
  "message": "我想去最近的无障碍洗手间，路好走吗？",
  "current_location": {
    "lat": 23.1189,
    "lng": 113.2351
  }
}
```

#### 响应示例 (Response)
```json
{
  "code": 200,
  "data": {
    "reply": "您好！距离您 80 米处的荔湾非遗馆旁设有无障碍洗手间，全程为平整青石板路无台阶。已为您规划平缓路线，请跟随语音慢行。",
    "actions": [
      {
        "type": "NAVIGATE_TO_POI",
        "target_name": "荔湾非遗馆无障碍卫生间",
        "lat": 23.1192,
        "lng": 113.2356
      }
    ]
  },
  "message": "success"
}
```

---

## 九、自动化测试与代码规范

本项目严格执行持续集成与质量控制，每次提交前需通过全量校验：

### 后端代码规范与测试

```powershell
# 1. 运行后端全量测试
$env:DEBUG="false"
.\.venv\Scripts\python.exe -m pytest backend

# 2. Ruff 静态代码检查
.\.venv\Scripts\python.exe -m ruff check backend

# 3. Ruff 格式规范检查
.\.venv\Scripts\python.exe -m ruff format --check backend
```

### 前端单元测试与打包验证

```powershell
cd frontend

# 1. 运行前端单元测试
corepack pnpm test

# 2. 运行构建测试 (确保无类型与打包报错)
corepack pnpm build
```

---

## 十、界面展示 (Screenshots)

| 老人端极简伴游界面 | 子女端安心看板 |
| :---: | :---: |
| *(截图占位：大字极简导航与语音浮窗)* | *(截图占位：电子围栏范围与足迹卡片)* |
| **街区适老调度一张图 (MapCanvas)** | **DeepSeek 伴游会话** |
| *(截图占位：适老 POI 分布与动态仿真轨迹)* | *(截图占位：适老口语化智能解答与路线推送)* |

---

## 十一、参考文献

1. 国家统计局.《2025 年全国 1% 人口抽样调查主要数据公报》, 2026.
2. 民政部, 全国老龄办.《2024 年度国家老龄事业发展公报》, 2025.
3. 中国旅游研究院.《中国银发旅游市场发展潜力测算报告》.
4. 去哪儿旅行.《2025 “新银发一族” 飞行报告》.
5. 江苏省消保委.《“银发一族” 旅游消费调查报告》, 2025.

---

## 开源协议

本项目采用 [MIT License](LICENSE) 开源许可协议。
```