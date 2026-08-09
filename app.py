"""
Flask主程序：提供视频流服务、舞蹈视频库与Web界面
"""

from flask import Flask, render_template, Response, jsonify, request, send_from_directory
import cv2
import threading
import time
import os
import json
from pose_analyzer import PoseAnalyzer
from standard_from_video import extract_standard_metrics
from dance_coach import ask_dance_coach, is_configured, load_config

app = Flask(__name__)

# ========== 全局状态 ==========
camera = None           # 摄像头对象
analyzer = PoseAnalyzer()  # 姿态分析器（全局单例）
is_running = False      # 是否正在运行
current_frame = None    # 当前帧（用于视频流）
lock = threading.Lock() # 线程锁
video_extract_lock = threading.Lock()  # 视频标准提取锁

# ========== 视频库 ==========
VIDEO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vidoe')
META_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'videos_meta.json')
video_standard_cache = {}   # filename -> metrics 缓存
VIDEO_EXTS = ('.mp4', '.mov', '.avi', '.webm', '.mkv')

# 分析结果缓存（供前端获取）
latest_analysis = {
    'score': 0,
    'feedback': [],
    'template': 'stand',
    'source': '内置模板:基本站姿',
    'timestamp': 0
}

# ========== 训练统计（持久化） ==========
STATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'training_stats.json')
stats_lock = threading.Lock()
_training_stats = None
_manual_active = False         # 手动训练会话是否开启
_manual_start = None           # 手动训练开始时间

def _default_stats():
    return {'total_sessions': 0, 'total_seconds': 0.0, 'daily_seconds': {}, 'daily_sessions': {}}

def load_stats():
    """读取训练统计（内存缓存 + 文件回退）"""
    global _training_stats
    if _training_stats is None:
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                _training_stats = json.load(f)
        except Exception:
            _training_stats = {}
        s = _default_stats()
        for k in s:
            _training_stats.setdefault(k, s[k])
    return _training_stats

def save_stats():
    """将训练统计写盘"""
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(_training_stats, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_video_library():
    """自动扫描 vidoe 目录，构建视频库（可配合 videos_meta.json 补充元数据）"""
    meta = {}
    if os.path.exists(META_FILE):
        try:
            with open(META_FILE, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        except Exception:
            meta = {}

    videos = []
    if os.path.isdir(VIDEO_DIR):
        for fn in sorted(os.listdir(VIDEO_DIR)):
            if fn.lower().endswith(VIDEO_EXTS):
                name = os.path.splitext(fn)[0]
                m = meta.get(fn, {})
                videos.append({
                    'id': name,
                    'title': m.get('title', name),
                    'category': m.get('category', '未分类'),
                    'tags': m.get('tags', []),
                    'filename': fn,
                    'size': os.path.getsize(os.path.join(VIDEO_DIR, fn)),
                })
    return videos


def get_camera():
    """获取或初始化摄像头"""
    global camera
    if camera is None or not camera.isOpened():
        # 尝试打开默认摄像头
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            # 尝试其他索引
            for i in range(1, 5):
                camera = cv2.VideoCapture(i)
                if camera.isOpened():
                    break
        
        if camera.isOpened():
            # 设置分辨率（降低以提升帧率）
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            camera.set(cv2.CAP_PROP_FPS, 30)
    
    return camera


def processing_loop():
    """后台处理线程：持续读取摄像头、AI分析、生成标注帧"""
    global current_frame, latest_analysis, is_running

    cap = get_camera()
    
    if not cap.isOpened():
        print("ERROR: Cannot open camera!")
        is_running = False
        return
    
    print("Processing loop started...")

    frame_count = 0
    fps_start = time.time()
    fps = 0
    
    while is_running:
        ret, frame = cap.read()
        if not ret:
            continue

        frame_count += 1
        now = time.time()
        if now - fps_start >= 1.0:
            fps = int(round(frame_count / (now - fps_start)))
            frame_count = 0
            fps_start = now

        # AI处理
        processed_frame, analysis = analyzer.process_frame(frame)

        # 更新全局状态
        with lock:
            current_frame = processed_frame.copy()
            template = analyzer.current_template
            if analyzer.external_template is not None:
                source = f'视频标准:{template}'
            else:
                source = f'内置模板:{template}'
            latest_analysis = {
                'score': analysis.get('overall_score', 0),
                'feedback': analysis.get('feedback', []),
                'template': template,
                'source': source,
                'fps': fps,
                'timestamp': time.time()
            }
        
        # 控制帧率（避免CPU过载）
        time.sleep(0.01)
    
    # 清理
    cap.release()
    print("Processing loop stopped.")


def generate_frames():
    """生成MJPEG视频流"""
    global current_frame
    
    while True:
        with lock:
            if current_frame is not None:
                # 编码为JPEG
                ret, buffer = cv2.imencode('.jpg', current_frame, 
                                          [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ret:
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        # 控制流速率（约30fps）
        time.sleep(0.033)


def get_video_standard(video_id):
    """获取视频的标准姿态模板（带缓存）"""
    videos = load_video_library()
    v = next((x for x in videos if x['id'] == video_id), None)
    if not v:
        return None, None
    path = os.path.join(VIDEO_DIR, v['filename'])

    if v['filename'] in video_standard_cache:
        return v, video_standard_cache[v['filename']]

    with video_extract_lock:
        # 双检缓存
        if v['filename'] in video_standard_cache:
            return v, video_standard_cache[v['filename']]
        metrics = extract_standard_metrics(path)
        if metrics:
            video_standard_cache[v['filename']] = metrics
        return v, metrics


# ========== 路由定义 ==========

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')


@app.route('/video_feed')
def video_feed():
    """视频流接口"""
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/video/<path:filename>')
def serve_video(filename):
    """播放舞蹈标准视频文件"""
    return send_from_directory(VIDEO_DIR, filename)


@app.route('/api/analysis')
def get_analysis():
    """获取当前分析结果（JSON）"""
    return jsonify(latest_analysis)


@app.route('/api/videos')
def api_videos():
    """视频库列表 + 搜索（?q=关键词）"""
    q = request.args.get('q', '').strip().lower()
    videos = load_video_library()
    if q:
        videos = [v for v in videos
                  if q in v['title'].lower()
                  or q in v['category'].lower()
                  or q in v['filename'].lower()
                  or any(q in t.lower() for t in v['tags'])]
    return jsonify({'videos': videos, 'total': len(videos)})


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


@app.route('/api/videos/<video_id>/thumbnail')
def video_thumbnail(video_id):
    """视频缩略图接口"""
    videos = load_video_library()
    v = next((x for x in videos if x['id'] == video_id), None)
    if not v:
        return ('', 404)
    frame = get_video_frame(os.path.join(VIDEO_DIR, v['filename']))
    if frame is None:
        return ('', 404)
    ret, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
    if not ret:
        return ('', 500)
    return Response(buf.tobytes(), mimetype='image/jpeg')


@app.route('/api/use_video', methods=['POST'])
def use_video():
    """选中视频，提取标准姿态，用于实时矫正"""
    data = request.get_json() or {}
    video_id = data.get('video_id', '')
    v, metrics = get_video_standard(video_id)
    if not v:
        return jsonify({'success': False, 'error': '未找到该视频'}), 404
    if not metrics:
        return jsonify({'success': False, 'error': '无法从该视频中识别出人体姿态'}), 422

    with lock:
        analyzer.set_external_template(v['title'], metrics)

    return jsonify({
        'success': True,
        'title': v['title'],
        'category': v['category'],
        'filename': v['filename'],
        'video_url': f"/video/{v['filename']}",
        'metrics_count': len(metrics)
    })


@app.route('/api/set_template', methods=['POST'])
def set_template():
    """切换内置动作模板"""
    data = request.get_json() or {}
    template_name = data.get('template', 'stand')

    with lock:
        ok = analyzer.set_template(template_name)
    if not ok:
        return jsonify({'success': False, 'error': f'未知模板: {template_name}'}), 400
    return jsonify({'success': True, 'template': template_name})


@app.route('/api/start', methods=['POST'])
def start():
    """启动处理"""
    global is_running
    
    if not is_running:
        is_running = True
        thread = threading.Thread(target=processing_loop)
        thread.daemon = True
        thread.start()
        return jsonify({'status': 'started'})
    
    return jsonify({'status': 'already_running'})


@app.route('/api/stop', methods=['POST'])
def stop():
    """停止处理"""
    global is_running
    is_running = False
    with stats_lock:
        save_stats()  # 停止时写盘，避免丢失统计
    return jsonify({'status': 'stopped'})


@app.route('/api/chat', methods=['POST'])
def api_chat():
    """AI舞蹈教练问答接口"""
    data = request.get_json() or {}
    message = (data.get('message') or '').strip()
    history = data.get('history') or []
    if not message:
        return jsonify({'success': False, 'error': '请输入问题'}), 400

    # 把当前训练模板作为背景提供给模型（如：视频标准:xxx 或 内置模板:xxx）
    with lock:
        context = latest_analysis.get('source', '') or ''

    answer, err = ask_dance_coach(message, history, context=context)
    if err:
        return jsonify({'success': False, 'error': err})
    return jsonify({'success': True, 'reply': answer})


@app.route('/api/coach/status')
def coach_status():
    """查询舞蹈教练是否已配置 API Key"""
    cfg = load_config()
    return jsonify({
        'configured': is_configured(),
        'model': cfg.get('deepseek_model', 'deepseek-chat'),
        'base_url': cfg.get('deepseek_base_url', 'https://api.deepseek.com')
    })


@app.route('/api/stats')
def api_stats():
    """获取训练统计：累计次数 / 累计时长 / 今日数据 / 手动会话状态"""
    with stats_lock:
        stats = load_stats()
        today = time.strftime('%Y-%m-%d')
        return jsonify({
            'total_sessions': stats['total_sessions'],
            'total_seconds': round(stats['total_seconds'], 1),
            'today_seconds': round(stats['daily_seconds'].get(today, 0.0), 1),
            'today_sessions': stats['daily_sessions'].get(today, 0),
            'today': today,
            'manual_active': _manual_active,
            'manual_elapsed': round(time.time() - _manual_start, 1) if (_manual_active and _manual_start is not None) else 0.0
        })


@app.route('/api/training/start', methods=['POST'])
def training_start():
    """手动开始一次训练：计一次会话并开始计时"""
    global _manual_active, _manual_start
    with stats_lock:
        if not _manual_active:
            _manual_active = True
            _manual_start = time.time()
            stats = load_stats()
            today = time.strftime('%Y-%m-%d')
            stats['total_sessions'] += 1
            stats['daily_sessions'][today] = stats['daily_sessions'].get(today, 0) + 1
            save_stats()
        return jsonify({'success': True, 'manual_active': _manual_active})


@app.route('/api/training/stop', methods=['POST'])
def training_stop():
    """手动结束当前训练会话：把本次时长计入累计并停止"""
    global _manual_active, _manual_start
    with stats_lock:
        if _manual_active and _manual_start is not None:
            elapsed = time.time() - _manual_start
            stats = load_stats()
            today = time.strftime('%Y-%m-%d')
            stats['total_seconds'] += elapsed
            stats['daily_seconds'][today] = stats['daily_seconds'].get(today, 0.0) + elapsed
            _manual_active = False
            _manual_start = None
            save_stats()
        return jsonify({'success': True, 'manual_active': _manual_active})


@app.route('/api/stats/reset', methods=['POST'])
def api_stats_reset():
    """清零全部训练统计（同时结束手动会话）"""
    global _training_stats, _manual_active, _manual_start
    with stats_lock:
        _training_stats = _default_stats()
        _manual_active = False
        _manual_start = None
        save_stats()
    return jsonify({'success': True})


# ========== 启动 ==========

if __name__ == '__main__':
    # 启动时自动开始处理
    is_running = True
    thread = threading.Thread(target=processing_loop)
    thread.daemon = True
    thread.start()
    
    # 运行Flask（局域网可访问）
    print("=" * 50)
    print("舞镜·智芯 - AI舞蹈教练 Demo")
    print("=" * 50)
    print("访问地址：")
    print("  本机：http://127.0.0.1:5000")
    print("  局域网：http://<本机IP>:5000")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
