# dance_standards.py
"""
舞蹈动作标准库：定义每个动作的"正确姿态"
"""

# 山膀标准（由舞蹈老师录制提取）
SHAN_BANG_STANDARD = {
    'name': '山膀',
    'category': '基本手位',
    'description': '双臂侧平举，与肩同高，肘微屈',
    
    # 各指标的标准值和容忍范围
    'metrics': {
        'left_shoulder_abduction': {
            'standard': 90.0,      # 标准值
            'tolerance': 5.0,    # 允许偏差±5°
            'weight': 1.2,       # 权重（重要性）
            'name': '左肩外展',
            'unit': '度'
        },
        'right_shoulder_abduction': {
            'standard': 90.0,
            'tolerance': 5.0,
            'weight': 1.2,
            'name': '右肩外展',
            'unit': '度'
        },
        'left_elbow_extension': {
            'standard': 175.0,    # 接近伸直
            'tolerance': 5.0,
            'weight': 1.0,
            'name': '左肘伸展',
            'unit': '度'
        },
        'right_elbow_extension': {
            'standard': 175.0,
            'tolerance': 5.0,
            'weight': 1.0,
            'name': '右肘伸展',
            'unit': '度'
        },
        'spine_vertical': {
            'standard': 178.0,    # 完全垂直（竖直≈180°）
            'tolerance': 3.0,     # 要求更严格
            'weight': 1.5,       # 最重要
            'name': '脊柱垂直度',
            'unit': '度'
        },
        'shoulder_symmetry': {
            'standard': 0.0,      # 完全对称
            'tolerance': 3.0,     # 允许3%偏差
            'weight': 1.3,
            'name': '双肩对称',
            'unit': '%'
        },
        'left_arm_level': {
            'standard': 0.0,      # 完全水平
            'tolerance': 5.0,
            'weight': 0.8,
            'name': '左臂水平度',
            'unit': '%'
        },
    },
    
    # 综合评分阈值
    'scoring': {
        'excellent': 90,   # ≥90分：优秀
        'good': 75,        # ≥75分：良好
        'pass': 60,        # ≥60分：及格
    }
}


# 按掌标准（另一个动作）
AN_ZHANG_STANDARD = {
    'name': '按掌',
    'category': '基本手位',
    'description': '手臂前伸，掌心向下按',
    
    'metrics': {
        'left_shoulder_flexion': {  # 注意：不是外展，是前屈！
            'standard': 45.0,
            'tolerance': 5.0,
            'weight': 1.2,
            'name': '左肩前屈',
            'unit': '度'
        },
        'left_elbow_extension': {
            'standard': 160.0,    # 按掌肘比山膀更屈
            'tolerance': 5.0,
            'weight': 1.0,
            'name': '左肘伸展',
            'unit': '度'
        },
        # ... 其他指标
    }
}


# 动作库注册表
ACTION_STANDARDS = {
    'shan_bang': SHAN_BANG_STANDARD,
    'an_zhang': AN_ZHANG_STANDARD,
    # 可扩展更多动作
}