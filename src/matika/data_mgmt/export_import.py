import os
import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from ..database import get_system_setting

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

def get_activity_categories(db: Session, context: str, t: dict):
    """
    Scans all activity metadata to find categories supported for export/import.
    context: 'user_data' or 'system_data'
    """
    categories = []
    # 1. Add core categories based on context
    if context == "user_data":
        categories.append({"id": "roles", "name": "include_roles", "label": t.get("label_include_roles", "Custom Roles")})
    else: # system_data
        categories.append({"id": "logging", "name": "include_logging", "label": t.get("label_include_logging", "Logging")})
        categories.append({"id": "endpoints", "name": "include_endpoints", "label": t.get("label_include_endpoints", "Endpoints")})
        categories.append({"id": "system_roles", "name": "include_system_roles", "label": t.get("label_include_system_roles", "System Roles")})

    # 2. Scan activity metadata
    metadata_dir = os.path.join(BASE_DIR, "metadata")
    if os.path.exists(metadata_dir):
        for filename in os.listdir(metadata_dir):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(metadata_dir, filename), "r") as f:
                        meta = json.load(f)
                        ei = meta.get("export_import", {})
                        if context == "user_data" and ei.get("supports_user_data"):
                            for cat in ei.get("user_data_categories", []):
                                categories.append({
                                    "id": cat["id"], 
                                    "name": cat["name"], 
                                    "label": t.get(cat["label_key"], cat["id"])
                                })
                        elif context == "system_data" and ei.get("supports_system_data"):
                            for cat in ei.get("system_data_categories", []):
                                categories.append({
                                    "id": cat["id"], 
                                    "name": cat["name"], 
                                    "label": t.get(cat["label_key"], cat["id"])
                                })
                except Exception as e:
                    logger.error(f"Error reading metadata for categories: {filename}: {e}")
    
    return categories
