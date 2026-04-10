import os
import json
import logging
from sqlalchemy import inspect
from ..database import PageType
from .paths import BASE_DIR

logger = logging.getLogger(__name__)

def load_metadata(activity_name: str, model_class=None) -> dict:
    """Loads metadata for a maintenance activity."""
    metadata_dir = os.path.join(BASE_DIR, "src", "matika", "metadata")
    paths = [
        os.path.join(metadata_dir, f"{activity_name}_maint_activity_metadata.json"),
        os.path.join(metadata_dir, f"{activity_name}.json")
    ]
    for path in paths:
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    
    # Fallback to model-derived defaults
    if model_class:
        columns = [c.key for c in inspect(model_class).mapper.column_attrs if c.key != 'id']
        return {
            "browse_panel": {
                "columns": [{"name": c, "label_key": f"th_{c}"} for c in columns]
            },
            "maintenance_panel": {
                "buttons": ["new", "edit", "delete"],
                "fields": [{"name": c, "label_key": f"label_{c}", "read_only": False} for c in columns]
            }
        }
    return {}

def format_num(value, lang_code="en"):
    """Formats numbers based on language code."""
    try:
        formatted = "{:,.2f}".format(float(value))
        if lang_code and lang_code.startswith("es"):
            return formatted.replace(",", "X").replace(".", ",").replace("X", ".")
        return formatted
    except (ValueError, TypeError):
        return value
