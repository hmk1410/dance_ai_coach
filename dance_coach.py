# -*- coding: utf-8 -*-
"""
dance_coach.py
AI舞蹈教练：调用 OpenAI 兼容接口（DeepSeek 等）实现智能问答，未配置时使用内置免费答疑引擎兜底。

配置方式（优先级：用户 Key > config.json 全局 > 内置引擎）：
  1) 网页端「账号与系统 → 大模型配置」填写自己的 API Key（加密存储，优先生效）
  2) 或编辑项目根目录的 config.json，填入 "deepseek_api_key"（全局生效）
  3) 都不配置时，自动使用内置免费答疑引擎回答舞蹈问题
"""

import json
import os
import re
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


def resolve_llm_config(user_llm=None):
    """
    解析当前有效的 LLM 配置。优先级：用户自己的 Key > config.json 全局。

    返回 (dict|None, source)：
      - user_llm 传 {'api_key':..,'base_url':..,'model':..} 且有 key → (该配置, 'user')
      - config.json / 环境变量有全局 key → (全局配置, 'global')
      - 都没有 → (None, 'none')，由调用方走内置引擎兜底
    """
    if user_llm and user_llm.get('api_key'):
        cfg = {
            'api_key': user_llm['api_key'],
            'base_url': user_llm.get('base_url') or DEFAULT_CONFIG['deepseek_base_url'],
            'model': user_llm.get('model') or DEFAULT_CONFIG['deepseek_model'],
        }
        return cfg, 'user'
    g = load_config()
    if g.get('deepseek_api_key'):
        return {
            'api_key': g['deepseek_api_key'],
            'base_url': g['deepseek_base_url'],
            'model': g['deepseek_model'],
        }, 'global'
    return None, 'none'


def is_configured():
    """是否已配置任意 API Key（用户或全局）"""
    cfg, src = resolve_llm_config()
    return src in ('user', 'global')


def ask_dance_coach(user_message, history=None, context='', user_llm=None, timeout=60):
    """
    调用大模型问答。返回 (回答文本, None) 或 (None, 错误信息字符串)。

    user_message: 用户的问题
    history:     历史消息 [{'role': 'user'|'assistant', 'content': '...'}, ...]
    context:     当前练习背景（如当前标准视频名），非必填
    user_llm:    用户自己的 LLM 配置 {'api_key','base_url','model'}，优先于全局配置
    """
    cfg, src = resolve_llm_config(user_llm)
    if cfg is None:
        # 无任何 Key：使用内置免费答疑引擎兜底
        return builtin_coach_answer(user_message, context=context), None

    g = load_config()
    system_prompt = g['coach_system_prompt']
    if context:
        system_prompt += f"\n用户当前正在练习：{context}。"

    messages = [{'role': 'system', 'content': system_prompt}]
    for m in (history or [])[-20:]:
        if m.get('role') in ('user', 'assistant') and m.get('content'):
            messages.append({'role': m['role'], 'content': m['content']})
    messages.append({'role': 'user', 'content': user_message})

    url = cfg['base_url'].rstrip('/') + '/chat/completions'
    payload = json.dumps({
        'model': cfg['model'],
        'messages': messages,
        'temperature': 0.7,
        'max_tokens': 800,
    }).encode('utf-8')

    req = urllib.request.Request(url, data=payload, headers={
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + cfg['api_key'],
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


# ========== 内置免费答疑引擎 ==========

BUILTIN_KB = [
    {
        'keys': ['山膀', '提腕', '沉肩', '开肩', '圆润', '手位', '手型', '压腕', '按掌', '兰花指'],
        'title': '山膀手位要领',
        'answer': (
            '山膀是古典舞最基础的手位，要领如下：\n'
            '1. 站姿：双脚小八字步，立腰拔背，头顶虚拎，目视前方。\n'
            '2. 手臂：两臂侧平举呈弧线，肘部微沉不僵直，肩要下沉（沉肩），不要耸肩。\n'
            '3. 手腕：提腕时指尖向上、手腕上提；压腕时掌心向下、手腕下压；手腕要圆润连贯。\n'
            '4. 手型：多用兰花指或单指，指根发力、指尖延伸，不要散架。\n'
            '练习建议：面对镜子对照「舞镜·智芯」的姿态分析，重点看双肩是否对称、手臂是否圆润水平。'
        )
    },
    {
        'keys': ['站姿', '体态', '立腰', '拔背', '含胸', '驼背', '塌腰', '挺拔', '身体姿态'],
        'title': '站姿与体态矫正',
        'answer': (
            '舞蹈站姿的核心理念是「立腰拔背、头顶虚拎」：\n'
            '1. 脊柱：想象头顶有根线向上提，脊柱拉长，不塌腰、不含胸、不驼背。\n'
            '2. 肩膀：双肩平正下沉，保持对称，不要一高一低。\n'
            '3. 重心：重心均匀落在双脚，膝盖放松不锁死，脚趾抓地。\n'
            '4. 日常：可每天靠墙站立 5~10 分钟，后脑勺、肩胛、臀、脚跟贴墙。\n'
            '借助「舞镜·智芯」的脊柱垂直度与双肩对称评分，可随时自查姿态。'
        )
    },
    {
        'keys': ['下腰', '前腰', '软度', '柔韧', '压腿', '劈叉', '开胯', '拉伸', '拉筋'],
        'title': '柔韧与软开训练',
        'answer': (
            '软开度训练必须循序渐进、防止受伤：\n'
            '1. 热身：先慢跑或跳跃 5 分钟，让身体热起来再压。\n'
            '2. 压腿：正压/旁压/后压交替，每条腿 30 秒×3 组，膝盖伸直、脚尖回勾。\n'
            '3. 劈叉：循序渐进用毛巾或瑜伽砖辅助，不要硬撑，以「微疼不刺痛」为度。\n'
            '4. 下腰：先学小腰（站立下后腰），再尝试跪下腰，最后才做站立下腰，必须有同伴保护。\n'
            '5. 放松：压完要踢腿、抖腿放松，避免韧带拉伤。\n'
            '记住：软度是「日积月累」，每天坚持 10 分钟比一周猛练一次更有效。'
        )
    },
    {
        'keys': ['转', '旋转', '平转', '原地转', '重心', '留头', '甩头', '眩晕', '头晕'],
        'title': '旋转技巧',
        'answer': (
            '旋转（平转/原地转）的核心是「留头甩头」和「重心」：\n'
            '1. 留头甩头：转动时眼睛盯住一个点，头尽量留到最后再迅速甩过去，可缓解眩晕。\n'
            '2. 重心：身体垂直，重心放在主力腿上，动力腿擦地推地发力。\n'
            '3. 手臂：旋转时手臂保持弧形收紧，形成向心力。\n'
            '4. 脚：落地要立半脚尖，脚踝稳定，避免内外翻。\n'
            '训练建议：先原地半脚尖站立练平衡 30 秒，再练单转，最后串平转。每日少量多次，防头晕。'
        )
    },
    {
        'keys': ['跳', '大跳', '小跳', '弹跳', '跳跃', '落地', '脚踝'],
        'title': '跳跃技巧',
        'answer': (
            '跳跃动作（小跳/大跳）的关键：\n'
            '1. 起跳：先屈膝蓄力，脚掌推地，发力瞬间绷直膝盖。\n'
            '2. 空中：身体收紧上提，手臂带动，腿部尽量展开（大跳需控腿）。\n'
            '3. 落地：先脚掌后脚跟，屈膝缓冲，避免膝盖与脚踝受伤。\n'
            '4. 训练：先练原地小跳找弹性，再练组合；注意每次落地要轻、稳、静。'
        )
    },
    {
        'keys': ['热身', '放松', '整理', '运动前后', '准备活动', '冷身'],
        'title': '热身与放松',
        'answer': (
            '正确的热身与放松能显著降低受伤风险：\n'
            '1. 热身（练前 5~10 分钟）：先活动关节（颈肩腰髋膝踝），再做动态拉伸如弓步压腿、摆臂。\n'
            '2. 正式训练：从慢到快、从简单到复杂，逐步加量。\n'
            '3. 放松（练后 5~10 分钟）：静态拉伸每个动作保持 20~30 秒，配合深呼吸。\n'
            '4. 补水：运动间隙少量多次补充水分。\n'
            '建议每天练舞都养成「热身-训练-放松」的完整习惯。'
        )
    },
    {
        'keys': ['受伤', '扭伤', '拉伤', '疼', '疼痛', '膝盖', '脚踝', '腰', '踝', '应急'],
        'title': '运动损伤预防与处理',
        'answer': (
            '舞蹈常见损伤的处理原则（RICE 原则）：\n'
            '1. Rest 休息：立即停止训练，避免继续受力。\n'
            '2. Ice 冰敷：前 48 小时每 2~3 小时冰敷 15~20 分钟，减轻肿胀。\n'
            '3. Compression 加压：用弹性绷带包扎，松紧适度。\n'
            '4. Elevation 抬高：把伤肢抬高到心脏以上，帮助消肿。\n'
            '重要提示：如果是剧烈疼痛、畸形、无法承重，请立即就医，不要自行处理。\n'
            '日常预防：充分热身、循序渐进、控制训练量、加强核心与脚踝力量。'
        )
    },
    {
        'keys': ['呼吸', '气息', '发力', '核心', '收腹', '力量', '稳定'],
        'title': '发力与核心',
        'answer': (
            '舞蹈发力讲究「以气带形、核心稳定」：\n'
            '1. 呼吸：动作配合呼吸，发力时呼气、延伸时吸气，不要憋气。\n'
            '2. 核心：训练时保持腹部微收、肋骨下沉，核心收紧可保护腰椎并提升稳定。\n'
            '3. 发力：动作从腰胯带动四肢，讲究「由内而外」，不要只用手臂蛮力。\n'
            '4. 训练：多做平板支撑、仰卧卷腹、臀桥等核心练习，每周 2~3 次。'
        )
    },
    {
        'keys': ['古典舞', '身韵', '神韵', '提沉', '冲靠', '含腆'],
        'title': '古典舞身韵',
        'answer': (
            '古典舞的灵魂在「身韵」：\n'
            '1. 提沉：以气息带动，吸气时胸腰上提、呼气时下沉，是一切身韵的基础。\n'
            '2. 冲靠：上身向侧前冲、侧后靠，配合胯部形成拧倾的韵律。\n'
            '3. 含腆：含胸与腆胸的交替，体现含蓄与舒展的对比。\n'
            '4. 练习：先练「提沉呼吸」，再练「云手」「摇臂」等单一元素，最后组合成套。\n'
            '身韵讲究「形神兼备」，建议结合「舞镜·智芯」的对称性反馈慢慢打磨。'
        )
    },
    {
        'keys': ['协调', '节奏', '卡点', '跟不上', '记不住', '笨手', '顺序'],
        'title': '协调与记动作',
        'answer': (
            '协调性差、记不住动作很常见，可以这样练：\n'
            '1. 拆解：把一段舞拆成 4~8 拍的小段，先上肢再下肢，最后合起来。\n'
            '2. 慢速：用 0.5~0.75 倍速跟练，熟练后再回正常速度。\n'
            '3. 卡点：先数拍子（口令节拍），找到每个动作对应的重拍。\n'
            '4. 重复：每天 3~5 遍连续记忆，睡前一晚更容易记住。\n'
            '5. 对照：用「舞镜·智芯」并排对比功能，一段段跟着标准视频练。'
        )
    },
]


def _match_builtin(message, context=''):
    """内置引擎：关键词匹配返回知识库答案，返回 (标题, 答案) 或 None"""
    text = (message or '') + ' ' + (context or '')
    best = None
    for item in BUILTIN_KB:
        for k in item['keys']:
            if k in text:
                return item['title'], item['answer']
    return best


def builtin_coach_answer(message, context=''):
    """
    内置免费答疑引擎：基于本地知识库的规则回答。
    命中关键词返回对应内容；未命中则给出引导建议。
    """
    hit = _match_builtin(message, context)
    if hit:
        title, answer = hit
        return f'【{title}】\n{answer}'

    # 兜底：未命中关键词时给出引导
    return (
        '当前未配置大模型 API Key，使用的是内置免费答疑引擎。\n'
        '我可以解答这些舞蹈问题：\n'
        '• 山膀手位、站姿体态、身韵气息\n'
        '• 软开度训练（压腿、劈叉、下腰）\n'
        '• 旋转、跳跃、协调记动作\n'
        '• 热身放松、运动损伤预防\n'
        '如果你想获得更丰富、更针对性的回答，可以在「账号与系统 → 大模型配置」'
        '填写自己的 API Key（DeepSeek 等，兼容 OpenAI 接口）。'
    )
