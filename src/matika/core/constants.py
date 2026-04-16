from enum import Enum

class PageType(str, Enum):
    MAINTENANCE = "Maintenance"
    SETTINGS = "Settings"
    INFO = "Info"

class PermissionLevel(str, Enum):
    CREATE = "Create"
    UPDATE = "Update"
    DELETE = "Delete"
    READ = "Read"
    FULL = "Full"
    NONE = "None"
