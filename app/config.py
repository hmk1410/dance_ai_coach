# -*- coding: utf-8 -*-
"""
config.py
应用配置：读取 config.json（全局大模型配置）+ 环境变量。
仿青就业的 config.py：集中管理路径与配置项。
"""

import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
VIDEO_DIR = os.path.join(BASE_DIR, 'vidoe')
META_FILE = os.path.join(BASE_DIR, 'videos_meta.json')
STATS_FILE = os.path.join(BASE_DIR, 'training_stats.json')

VIDEO_EXTS = ('.mp4', '.mov', '.avi', '.webm', '.mkv')

DEFAULT_CONFIG = {
    'deepseek_api_key': '',
    'deepseek_model': 'deepseek-chat',
    'deepseek_base_url': 'https://api.deepseek.com',
    'coach_system_prompt': (
        '你是「舞镜·智芯」AI舞蹈教练，一位专业、耐心、友善的中文舞蹈老师。'
        '你精通古典舞、现代舞、街舞等舞种，熟悉中国古典舞手位（如：山膀、按掌、提腕、压腕）'
        '和身体姿态要求（立腰拔背、双肩平正、手臂圆润等）。'
        '用户会向你请教舞蹈动作要领、姿态矫正、训练方法、身体损伤预防等问题。'
        '请用简洁、清晰、鼓励的语气回答，必要时给出分步骤建议。回答控制在500字以内。'
    )
}


def load_config():
    """读取配置：config.json 为基础，环境变量 DEEPSEEK_API_KEY 优先"""
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            file_cfg = json.load(f)
        cfg.update({k: v for k, v in file_cfg.items() if v not in (None, '')})
    except Exception:
        pass
    env_key = os.environ.get('DEEPSEEK_API_KEY')
    if env_key:
        cfg['deepseek_api_key'] = env_key
    return cfg


def get_secret_key():
    """Flask secret_key + LLM Key 加密派生密钥，保持一致"""
    return os.environ.get('DANCE_SECRET', 'dance-coach-secret-2026-verify-works-001')
