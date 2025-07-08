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
        return yaml.yaml_load(self.path_obj.open().read())

    def update(self, version: str, run_click_hook: str = "post") -> None:
        data = self.load()
        versions = data["migration"]["versions"]
        version_item = [x for x in versions if x["version"] == version]
        if version_item:
            version_item = version_item[0]
        else:
            version_item = {"version": version}
            versions.append(version_item)
        if not version_item.get("operations"):
            version_item["operations"] = {}
        operations = version_item["operations"]
        cmd = self._make_click_odoo_update_cmd()
        if cmd not in operations.get(run_click_hook, []):
            operations.setdefault(run_click_hook, []).append(cmd)
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
