# -*- coding: utf-8 -*-
"""
coach.py
AI 教练服务：封装 dance_coach 的问答与配置解析。
"""

from dance_coach import (ask_dance_coach as _ask,
                         is_configured as _is_configured,
                         load_config as _load_config)


def ask(message, history=None, context='', user_llm=None):
    return _ask(message, history, context=context, user_llm=user_llm)


def is_configured():
    return _is_configured()


def load_global_config():
    return _load_config()
