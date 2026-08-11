# -*- coding: utf-8 -*-
"""
pose_runner.py
姿态处理服务：摄像头读取循环、MJPEG 视频流、视频帧截图。
"""

import time

import cv2

from .. import config
from .. import state


def get_camera():
    """获取或初始化摄像头"""
    if state.camera is None or not state.camera.isOpened():
        state.camera = cv2.VideoCapture(0)
        if not state.camera.isOpened():
            for i in range(1, 5):
                state.camera = cv2.VideoCapture(i)
                if state.camera.isOpened():
                    break
        if state.camera.isOpened():
            state.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            state.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            state.camera.set(cv2.CAP_PROP_FPS, 60)
    return state.camera


def processing_loop():
    """后台处理线程：持续读取摄像头、AI分析、生成标注帧"""
    cap = get_camera()
    if not cap.isOpened():
        print("ERROR: Cannot open camera!")
        state.is_running = False
        return

    print("Processing loop started...")
    frame_count = 0
    fps_start = time.time()
    fps = 0

    while state.is_running:
        ret, frame = cap.read()
        if not ret:
            continue

        # 镜像显示：画面像照镜子一样左右翻转
        frame = cv2.flip(frame, 1)

        frame_count += 1
        now = time.time()
        if now - fps_start >= 1.0:
            fps = int(round(frame_count / (now - fps_start)))
            frame_count = 0
            fps_start = now

        processed_frame, analysis = state.analyzer.process_frame(frame)

        with state.lock:
            state.current_frame = processed_frame.copy()
            source = '未选择视频标准'
            if state.analyzer.dtw_matcher is not None:
                source = '跟练:' + state.analyzer.current_template
            elif state.analyzer.external_template is not None:
                source = '视频标准:' + state.analyzer.current_template
            state.latest_analysis = {
                'score': analysis.get('overall_score', 0),
                'feedback': analysis.get('feedback', []),
                'source': source,
                'fps': fps,
                'timestamp': time.time()
            }

        time.sleep(0.002)

    cap.release()
    print("Processing loop stopped.")


def generate_frames():
    """生成MJPEG视频流"""
    while True:
        with state.lock:
            if state.current_frame is not None:
                ret, buffer = cv2.imencode('.jpg', state.current_frame,
                                          [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ret:
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.016)


def get_video_frame(video_path, frame_ratio=0.2):
    """从视频中截取一帧（用于缩略图）"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    target = max(0, int(total * frame_ratio) - 1)
    cap.set(cv2.CAP_PROP_POS_FRAMES, target)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None
    return frame
