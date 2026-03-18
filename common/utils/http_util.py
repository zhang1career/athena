"""HTTP response utilities for REST API"""
import json
import logging
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

from django.conf import settings
from rest_framework import status as http_status
from rest_framework.exceptions import ParseError
from rest_framework.response import Response as DRFResponse

from common.consts.response_const import RET_OK
from common.pojo.response import Response as ResponsePojo

logger = logging.getLogger(__name__)


def url_decode(s: str) -> str:
    return unquote(s) if s else ""


def safe_request_data(request) -> dict:
    """Safely get request.data as dict. Returns {} on empty/invalid JSON body."""
    try:
        data = getattr(request, "data", None)
        if data is None:
            return {}
        if isinstance(data, dict):
            return data
        return {}
    except (json.JSONDecodeError, ValueError, TypeError, ParseError):
        return {}


def with_type(data):
    """Convert string to int, 'true'/'false' to bool"""
    try:
        if isinstance(data, list):
            return [with_type(item) for item in data]
        if isinstance(data, dict):
            return {key: with_type(value) for key, value in data.items()}
        if data is None:
            return None
        if isinstance(data, (int, bool, float)):
            return data
        if isinstance(data, str):
            if data.isnumeric():
                return int(data)
            if data.lower() == "true":
                return True
            if data.lower() == "false":
                return False
            return url_decode(data)
        raise TypeError(f"Unsupported type: {type(data)}")
    except Exception as e:
        logger.error("Error processing data: %s", e)
        raise


def resp_ok(data=None):
    obj = ResponsePojo(errorCode=RET_OK, data=data, message="")
    resp = DRFResponse(asdict(obj), status=http_status.HTTP_200_OK)
    resp["Expires"] = (datetime.now(timezone.utc) + timedelta(seconds=5)).strftime(
        "%a, %d %b %Y %H:%M:%S %Z"
    )
    return resp


def resp_err(message, code=-1, status=http_status.HTTP_200_OK):
    obj = ResponsePojo(errorCode=code, data=None, message=message)
    return DRFResponse(asdict(obj), status=status)


def resp_exception(e: Exception, code=-1, status=http_status.HTTP_200_OK):
    message = repr(e) if settings.DEBUG else str(e)
    obj = ResponsePojo(errorCode=code, data=None, message=message)
    return DRFResponse(asdict(obj), status=status)
