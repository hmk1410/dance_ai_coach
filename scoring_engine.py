# scoring_engine.py
"""
评分引擎：用户动作 vs 标准模板 → 得分 + 偏差 + 建议
"""

class DanceScoringEngine:
    """舞蹈评分引擎"""
    
    def __init__(self, standard):
        self.standard = standard
    
    def score(self, user_features):
        """
        评分主函数
        user_features: 从用户视频提取的特征字典
        返回：完整评分结果
        """
        metrics = self.standard['metrics']
        details = []
        total_weight = 0
        weighted_score = 0
        
        for key, config in metrics.items():
            if key not in user_features:
                continue
            
            actual = user_features[key]
            std = config['standard']
            tol = config['tolerance']
            weight = config['weight']
            
            # 计算偏差
            deviation = abs(actual - std)
            
            # 计算单项得分（0~100）
            if deviation <= tol * 0.3:
                # 偏差在30%容忍范围内：优秀
                score = 95 + min(5, (tol * 0.3 - deviation) * 2)
                level = 'excellent'
            elif deviation <= tol * 0.6:
                score = 80 + min(15, (tol * 0.6 - deviation) * 3)
                level = 'good'
            elif deviation <= tol:
                score = 60 + min(20, (tol - deviation) * 4)
                level = 'warning'
            else:
                # 超出容忍范围：不及格
                score = max(0, 60 - (deviation - tol) * 2)
                level = 'error'
            
            total_weight += weight
            weighted_score += score * weight
            
            # 生成具体建议
            suggestion = self._generate_suggestion(
                config['name'], actual, std, deviation, level
            )
            
            details.append({
                'metric_key': key,
                'name': config['name'],
                'actual': round(actual, 1),
                'standard': std,
                'deviation': round(deviation, 1),
                'tolerance': tol,
                'score': round(score, 1),
                'level': level,
                'weight': weight,
                'suggestion': suggestion,
                'unit': config['unit']
            })
        
        # 综合得分
        overall = weighted_score / total_weight if total_weight > 0 else 0
        
        # 确定综合等级
        thresholds = self.standard['scoring']
        if overall >= thresholds['excellent']:
            overall_level = 'excellent'
        elif overall >= thresholds['good']:
            overall_level = 'good'
        elif overall >= thresholds['pass']:
            overall_level = 'pass'
        else:
            overall_level = 'fail'
        
        # 找出最严重的问题（用于语音优先播报）
        worst = min(details, key=lambda x: x['score']) if details else None
        
        return {
            'action_name': self.standard['name'],
            'overall_score': round(overall, 1),
            'overall_level': overall_level,
            'details': details,
            'worst_problem': worst,
            'summary': self._generate_summary(overall, worst)
        }
    
    def _generate_suggestion(self, name, actual, standard, deviation, level):
        """生成人话建议"""
        if level == 'excellent':
            return f'{name}完美'
        
        direction = '偏大' if actual > standard else '偏小'
        
        # 舞蹈术语映射
        suggestions = {
            '左肩外展': {
                '偏大': '左臂过高，请下沉至肩平',
                '偏小': '左臂下沉不足，请再抬高与肩平'
            },
            '右肩外展': {
                '偏大': '右臂过高，请下沉',
                '偏小': '右臂下沉不足，请抬高'
            },
            '左肘伸展': {
                '偏大': '左肘过直，请微屈（山膀肘微屈）',
                '偏小': '左肘弯曲过大，请伸直'
            },
            '脊柱垂直度': {
                '偏大': '身体前倾，请立腰拔背',
                '偏小': '身体后仰，请收腹微含胸'
            },
            '双肩对称': {
                '偏大': '双肩不平，请调整至同一高度',
                '偏小': '双肩不平，请调整至同一高度'
            },
            '左臂水平度': {
                '偏大': '左臂上抬，请放平',
                '偏小': '左臂下沉，请抬平'
            }
        }
        
        return suggestions.get(name, {}).get(
            direction, 
            f'{name}{direction}，当前{actual}，标准{standard}'
        )
    
    def _generate_summary(self, score, worst):
        """生成综合评语"""
        if score >= 90:
            return '优秀！山膀手位规范，请保持'
        elif score >= 80:
            return '良好，轻微调整即可完美'
        elif score >= 70:
            return f'需改进：{worst["suggestion"]}' if worst else '需改进'
        elif score >= 60:
            return f'问题较大：{worst["suggestion"]}，建议对照示范视频'
        else:
            return f'基础不牢：{worst["suggestion"]}，建议重新学习基本手位'