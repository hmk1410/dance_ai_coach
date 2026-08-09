# standard_from_video.py
"""
从舞蹈老师录制视频 → 自动提取标准模板
"""

import cv2
from dance_features import DanceFeatureExtractor
from dance_standards import SHAN_BANG_STANDARD


def extract_standard_metrics(video_path, hold_seconds=3, max_frames=400, stride=8):
    """
    从视频提取可直接用于 PoseAnalyzer 的标准指标。

    策略：从全片检出所有人体姿态帧，再挑选"最接近众数姿态"的一批帧，
    用它们的均值作为标准。这样即使舞者只在部分镜头中清晰可见也能工作。

    返回: {指标名: (min, standard, max)}；失败返回 None
    """
    import mediapipe as mp
    import statistics

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None

    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0:
        fps = 25

    mp_pose = mp.solutions.pose
    # 静态图模式：逐帧独立检测，对人体姿态更准确
    pose = mp_pose.Pose(static_image_mode=True, model_complexity=1,
                        min_detection_confidence=0.3)
    extractor = DanceFeatureExtractor()

    all_features = []
    frame_count = 0
    while len(all_features) < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_count % stride != 0:
            frame_count += 1
            continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)
        if results.pose_landmarks:
            try:
                feats = extractor.extract_shan_bang_features(results.pose_landmarks.landmark)
                all_features.append(feats)
            except Exception:
                pass
        frame_count += 1

    cap.release()
    pose.close()

    if len(all_features) < 3:
        return None

    # 计算各指标的众数（中位数）
    keys = list(all_features[0].keys())
    medians = {k: statistics.median(f[k] for f in all_features) for k in keys}

    # 每帧与中位姿态的偏差
    deviations = []
    for f in all_features:
        dev = sum(abs(f[k] - medians[k]) for k in keys) / len(keys)
        deviations.append(dev)

    # 保留偏差最小的 40%（最稳定的保持姿态）
    order = sorted(range(len(all_features)), key=lambda i: deviations[i])
    keep_count = max(5, int(len(order) * 0.4))
    selected = [all_features[i] for i in order[:keep_count]]

    metrics = {}
    for k in keys:
        values = [f[k] for f in selected]
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 2.0
        tol = max(stdev * 2, 3.0)
        metrics[k] = (round(mean - tol, 1), round(mean, 1), round(mean + tol, 1))

    return metrics


def extract_standard_from_video(video_path, action_name, hold_seconds=3):
    """
    从老师标准动作视频提取模板参数
    
    参数：
        video_path: 视频文件路径
        action_name: 动作名称（'shan_bang'等）
        hold_seconds: 动作保持时间（用于取平均）
    
    返回：
        标准模板字典，可直接保存为JSON
    """
    import mediapipe as mp
    
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # MediaPipe初始化
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(static_image_mode=False)
    
    extractor = DanceFeatureExtractor()
    
    # 存储所有帧的特征
    all_features = []
    
    print(f"正在分析视频: {video_path}")
    print(f"总帧数: {total_frames}, FPS: {fps}")
    
    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # 处理每第5帧（降低计算量）
        if frame_count % 5 != 0:
            frame_count += 1
            continue
        
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)
        
        if results.pose_landmarks:
            # 提取特征
            features = extractor.extract_shan_bang_features(results.pose_landmarks.landmark)
            all_features.append(features)
            
            # 显示进度
            if frame_count % 30 == 0:
                print(f"  已处理 {frame_count}/{total_frames} 帧")
        
        frame_count += 1
    
    cap.release()
    pose.close()
    
    # 寻找最稳定的片段（老师保持定型的部分）
    # 简单方法：取中间1/3的帧（通常老师会在中间保持定型）
    start_idx = len(all_features) // 3
    end_idx = start_idx + int(hold_seconds * fps / 5)  # 每5帧采样一次
    end_idx = min(end_idx, len(all_features))
    
    stable_features = all_features[start_idx:end_idx]
    
    # 计算平均值作为标准值
    import statistics
    
    standard_values = {}
    tolerances = {}
    
    for key in stable_features[0].keys():
        values = [f[key] for f in stable_features]
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 2.0
        
        standard_values[key] = round(mean, 1)
        tolerances[key] = round(stdev * 2, 1)  # 2倍标准差作为容忍范围
    
    # 构建模板
    template = {
        'name': action_name,
        'source_video': video_path,
        'extracted_at': '2026-05-04',
        'sample_frames': len(stable_features),
        'standard_values': standard_values,
        'tolerances': tolerances,
        'teacher': '待填写',  # 手动补充
        'style': '古典舞',    # 手动补充
    }
    
    return template


# ========== 使用示例 ==========

if __name__ == '__main__':
    # 1. 老师录制视频：站在标记位置，做3次山膀，每次保持5秒
    # 2. 保存为 teacher_shan_bang.mp4
    
    # 3. 提取标准
    template = extract_standard_from_video(
        video_path="teacher_shan_bang.mp4",
        action_name="山膀",
        hold_seconds=3
    )
    
    # 4. 打印结果
    print("\n【提取的标准模板】")
    print(f"动作: {template['name']}")
    print(f"样本帧数: {template['sample_frames']}")
    print("\n标准值:")
    for key, val in template['standard_values'].items():
        tol = template['tolerances'][key]
        print(f"  {key}: {val}° ± {tol}°")
    
    # 5. 保存为JSON文件
    import json
    with open('standards/shan_bang_from_teacher.json', 'w', encoding='utf-8') as f:
        json.dump(template, f, ensure_ascii=False, indent=2)
    
    print("\n✓ 模板已保存到 standards/shan_bang_from_teacher.json")
    print("请手动补充：老师姓名、舞蹈流派、动作级别等信息")