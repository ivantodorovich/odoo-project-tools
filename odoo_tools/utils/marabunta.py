# Copyright 2023 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import Any, Union

from . import yaml


class MarabuntaFileHandler:
    def __init__(self, path_obj: Union[str, PathLike[str], Path]) -> None:
        self.path_obj = Path(path_obj)

    def load(self) -> dict[str, Any]:
        with self.path_obj.open() as f:
            content = f.read()
        result = yaml.yaml_load(content)
        if result is None:
            return {}
        return dict(result)  # Ensure it's a dict

    def update(self, version: str, run_click_hook: str = "post") -> None:
        data = self.load()
        versions = data.get("migration", {}).get("versions", [])
        version_item = None
        for item in versions:
            if item.get("version") == version:
                version_item = item
                break
        
        if version_item is None:
            version_item = {"version": version}
            versions.append(version_item)
            # Ensure migration structure exists
            if "migration" not in data:
                data["migration"] = {}
            data["migration"]["versions"] = versions
        
        if not version_item.get("operations"):
            version_item["operations"] = {}
        
        # Ensure operations is a dict
        operations_obj = version_item["operations"]
        if not isinstance(operations_obj, dict):
            operations_obj = {}
            version_item["operations"] = operations_obj
        
        operations: dict[str, list[str]] = operations_obj
        cmd = self._make_click_odoo_update_cmd()
        if run_click_hook not in operations:
            operations[run_click_hook] = []
        if cmd not in operations[run_click_hook]:
            operations[run_click_hook].append(cmd)
        yaml.update_yml_file(self.path_obj, data)

    def _make_click_odoo_update_cmd(self) -> str:
        return "click-odoo-update"

    def get_migration_file_modules(self) -> set[str]:
        """Read the migration.yml and get module list."""
        content = self.load()
        modules = set()
        for version in range(len(content["migration"]["versions"])):
            try:
                migration_version = content["migration"]["versions"][version]
                modules.update(migration_version["addons"]["upgrade"])
            except KeyError:
                pass
        return modules
