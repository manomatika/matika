import pytest
from matika.database import PageType
from matika.main import app
from fastapi.routing import APIRoute


def _iter_api_routes(app_routes):
    """
    Yield all APIRoute objects from app.routes, handling both:
    - FastAPI < 0.138: routes included via include_router appear directly as APIRoute
    - FastAPI >= 0.138: routes included via include_router appear as _IncludedRouter;
      walk into their effective_candidates() to retrieve the original APIRoute.
    """
    for route in app_routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "effective_candidates"):
            # FastAPI 0.138+ _IncludedRouter
            for ctx in route.effective_candidates():
                if isinstance(ctx.original_route, APIRoute):
                    yield ctx.original_route


def test_all_routes_have_page_type():
    """
    Ensures ALL routes (except static mounts) have exactly one PageType tag.
    """
    valid_tags = {tag.value for tag in PageType}

    for route in _iter_api_routes(app.routes):
        if route.path.startswith("/static"):
            continue

        route_tags = set(route.tags or [])
        intersection = route_tags.intersection(valid_tags)

        assert len(intersection) == 1, (
            f"Route {route.path} [{route.methods}] must have exactly one PageType tag. "
            f"Found: {list(intersection)}"
        )


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

    all_routes = list(_iter_api_routes(app.routes))

    for path, expected_type in routes_map.items():
        found = False
        for route in all_routes:
            if route.path == path:
                assert expected_type.value in route.tags, (
                    f"Route {path} expected tag {expected_type.value}"
                )
                found = True
                break
        assert found, f"Route {path} not found in app routes"
