"""快速检测视频中人体姿态可见率。用法: python test_pose_detection.py <video> [--stride N]"""
import sys
import cv2
import mediapipe as mp
import statistics

def detect(video_path, stride=10, max_frames=400):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"{video_path}: 无法打开")
        return
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(static_image_mode=True, model_complexity=1, min_detection_confidence=0.3)
    total = 0
    ok = 0
    frame_count = 0
    while total < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_count % stride != 0:
            frame_count += 1
            continue
        total += 1
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)
        if results.pose_landmarks:
            ok += 1
        frame_count += 1
    cap.release()
    pose.close()
    rate = ok / total * 100 if total else 0
    print(f"{video_path}: 采样{total}帧, 检出{ok}帧, 检出率 {rate:.1f}%")

if __name__ == "__main__":
    stride = 10
    args = sys.argv[1:]
    if "--stride" in args:
        i = args.index("--stride")
        stride = int(args[i + 1])
        args = args[:i] + args[i + 2:]
    detect(args[0], stride=stride)
