# 舞镜·智芯 AI舞蹈教练

基于 MediaPipe 姿态检测与 DeepSeek 大模型的 AI 舞蹈教学应用。通过摄像头实时捕捉用户舞姿，与标准动作对比，给出姿态矫正和分步骤训练建议。

## 功能特性

- 实时姿态检测：基于 MediaPipe Pose 提取 33 个身体关键点
- 舞蹈评分：与标准舞蹈视频对比，多维评分（姿态、节奏、协调性）
- AI 教练对话：集成 DeepSeek，回答动作要领、姿态矫正、训练方法等问题
- 动作库管理：自动扫描 `vidoe/` 目录构建视频库

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

### 3. 配置 DeepSeek API Key

编辑 `config.json`，填入你的 API Key：

```json
{
  "deepseek_api_key": "sk-xxx"
}
```

### 4. 准备舞蹈视频

将标准舞蹈视频放入 `vidoe/` 目录（支持 .mp4/.mov/.avi/.webm/.mkv）。

### 5. 启动应用

```bash
python app.py
```

## 目录结构

```
├── app.py                    # 主入口（Flask 应用）
├── pose_analyzer.py          # 姿态检测分析
├── scoring_engine.py         # 舞蹈评分引擎
├── dance_standards.py        # 标准动作管理
├── dance_features.py         # 舞蹈特征提取
├── feedback_renderer.py      # 反馈渲染
├── standard_from_video.py    # 从视频提取标准动作
├── dance_coach.py            # AI 教练对话模块
├── templates/                # 前端页面
├── vidoe/                    # 舞蹈视频库
└── config.json               # 配置文件
```

## 技术栈

- Python 3.12
- MediaPipe
- OpenCV
- Flask
- DeepSeek API
