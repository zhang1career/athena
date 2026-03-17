"""Custom model fields for platform_app."""
import json

from django.db import models


class JSONTextField(models.TextField):
    """Stores Python dict/list as JSON string in DB; returns dict/list in Python."""

    def __init__(self, *args, json_type=dict, **kwargs):
        self.json_type = json_type
        super().__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return self.json_type()
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return self.json_type()

    def get_prep_value(self, value):
        if value is None:
            return json.dumps(self.json_type(), ensure_ascii=False)
        return json.dumps(value, ensure_ascii=False)
