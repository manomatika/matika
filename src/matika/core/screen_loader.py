import os
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

SUPPORTED_SCHEMA = "1.0"
ALLOWED_VERBS = frozenset({
    "navigate",
    "fill",
    "click",
    "wait_for",
    "assert_present",
    "assert_absent",
    "assert_value",
})


class ScreenLoaderService:
    """
    Standalone service for discovering and loading screen files.

    Scans two locations:
      - core_screens_dir: framework-owned screens (src/matika/screens/)
      - plugins_dir:      one subdirectory per AppLug

    load_screens() returns a unified structure keyed by source_id.
    Each source maps to a list of screen entry dicts (type "screen" or
    "not_a_screen").

    Core screens are assembled by merging all *_screens.json files found in
    core_screens_dir into a single "core" list. Plugin screens expect exactly
    one *_screens.json per plugin directory.

    Duplicate screen_ids across all sources cause a RuntimeError at load time
    (startup abort) — this is intentional fail-loud behaviour.
    """

    def __init__(self, core_screens_dir: str, plugins_dir: str):
        self.core_screens_dir = core_screens_dir
        self.plugins_dir = plugins_dir
        self._cache: Optional[Dict[str, List[Dict]]] = None

    def load_screens(self) -> Dict[str, List[Dict]]:
        """
        Returns {source_id: [list of screen entries]} for all discovered
        *_screens.json files.
        "core" is assembled by merging all *_screens.json files in
        core_screens_dir. Each plugin contributes one entry keyed by its
        directory name.
        Result is cached after the first call; call invalidate_cache() to
        refresh.
        Raises RuntimeError if any screen_id is duplicated across sources.
        """
        if self._cache is None:
            self._cache = self._do_load_screens()
        return self._cache

    def _do_load_screens(self) -> Dict[str, List[Dict]]:
        result: Dict[str, List[Dict]] = {}

        # Core screens: merge all *_screens.json files in core_screens_dir.
        core = self._load_core_screens()
        if core is not None:
            result["core"] = core

        # Plugin screens: one *_screens.json per plugin subdirectory.
        if os.path.exists(self.plugins_dir):
            for entry in sorted(os.listdir(self.plugins_dir)):
                plugin_path = os.path.join(self.plugins_dir, entry)
                if not os.path.isdir(plugin_path):
                    continue

                screens_file: Optional[str] = None
                for filename in os.listdir(plugin_path):
                    if filename.endswith("_screens.json"):
                        screens_file = os.path.join(plugin_path, filename)
                        break

                if not screens_file:
                    continue

                parsed = self._parse_screens_file(screens_file)
                if parsed is not None:
                    result[entry] = parsed

        self._check_duplicate_ids(result)
        return result

    def _load_core_screens(self) -> Optional[List[Dict]]:
        """Merge all *_screens.json files in core_screens_dir into a single list."""
        if not os.path.exists(self.core_screens_dir):
            return None

        merged: List[Dict] = []
        found_any = False

        for filename in sorted(os.listdir(self.core_screens_dir)):
            if not filename.endswith("_screens.json"):
                continue
            path = os.path.join(self.core_screens_dir, filename)
            parsed = self._parse_screens_file(path)
            if parsed is None:
                continue
            found_any = True
            merged.extend(parsed)

        if not found_any:
            return None

        return merged

    def _parse_screens_file(self, path: str) -> Optional[List[Dict]]:
        """
        Read and validate a single *_screens.json file.
        Returns a list of screen entry dicts or None on schema mismatch or
        parse error (including invalid JSON).
        Raises ValueError if an entry fails validation (unknown verb, missing
        required field, unknown type).
        """
        # Parse JSON separately so decode errors are caught and logged, not re-raised.
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            logger.error("Failed to load screens file %s: %s", path, exc)
            return None

        schema = data.get("schema_version")
        if schema != SUPPORTED_SCHEMA:
            logger.warning(
                "Skipping %s: unsupported schema_version '%s'", path, schema
            )
            return None

        entries: List[Dict] = []
        for entry in data.get("screens", []):
            entry_type = entry.get("type")

            if entry_type == "not_a_screen":
                if "reason" not in entry:
                    raise ValueError(
                        f"Screen entry '{entry.get('screen_id')}' in {path} "
                        f"has type 'not_a_screen' but is missing required 'reason' field"
                    )
                entries.append(entry)

            elif entry_type == "screen":
                if "markers" not in entry:
                    raise ValueError(
                        f"Screen entry '{entry.get('screen_id')}' in {path} "
                        f"has type 'screen' but is missing required 'markers' field"
                    )
                # Validate optional required_markers field.
                required_markers = entry.get("required_markers")
                if required_markers is not None:
                    if not isinstance(required_markers, list):
                        raise ValueError(
                            f"Screen entry '{entry.get('screen_id')}' in {path} "
                            f"has 'required_markers' that is not a list"
                        )
                    markers = entry.get("markers", [])
                    for sel in required_markers:
                        if sel not in markers:
                            raise ValueError(
                                f"Screen entry '{entry.get('screen_id')}' in {path} "
                                f"has 'required_markers' entry '{sel}' that is not in 'markers'"
                            )
                steps = entry.get("steps")
                if not isinstance(steps, list):
                    raise ValueError(
                        f"Screen entry '{entry.get('screen_id')}' in {path} "
                        f"has type 'screen' but 'steps' must be a list"
                    )
                for step in steps:
                    verb = step.get("verb")
                    if verb not in ALLOWED_VERBS:
                        raise ValueError(
                            f"Screen entry '{entry.get('screen_id')}' in {path} "
                            f"contains unknown verb '{verb}'. "
                            f"Allowed verbs: {sorted(ALLOWED_VERBS)}"
                        )
                entries.append(entry)

            else:
                raise ValueError(
                    f"Screen entry '{entry.get('screen_id')}' in {path} "
                    f"has unknown type '{entry_type}'. "
                    f"Expected 'screen' or 'not_a_screen'."
                )

        return entries

    def _check_duplicate_ids(self, all_screens: Dict[str, List[Dict]]) -> None:
        """
        Check for duplicate screen_ids across all sources.
        Raises RuntimeError naming the offending screen_id and both source names.
        This is intentional fail-loud behaviour — startup must abort on any dup.
        """
        seen: Dict[str, str] = {}  # screen_id -> source_id
        for source_id, entries in all_screens.items():
            for entry in entries:
                sid = entry.get("screen_id")
                if sid is None:
                    continue
                if sid in seen:
                    raise RuntimeError(
                        f"Duplicate screen_id '{sid}' found in both "
                        f"'{seen[sid]}' and '{source_id}'. "
                        f"Each screen_id must be unique across all sources."
                    )
                seen[sid] = source_id

    def invalidate_cache(self) -> None:
        self._cache = None
