import time
from django.conf import settings

_static_version = None


def _get_static_version():
    global _static_version
    if _static_version is None:
        _static_version = int(time.time())
    return _static_version


def console_context(request):
    return {
        "static_version": _get_static_version(),
        "apps": {
            "experiments": {
                "name": "实验管理",
                "enabled": True,
                "description": "实验管理、详情、指标对比",
                "icon": "flask",
            },
            "strategies": {
                "name": "策略管理",
                "enabled": True,
                "description": "已注册策略及参数 schema",
                "icon": "cog",
            },
        },
    }
