# dance_features.py
"""
从MediaPipe 33个关键点 → 提取舞蹈专用特征
"""

import numpy as np
import math


class DanceFeatureExtractor:
    """舞蹈特征提取器"""
    
    # 关键点索引映射
    LANDMARKS = {
        'nose': 0,
        'left_shoulder': 11, 'right_shoulder': 12,
        'left_elbow': 13, 'right_elbow': 14,
        'left_wrist': 15, 'right_wrist': 16,
        'left_hip': 23, 'right_hip': 24,
        'left_knee': 25, 'right_knee': 26,
        'left_ankle': 27, 'right_ankle': 28,
    }
    
    @staticmethod
    def calculate_angle(a, b, c):
        """计算三点夹角（b为顶点）"""
        ba = np.array(a) - np.array(b)
        bc = np.array(c) - np.array(b)
        
        cosine = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
        cosine = np.clip(cosine, -1.0, 1.0)
        angle = np.degrees(np.arccos(cosine))
        return angle
    
    @classmethod
    def extract_shan_bang_features(cls, landmarks):
        """
        提取"山膀"手位的关键特征
        landmarks: MediaPipe的33个关键点列表
        """
        # 获取坐标
        def get_point(name):
            idx = cls.LANDMARKS[name]
            lm = landmarks[idx]
            return [lm.x, lm.y]
        
        ls = get_point('left_shoulder')
        rs = get_point('right_shoulder')
        le = get_point('left_elbow')
        re = get_point('right_elbow')
        lw = get_point('left_wrist')
        rw = get_point('right_wrist')
        lh = get_point('left_hip')
        rh = get_point('right_hip')
        
        # ========== 计算舞蹈专用角度 ==========
        
        # 1. 肩外展角（手臂与躯干垂直线的夹角）
        # 躯干垂直参考：肩正下方
        torso_left = [ls[0], ls[1] + 0.1]
        torso_right = [rs[0], rs[1] + 0.1]
        
        left_abduction = cls.calculate_angle(torso_left, ls, le)
        right_abduction = cls.calculate_angle(torso_right, rs, re)
        
        # 2. 肘伸展角（180°为完全伸直）
        left_elbow = cls.calculate_angle(ls, le, lw)
        right_elbow = cls.calculate_angle(rs, re, rw)
        
        # 3. 脊柱垂直度
        shoulder_mid = [(ls[0]+rs[0])/2, (ls[1]+rs[1])/2]
        hip_mid = [(lh[0]+rh[0])/2, (lh[1]+rh[1])/2]
        vertical_ref = [shoulder_mid[0], shoulder_mid[1] + 0.1]
        spine_vertical = 180 - cls.calculate_angle(vertical_ref, shoulder_mid, hip_mid)
        
        # 4. 左右对称性（肩高差、肘高差）
        shoulder_diff = abs(ls[1] - rs[1]) * 100  # 归一化坐标转百分比
        elbow_diff = abs(le[1] - re[1]) * 100
        
        # 5. 手臂水平度（山膀要求手臂水平）
        left_arm_level = abs(le[1] - ls[1]) * 100  # 肘与肩的垂直偏差
        right_arm_level = abs(re[1] - rs[1]) * 100
        
        return {
            'left_shoulder_abduction': round(left_abduction, 1),
            'right_shoulder_abduction': round(right_abduction, 1),
            'left_elbow_extension': round(left_elbow, 1),
            'right_elbow_extension': round(right_elbow, 1),
            'spine_vertical': round(spine_vertical, 1),
            'shoulder_symmetry': round(shoulder_diff, 1),
            'elbow_symmetry': round(elbow_diff, 1),
            'left_arm_level': round(left_arm_level, 1),
            'right_arm_level': round(right_arm_level, 1),
        }
    
    @classmethod
    def extract_an_zhang_features(cls, landmarks):
        """
        提取"按掌"手位的关键特征
        （与山膀不同的角度重点）
        """
        # 按掌：肩内收、肘弯曲、掌心向下
        # 实现类似，角度标准不同
        pass  # 可扩展