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

class MenuType(str, Enum):
    DEFAULT = "Default"
    APPLICATION = "Application"
    ROLE = "Role"
    SYSTEM = "System"
    FAVORITES = "Favorites"

class MenuItemType(str, Enum):
    LINK = "Link"
    MENU = "Menu"
    SEPARATOR = "Separator"
