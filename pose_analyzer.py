"""
姿态分析模块：封装MediaPipe检测和舞蹈动作分析
"""

import cv2
import mediapipe as mp
import numpy as np
import math


class PoseAnalyzer:
    def __init__(self):
        # MediaPipe Pose初始化
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,      # 视频流模式（连续帧，更快）
            model_complexity=1,           # 复杂度：0轻量/1标准/2重型
            smooth_landmarks=True,        # 平滑关键点，减少抖动
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        
        # 关键点名称映射（33个关键点）
        self.LANDMARK_NAMES = {
            0: 'nose',
            11: 'left_shoulder', 12: 'right_shoulder',
            13: 'left_elbow', 14: 'right_elbow',
            15: 'left_wrist', 16: 'right_wrist',
            23: 'left_hip', 24: 'right_hip',
            25: 'left_knee', 26: 'right_knee',
            27: 'left_ankle', 28: 'right_ankle',
        }
        
        # 标准动作模板（示例：古典舞"山膀"手位）
        # 格式：{关节名: (最小角度, 标准角度, 最大角度)}
        self.TEMPLATES = {
            'shan_bang': {  # 山膀
                'left_shoulder_abduction': (85, 90, 95),   # 左肩外展
                'right_shoulder_abduction': (85, 90, 95),  # 右肩外展
                'left_elbow_extension': (160, 180, 180),   # 左肘伸直
                'right_elbow_extension': (160, 180, 180), # 右肘伸直
                'spine_vertical': (170, 178, 180),         # 脊柱垂直（竖直≈180°）
            },
            'stand': {  # 基本站姿
                'spine_vertical': (170, 178, 180),
                'left_knee_extension': (170, 180, 180),
                'right_knee_extension': (170, 180, 180),
                'hip_width': (0.8, 1.0, 1.2),  # 髋宽与肩宽比
            }
        }
        
        self.current_template = 'stand'  # 默认站姿
        self.feedback_history = []       # 反馈历史
        self.external_template = None    # 来自视频的外部标准模板
        
    def calculate_angle(self, a, b, c):
        """
        计算三点形成的角度（b为顶点）
        a, b, c: [x, y] 坐标
        返回: 角度（度）
        """
        a = np.array(a)
        b = np.array(b)
        c = np.array(c)
        
        ba = a - b
        bc = c - b
        
        # 计算夹角
        cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
        cosine_angle = np.clip(cosine_angle, -1.0, 1.0)  # 防止数值误差
        angle = np.degrees(np.arccos(cosine_angle))
        
        return angle
    
    def get_landmark_coords(self, landmarks, idx):
        """获取指定关键点的坐标 [x, y]（归一化转像素）"""
        lm = landmarks.landmark[idx]
        return [lm.x, lm.y]
    
    def analyze_pose(self, landmarks, image_shape):
        """
        分析姿态，计算各项角度指标
        返回: dict，包含所有计算出的角度和偏差
        """
        h, w = image_shape[:2]
        results = {}
        
        # ========== 1. 提取关键点坐标 ==========
        # 肩部
        ls = self.get_landmark_coords(landmarks, 11)  # 左肩
        rs = self.get_landmark_coords(landmarks, 12)  # 右肩
        # 肘部
        le = self.get_landmark_coords(landmarks, 13)  # 左肘
        re = self.get_landmark_coords(landmarks, 14)  # 右肘
        # 腕部
        lw = self.get_landmark_coords(landmarks, 15)  # 左腕
        rw = self.get_landmark_coords(landmarks, 16)  # 右腕
        # 髋部
        lh = self.get_landmark_coords(landmarks, 23)  # 左髋
        rh = self.get_landmark_coords(landmarks, 24)  # 右髋
        # 膝部
        lk = self.get_landmark_coords(landmarks, 25)  # 左膝
        rk = self.get_landmark_coords(landmarks, 26)  # 右膝
        # 踝部
        la = self.get_landmark_coords(landmarks, 27)  # 左踝
        ra = self.get_landmark_coords(landmarks, 28)  # 右踝
        # 鼻/眼（用于头部参考）
        nose = self.get_landmark_coords(landmarks, 0)
        
        # ========== 2. 计算关键角度 ==========
        
        # 肩外展角（手臂与躯干的角度）
        # 使用肩-髋垂直线作为参考
        torso_left = [ls[0], ls[1] + 0.1]  # 假想的下方点
        torso_right = [rs[0], rs[1] + 0.1]
        
        results['left_shoulder_abduction'] = self.calculate_angle(torso_left, ls, le)
        results['right_shoulder_abduction'] = self.calculate_angle(torso_right, rs, re)
        
        # 肘伸展角（180度为完全伸直）
        results['left_elbow_extension'] = self.calculate_angle(ls, le, lw)
        results['right_elbow_extension'] = self.calculate_angle(rs, re, rw)
        
        # 脊柱垂直度（肩中点到髋中点的连线与垂直线的夹角）
        shoulder_mid = [(ls[0]+rs[0])/2, (ls[1]+rs[1])/2]
        hip_mid = [(lh[0]+rh[0])/2, (lh[1]+rh[1])/2]
        vertical_ref = [shoulder_mid[0], shoulder_mid[1] + 0.1]
        results['spine_vertical'] = 180 - self.calculate_angle(vertical_ref, shoulder_mid, hip_mid)
        
        # 膝伸展角
        results['left_knee_extension'] = self.calculate_angle(lh, lk, la)
        results['right_knee_extension'] = self.calculate_angle(rh, rk, ra)
        
        # 髋宽比（髋宽 / 肩宽，评估下肢开度）
        shoulder_width = math.dist(ls, rs)
        hip_width = math.dist(lh, rh)
        results['hip_width'] = hip_width / (shoulder_width + 1e-6)
        
        # 左右对称性与手臂水平度（用于视频标准对比）
        results['shoulder_symmetry'] = abs(ls[1] - rs[1]) * 100
        results['elbow_symmetry'] = abs(le[1] - re[1]) * 100
        results['left_arm_level'] = abs(le[1] - ls[1]) * 100
        results['right_arm_level'] = abs(re[1] - rs[1]) * 100
        
        # ========== 3. 与标准模板对比，生成反馈 ==========
        template = self.external_template if self.external_template is not None else self.TEMPLATES.get(self.current_template, {})
        feedback = []
        
        for key, (min_val, std_val, max_val) in template.items():
            if key in results:
                actual = results[key]
                deviation = abs(actual - std_val)
                
                # 判断等级
                if actual < min_val or actual > max_val:
                    level = 'error'      # 严重偏差
                elif deviation > (max_val - min_val) * 0.5:
                    level = 'warning'    # 轻微偏差
                else:
                    level = 'good'       # 合格
                
                feedback.append({
                    'name': key,
                    'actual': round(actual, 1),
                    'standard': std_val,
                    'deviation': round(deviation, 1),
                    'level': level
                })
        
        results['feedback'] = feedback
        results['overall_score'] = self._calculate_score(feedback)
        
        return results
    
    def _calculate_score(self, feedback):
        """计算综合评分（0-100）"""
        if not feedback:
            return 0
        good_count = sum(1 for f in feedback if f['level'] == 'good')
        return int((good_count / len(feedback)) * 100)
    
    def draw_analysis(self, image, landmarks, analysis_results):
        """
        在图像上绘制分析结果
        返回: 标注后的图像
        """
        h, w = image.shape[:2]
        
        # 1. 绘制MediaPipe默认骨骼（可选）
        self.mp_drawing.draw_landmarks(
            image,
            landmarks,
            self.mp_pose.POSE_CONNECTIONS,
            landmark_drawing_spec=self.mp_drawing_styles.get_default_pose_landmarks_style()
        )
        
        # 2. 绘制自定义标注
        feedback = analysis_results.get('feedback', [])
        
        for item in feedback:
            name = item['name']
            actual = item['actual']
            deviation = item['deviation']
            level = item['level']
            
            # 根据偏差等级选择颜色
            if level == 'good':
                color = (0, 255, 0)      # 绿色
            elif level == 'warning':
                color = (0, 255, 255)    # 黄色
            else:
                color = (0, 0, 255)      # 红色
            
            # 在对应位置绘制文字（简化：统一显示在左上角）
            # 实际项目中应根据关节位置就近显示
        
        # 3. 绘制综合信息面板
        self._draw_info_panel(image, analysis_results)
        
        return image
    
    def _draw_info_panel(self, image, results):
        """绘制左上角信息面板"""
        h, w = image.shape[:2]
        
        # 半透明背景
        overlay = image.copy()
        cv2.rectangle(overlay, (10, 10), (350, 180), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, image, 0.4, 0, image)
        
        # 文字信息
        score = results.get('overall_score', 0)
        color = (0, 255, 0) if score >= 80 else (0, 255, 255) if score >= 60 else (0, 0, 255)
        
        cv2.putText(image, f"Score: {score}", (20, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 2)
        cv2.putText(image, f"Template: {self.current_template}", (20, 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # 显示主要偏差
        y_offset = 130
        for item in results.get('feedback', [])[:3]:  # 只显示前3个
            text = f"{item['name']}: {item['actual']}° (±{item['deviation']}°)"
            cv2.putText(image, text, (20, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, 
                       (0, 255, 0) if item['level'] == 'good' else (0, 0, 255), 1)
            y_offset += 30
    
    def process_frame(self, frame):
        """
        处理单帧图像：检测+分析+标注
        返回: (标注后的图像, 分析结果字典)
        """
        # RGB转换（MediaPipe需要RGB）
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb_frame)
        
        analysis = {}
        
        if results.pose_landmarks:
            # 有检测到人体
            analysis = self.analyze_pose(results.pose_landmarks, frame.shape)
            frame = self.draw_analysis(frame, results.pose_landmarks, analysis)
        else:
            # 未检测到人体
            cv2.putText(frame, "No person detected", (50, 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        return frame, analysis
    
    def set_template(self, template_name):
        """切换标准动作模板（内置模板）"""
        self.external_template = None
        if template_name in self.TEMPLATES:
            self.current_template = template_name
            return True
        return False

    def set_external_template(self, name, metrics):
        """设置来自视频的外部标准模板
        metrics: {指标名: (最小, 标准, 最大)}
        """
        self.external_template = metrics
        self.current_template = name
    
    def release(self):
        """释放资源"""
        self.pose.close()