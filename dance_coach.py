"""
dance_coach.py
AI舞蹈教练：调用 DeepSeek（OpenAI 兼容接口）实现智能问答。

如何配置 API Key（二选一）：
  1) 编辑项目根目录的 config.json，把 "deepseek_api_key" 留空处填入你的
     DeepSeek API Key（例如 sk-xxxxx）
  2) 或在启动服务前设置环境变量：DEEPSEEK_API_KEY=sk-xxxxx
之后重启服务即可在网页「🤖 舞蹈教练」页面使用。
"""

import json
import os
import urllib.request
import urllib.error

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')

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


def is_configured():
    """是否已配置 API Key"""
    return bool(load_config().get('deepseek_api_key'))


def ask_dance_coach(user_message, history=None, context='', timeout=60):
    """
    调用 DeepSeek 问答。

    user_message: 用户的问题
    history:     历史消息 [{'role': 'user'|'assistant', 'content': '...'}, ...]
    context:     当前练习背景（如当前模板名称），非必填，会附加给模型

    返回: (回答文本, None) 或 (None, 错误信息字符串)
    """
    cfg = load_config()
    api_key = cfg.get('deepseek_api_key')
    if not api_key:
        return None, ('尚未配置 DeepSeek API Key。请编辑项目根目录的 config.json，'
                      '在 "deepseek_api_key" 中填入你的 Key 后重启服务。')

    system_prompt = cfg['coach_system_prompt']
    if context:
        system_prompt += f"\n用户当前正在练习：{context}。"

    messages = [{'role': 'system', 'content': system_prompt}]
    for m in (history or [])[-20:]:
        if m.get('role') in ('user', 'assistant') and m.get('content'):
            messages.append({'role': m['role'], 'content': m['content']})
    messages.append({'role': 'user', 'content': user_message})

    url = cfg['deepseek_base_url'].rstrip('/') + '/chat/completions'
    payload = json.dumps({
        'model': cfg['deepseek_model'],
        'messages': messages,
        'temperature': 0.7,
        'max_tokens': 800,
    }).encode('utf-8')

    req = urllib.request.Request(url, data=payload, headers={
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + api_key,
    })

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        content = data['choices'][0]['message']['content']
        return content, None
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return None, f'API 请求失败 (HTTP {e.code})：{body[:200]}'
    except urllib.error.URLError as e:
        return None, f'网络错误：{e.reason}'
    except Exception as e:
        return None, f'请求异常：{e}'
