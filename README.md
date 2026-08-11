# 舞镜·智芯 AI舞蹈教练

基于 MediaPipe 姿态检测与大模型（DeepSeek 等，兼容 OpenAI 接口）的 AI 舞蹈教学应用。通过摄像头实时捕捉用户舞姿，与标准舞蹈视频动作对比，给出姿态矫正、多维评分和分步骤训练建议。

## 功能特性

- 实时姿态检测：基于 MediaPipe Pose 提取 33 个身体关键点
- 实时训练：摄像头画面镜像显示，与标准舞蹈视频**左右并排对比**，支持点击放大预览
- 舞蹈评分：与标准舞蹈视频对比，多维评分（姿态、对称性、幅度等）
- **跟练模式（DTW 时序对齐）**：自动从标准视频提取姿态标准序列，逐帧与用户动作时序对齐评分，支持「跟练进度」实时反馈与关节偏差提示
- 训练暂停：训练中可随时暂停/继续，暂停期间计时冻结、不计分
- 视频库：自动扫描 `vidoe/` 目录构建视频库，支持上传（可选标题/分类）、搜索、分类、删除
- AI 教练对话：三级优先级 **用户 Key > config.json 全局 > 内置免费答疑引擎**
  - 每个用户可在网页「⚙️ 大模型」自行配置自己的 API Key（加密存储，兼容任意 OpenAI 接口服务）
  - 未配置任何 Key 时，自动使用内置免费答疑引擎（山膀手位、站姿体态、软开度、旋转、跳跃、热身放松、损伤预防等知识库）
- 用户系统：注册 / 登录 / 登出（SQLite 存储，PBKDF2 密码哈希，Flask 签名会话）
- 后台管理：数据看板（用户数、视频数、训练次数/时长、平均分、近7天趋势）、用户封禁与管理员权限管理
- 训练统计：累计训练次数 / 时长 / 今日数据 / 历史得分

## 快速开始

### 1. 创建虚拟环境

```bash
python -m venv venv
```

- Windows 激活：`venv\Scripts\activate`
- Mac/Linux 激活：`source venv/bin/activate`

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置大模型（可选）

不配置也能用——自动走内置免费答疑引擎。要启用大模型回答，二选一：

- **全局配置**：在项目根目录新建 `config.json`（该文件含 API Key，已从版本控制移除），填入你的 Key / 模型 / 接口：

  ```json
  {
    "deepseek_api_key": "你的API Key",
    "deepseek_model": "glm-4-flash-250414",
    "deepseek_base_url": "https://open.bigmodel.cn/api/paas/v4"
  }
  ```

  推荐使用免费模型：智谱 **GLM-4-Flash**（`glm-4-flash-250414`，永久免费，接口 `https://open.bigmodel.cn/api/paas/v4`）。也可换成 DeepSeek、通义千问 Qwen 等任意 OpenAI 兼容接口。

- **用户配置（推荐）**：启动后登录网页，点右上角「⚙️ 大模型」，填写自己的 API Key / Base URL / 模型名（兼容 OpenAI 接口格式 `/chat/completions`，如 DeepSeek、通义千问 Qwen 等）。留空保存即清除用户配置。

### 4. 准备舞蹈视频

将标准舞蹈视频放入 `vidoe/` 目录（支持 .mp4/.mov/.avi/.webm/.mkv），或直接在视频库页面上传。

### 5. 启动应用

```bash
python run.py
```

浏览器访问 `http://127.0.0.1:5000`，首次注册的账号自动成为管理员（默认数据中预置管理员 `admin / admin123`，请及时修改密码）。

## 目录结构（分层架构）

```
├── run.py                     # 启动脚本
├── app/                       # 应用包（分层架构）
│   ├── __init__.py            # 应用工厂 create_app()，注册所有蓝图
│   ├── config.py              # 配置读取（config.json + 环境变量）
│   ├── state.py               # 全局运行时状态（摄像头/分析器/统计）
│   ├── models.py              # 数据访问层（视频库/训练统计/SQLite 用户）
│   ├── security.py            # 认证装饰器 + 密码哈希 + LLM Key 加解密
│   ├── services/              # 业务逻辑层
│   │   ├── pose_runner.py     # 姿态处理循环 + MJPEG 视频流
│   │   ├── video_lib.py       # 视频库/标准提取/上传
│   │   ├── coach.py           # AI 教练对话封装
│   │   └── stats.py           # 训练统计逻辑
│   └── routers/               # API 路由层（Flask Blueprint）
│       ├── auth.py            # /api/auth/* 认证
│       ├── admin.py           # 首页/管理页 + /api/admin/*
│       ├── live.py            # /video_feed /api/analysis /api/start|stop
│       ├── videos.py          # /api/videos /api/upload /api/use_video
│       ├── coach.py           # /api/chat /api/coach/* /api/llm/*
│       └── stats.py           # /api/stats /api/training/* /api/score/*
├── pose_analyzer.py           # 姿态检测分析（MediaPipe）
├── scoring_engine.py          # 舞蹈评分引擎
├── dance_standards.py         # 标准动作管理
├── dance_features.py          # 舞蹈特征提取
├── feedback_renderer.py       # 反馈渲染
├── standard_from_video.py     # 从视频提取标准动作
├── dtw_tracker.py             # DTW 时序对齐（标准序列提取 + 在线对齐评分）
├── dance_coach.py             # AI 教练对话模块 + 内置免费答疑引擎
├── templates/                 # 前端页面（index / admin）
├── vidoe/                     # 舞蹈视频库
├── users.db                   # 用户数据库（运行时自动生成）
└── config.json                # 全局配置文件（含 API Key，不入版本控制，需自行创建）
```

## 技术栈

- Python 3.12
- MediaPipe
- OpenCV
- Flask
- SQLite（标准库）
- DeepSeek / 智谱 GLM / 任意 OpenAI 兼容大模型 API
