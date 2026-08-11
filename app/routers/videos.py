# -*- coding: utf-8 -*-
"""
videos.py
视频库路由：列表 / 缩略图 / 上传 / 选中训练 / 删除 / 改元数据。
"""

import os

import cv2
from flask import Blueprint, request, jsonify, Response, send_from_directory

from .. import config
from .. import models
from ..services import video_lib, pose_runner
from ..security import login_required, admin_required

bp = Blueprint('videos', __name__)


@bp.route('/video/<path:filename>')
def serve_video(filename):
    return send_from_directory(config.VIDEO_DIR, filename)


@bp.route('/api/videos')
@login_required
def list_videos():
    q = request.args.get('q', '').strip().lower()
    videos = models.load_video_library()
    if q:
        videos = [v for v in videos
                  if q in v['title'].lower()
                  or q in v['category'].lower()
                  or q in v['filename'].lower()
                  or any(q in t.lower() for t in v['tags'])]
    return jsonify({'videos': videos, 'total': len(videos)})


@bp.route('/api/videos/<video_id>/thumbnail')
@login_required
def thumbnail(video_id):
    v = models.find_video(video_id)
    if not v:
        return ('', 404)
    frame = pose_runner.get_video_frame(os.path.join(config.VIDEO_DIR, v['filename']))
    if frame is None:
        return ('', 404)
    ret, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
    if not ret:
        return ('', 500)
    return Response(buf.tobytes(), mimetype='image/jpeg')


@bp.route('/api/videos/<video_id>', methods=['DELETE'])
@admin_required
def delete_video(video_id):
    ok, err = video_lib.delete_video(video_id)
    if not ok:
        code = 403 if '山膀' in (err or '') else 500
        return jsonify({'success': False, 'error': err}), code
    return jsonify({'success': True})


@bp.route('/api/videos/<video_id>', methods=['PUT'])
@admin_required
def update_video_meta(video_id):
    v = models.find_video(video_id)
    if not v:
        return jsonify({'success': False, 'error': '未找到该视频'}), 404
    data = request.get_json() or {}
    category = (data.get('category') or '').strip()
    title = (data.get('title') or '').strip()
    entry = dict(v)
    entry.pop('size', None)
    if category:
        entry['category'] = category
    if title:
        entry['title'] = title
    models.save_video_meta(v['filename'], {k: entry[k] for k in ('title', 'category', 'tags') if k in entry})
    return jsonify({
        'success': True,
        'category': entry.get('category', v['category']),
        'title': entry.get('title', v['title'])
    })


@bp.route('/api/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '未选择文件'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': '文件名为空'}), 400

    ok, result = video_lib.save_upload(file)
    if not ok:
        return jsonify({'success': False, 'error': result}), 400

    filename = result['filename']
    metrics = result['metrics']
    title = (request.form.get('title') or '').strip()
    category = (request.form.get('category') or '').strip()
    entry = {'title': title or os.path.splitext(filename)[0], 'category': category or '未分类'}
    if title or category:
        models.save_video_meta(filename, entry)

    return jsonify({
        'success': True,
        'filename': filename,
        'title': entry['title'],
        'category': entry['category'],
        'metrics_count': len(metrics) if metrics else 0,
        'can_use': metrics is not None
    })


@bp.route('/api/use_video', methods=['POST'])
@login_required
def use_video():
    data = request.get_json() or {}
    video_id = data.get('video_id', '')
    v, metrics = video_lib.get_video_standard(video_id)
    if not v:
        return jsonify({'success': False, 'error': '未找到该视频'}), 404
    if not metrics:
        return jsonify({'success': False, 'error': '无法从该视频中识别出人体姿态'}), 422
    with state_lock():
        import app.state as st
        st.analyzer.set_external_template(v['title'], metrics)
    return jsonify({
        'success': True,
        'title': v['title'],
        'category': v['category'],
        'filename': v['filename'],
        'video_url': '/video/' + v['filename'],
        'metrics_count': len(metrics)
    })


def state_lock():
    import app.state as st
    return st.lock
