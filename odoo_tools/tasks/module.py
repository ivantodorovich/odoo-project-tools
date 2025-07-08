# Copyright 2017 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from __future__ import annotations

import os
from typing import Any

from invoke import task


def get_addons_path() -> list[str]:
    """Reconstruct addons_path based on known odoo module locations"""
    # TODO: change depending on new structure
    # use root_path to get root project directory
    addons_path = ["odoo/src/addons", "odoo/local-src"]
    ext_path = "odoo/external-src/"
    addons_path.extend(
        [ext_path + i for i in os.listdir(ext_path) if os.path.isdir(ext_path + i)]
    )
    return addons_path


class Module:
    def __init__(self, name: str) -> None:
        self.name = name

    @property
    def dir(self) -> str:
        """Gives the location of a module

        Search in know locations

        :returns directory

        """
        addons_path = get_addons_path()
        for folder in addons_path:
            if self.name in os.listdir(folder):
                return folder
        # TODO: change depending on new structure
        # use root_path to get root project directory
        if self.name == "base":
            return "odoo/src/odoo/addons"
        raise Exception(f"module {self.name} not found")

    @property
    def path(self) -> str:
        directory = self.dir
        return os.path.join(directory, self.name)

    def get_dependencies(self) -> list[str]:
        if self.name == "base":
            return []
        path = self.path
        try:
            manifest_path = os.path.join(path, "__manifest__.py")
            with open(manifest_path) as f:
                manifest_data = eval(f.read())  # type: ignore[misc]
                return manifest_data.get("depends", [])
        except OSError:
            manifest_path = os.path.join(path, "__openerp__.py")
            with open(manifest_path) as f:
                manifest_data = eval(f.read())  # type: ignore[misc]
                return manifest_data.get("depends", [])


@task
def where_is(ctx: Any, module_name: str) -> None:
    """Locate a module"""
    print(Module(module_name).path)
