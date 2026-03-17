from dataclasses import dataclass, field
from typing import Any, List

EMPTY_STRING = ""


@dataclass
class ResponseEmbeddedError:
    path: str = EMPTY_STRING
    message: str = EMPTY_STRING
    rejectValue: Any = None
    source: str = EMPTY_STRING


@dataclass
class Response:
    errorCode: int = 0
    data: Any = None
    message: str = EMPTY_STRING
    _embedded: List[ResponseEmbeddedError] = field(default_factory=list)

    def get_data(self):
        return self.data

    def get_message(self):
        return self.message

    def get_error_code(self):
        return self.errorCode

    def is_success(self) -> bool:
        return self.errorCode == 0
