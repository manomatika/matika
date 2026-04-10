import pytest
from matika.database import PageType
from matika.main import app
from fastapi.routing import APIRoute

def test_all_routes_have_page_type():
    """
    Ensures ALL routes (except static mounts) have exactly one PageType tag.
    """
    valid_tags = {tag.value for tag in PageType}
    
    for route in app.routes:
        # Skip static files and internal FastAPI routes if any (like docs)
        if isinstance(route, APIRoute):
            if route.path.startswith("/static"):
                continue
            
            # Check tags
            route_tags = set(route.tags or [])
            intersection = route_tags.intersection(valid_tags)
            
            assert len(intersection) == 1, f"Route {route.path} [{route.methods}] must have exactly one PageType tag. Found: {list(intersection)}"

def test_specific_page_types():
    """
    Verifies that specific routes have the correct PageType.
    """
    routes_map = {
        "/admin/users": PageType.MAINTENANCE,
        "/admin/roles": PageType.MAINTENANCE,
        "/admin/permissions": PageType.MAINTENANCE,
        "/settings/user": PageType.SETTINGS,
        "/settings/system": PageType.SETTINGS,
        "/": PageType.INFO,
        "/about": PageType.INFO,
    }
    
    for path, expected_type in routes_map.items():
        found = False
        for route in app.routes:
            if isinstance(route, APIRoute) and route.path == path:
                assert expected_type.value in route.tags, f"Route {path} expected tag {expected_type.value}"
                found = True
                break
        assert found, f"Route {path} not found in app routes"
