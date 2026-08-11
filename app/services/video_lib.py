# -*- coding: utf-8 -*-
"""
video_lib.py
视频库服务：标准姿态提取、选中视频、上传处理。
"""

import os

from werkzeug.utils import secure_filename

from standard_from_video import extract_standard_metrics
from dtw_tracker import extract_standard_sequence

from .. import config
from .. import models
from .. import state


def get_video_standard(video_id):
    """获取视频的标准姿态模板（带缓存）

    缓存结构：{filename: {'metrics': {...}或None, 'sequence': [...]或None}}
    """
    v = models.find_video(video_id)
    if not v:
        return None, None
    path = os.path.join(config.VIDEO_DIR, v['filename'])

    cached = state.video_standard_cache.get(v['filename'])
    if cached is not None:
        return v, cached.get('metrics')

    with state.video_extract_lock:
        cached = state.video_standard_cache.get(v['filename'])
        if cached is not None:
            return v, cached.get('metrics')
        metrics = extract_standard_metrics(path)
        sequence = extract_standard_sequence(path)
        state.video_standard_cache[v['filename']] = {
            'metrics': metrics,
            'sequence': sequence,
        }
        return v, metrics


def get_video_sequence(video_id):
    """获取视频的 DTW 标准姿态序列（带缓存）"""
    v, _ = get_video_standard(video_id)
    if not v:
        return None
    cached = state.video_standard_cache.get(v['filename'])
    return cached.get('sequence') if cached else None


def select_video_for_training(video_id):
    """选中视频作为训练标准，返回 (v, metrics) 或 (None, None)

    优先使用 DTW 时序对齐（动态动作）；无可用时退回静态角度标准。
    """
    v, metrics = get_video_standard(video_id)
    if not v:
        return v, metrics
    sequence = get_video_sequence(video_id)
    with state.lock:
        if sequence:
            state.analyzer.set_dtw(v['title'], sequence)
        elif metrics:
            state.analyzer.set_external_template(v['title'], metrics)
        else:
            return v, None
    return v, metrics


def save_upload(file_storage):
    """保存上传文件到视频库，返回 (ok, data 或 error)"""
    if file_storage.filename == '':
        return False, '文件名为空'

    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in config.VIDEO_EXTS:
        return False, '不支持的文件格式 {0}，支持：{1}'.format(ext, ', '.join(config.VIDEO_EXTS))

    filename = secure_filename(file_storage.filename)
    save_path = os.path.join(config.VIDEO_DIR, filename)
    base, ext2 = os.path.splitext(filename)
    counter = 1
    while os.path.exists(save_path):
        filename = '{0}_{1}{2}'.format(base, counter, ext2)
        save_path = os.path.join(config.VIDEO_DIR, filename)
        counter += 1

    file_storage.save(save_path)

    metrics = None
    try:
        metrics = extract_standard_metrics(save_path)
    except Exception:
        pass

    state.video_standard_cache.clear()
    return True, {
        'filename': filename,
        'metrics': metrics,
    }


def delete_video(video_id):
    """删除视频。返回 (ok, error 或 None)"""
    v = models.find_video(video_id)
    if not v:
        return False, '未找到该视频'
    if '山膀' in v.get('title', '') or any('山膀' in t for t in v.get('tags', [])):
        return False, '山膀示范视频不可删除'
    path = os.path.join(config.VIDEO_DIR, v['filename'])
    try:
        os.remove(path)
    except Exception as e:
        return False, '删除失败：{0}'.format(e)
    state.video_standard_cache.pop(v['filename'], None)
    models.remove_video_meta(v['filename'])
    return True, None
