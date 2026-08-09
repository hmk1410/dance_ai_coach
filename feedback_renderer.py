# feedback_renderer.py
"""
反馈渲染：把评分结果 → 可视化 + 语音
"""

class FeedbackRenderer:
    """反馈渲染器"""
    
    def __init__(self):
        self.last_spoken = ''
        self.speak_cooldown = 3  # 秒
    
    def render_frame(self, image, landmarks, score_result):
        """
        在视频帧上绘制反馈信息
        """
        h, w = image.shape[:2]
        
        # 1. 绘制骨骼（MediaPipe默认）
        # ...（已有）
        
        # 2. 绘制问题部位高亮
        for detail in score_result['details']:
            if detail['level'] in ['warning', 'error']:
                self._highlight_problem(image, landmarks, detail)
        
        # 3. 绘制信息面板
        self._draw_info_panel(image, score_result)
        
        # 4. 绘制标准参考线（山膀专用）
        if score_result['action_name'] == '山膀':
            self._draw_shan_bang_guide(image, h, w)
        
        return image
    
    def _highlight_problem(self, image, landmarks, detail):
        """高亮显示问题部位"""
        # 根据指标名确定关键点
        key_to_points = {
            'left_shoulder_abduction': [11, 13],
            'right_shoulder_abduction': [12, 14],
            'left_elbow_extension': [11, 13, 15],
            'spine_vertical': [11, 12, 23, 24],
        }
        
        points = key_to_points.get(detail['metric_key'], [])
        for idx in points:
            lm = landmarks[idx]
            x, y = int(lm.x * image.shape[1]), int(lm.y * image.shape[0])
            cv2.circle(image, (x, y), 10, (0, 0, 255), -1)  # 红色高亮
    
    def _draw_info_panel(self, image, result):
        """绘制左上角信息面板"""
        h, w = image.shape[:2]
        
        # 半透明背景
        overlay = image.copy()
        cv2.rectangle(overlay, (10, 10), (400, 200), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, image, 0.3, 0, image)
        
        # 综合评分（大数字）
        score = result['overall_score']
        color = (0, 255, 0) if score >= 80 else (0, 255, 255) if score >= 60 else (0, 0, 255)
        cv2.putText(image, f"{score}", (30, 80), 
                   cv2.FONT_HERSHEY_SIMPLEX, 2.5, color, 3)
        cv2.putText(image, "分", (120, 80), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        # 动作名称和评语
        cv2.putText(image, f"【{result['action_name']}】", (30, 120),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(image, result['summary'][:20], (30, 155),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        
        # 显示前3个问题
        y = 185
        problems = [d for d in result['details'] if d['level'] in ['warning', 'error']][:3]
        for p in problems:
            text = f"· {p['name']}: {p['actual']}° (标准{p['standard']}°)"
            cv2.putText(image, text, (30, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            y += 25
    
    def _draw_shan_bang_guide(self, image, h, w):
        """绘制山膀参考线"""
        center_y = h // 2
        center_x = w // 2
        
        # 水平肩线（半透明绿色虚线）
        overlay = image.copy()
        for x in range(0, w, 20):
            cv2.line(overlay, (x, center_y), (x+10, center_y), 
                    (0, 255, 0), 2)
        cv2.addWeighted(overlay, 0.3, image, 0.7, 0, image)
        
        # 标注文字
        cv2.putText(image, "标准肩线", (w-100, center_y-10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    
    def speak(self, text):
        """语音播报（带冷却，避免重复）"""
        import time
        current_time = time.time()
        
        if text == self.last_spoken:
            return
        
        # 使用Web Speech API或pyttsx3
        # 实际实现略...
        
        self.last_spoken = text