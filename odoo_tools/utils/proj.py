# Copyright 2023 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
from __future__ import annotations

import os
import shutil
import subprocess
import venv
from functools import cache
from os import PathLike
from pathlib import Path
from typing import Any, Union

from ..config import get_conf_key
from . import ui
from .misc import get_template_path
from .path import build_path, get_root_marker, root_path
from .yaml import yaml_load


@cache
def get_project_manifest(key: str | None = None) -> dict[str, Any]:
    path = root_path() / get_root_marker()
    with open(path) as f:
        return yaml_load(f.read())


def get_project_manifest_key(key: str) -> Any:
    return get_project_manifest()[key]


def get_current_version(serie_only: bool = False) -> str:
    """Get current project version."""
    version = get_project_manifest_key("odoo_version")
    if serie_only:
        version = ".".join(version.split(".")[0:2])
    return version


def setup_venv(venv_dir: Union[str, PathLike[str]], odoo_src_path: Union[str, PathLike[str], None] = None) -> None:
    """Setup a virtual environment for the project.
    
    :param venv_dir: Directory to create the virtual environment in
    :param odoo_src_path: Path to odoo source for development install
    """
    venv_path = Path(venv_dir)
    if venv_path.exists():
        ui.echo(f"Virtual environment already exists at {venv_path}")
    else:
        ui.echo(f"Creating virtual environment at {venv_path}")
        venv.create(venv_path, with_pip=True)

    pip_exe = venv_path / "bin" / "pip"
    
    # Install basic requirements
    subprocess.run([str(pip_exe), "install", "--upgrade", "pip", "setuptools", "wheel"], check=True)
    
    # Install project requirements
    req_file = build_path("requirements.txt")
    if req_file.exists():
        subprocess.run([str(pip_exe), "install", "-r", str(req_file)], check=True)
    
    # Install odoo in development mode if path provided
    if odoo_src_path:
        odoo_path = Path(odoo_src_path)
        if odoo_path.exists():
            subprocess.run([str(pip_exe), "install", "-e", str(odoo_path)], check=True)
    
    ui.echo(f"Virtual environment setup complete at {venv_path}")


def ensure_local_requirements(local_requirement_path: Union[str, PathLike[str]]) -> None:
    """Ensure local requirements file exists."""
    path = Path(local_requirement_path)
    if not path.exists():
        template_path = get_template_path("local-requirements.txt")
        shutil.copy(template_path, path)


def generate_odoo_config_file(
    config_path: Union[str, PathLike[str]],
    db_host: str = "localhost",
    db_port: int = 5432,
    db_user: str = "odoo",
    db_password: str = "odoo",
    addons_path: list[str] | None = None,
) -> None:
    """Generate an Odoo configuration file.
    
    :param config_path: Path where to write the config file
    :param db_host: Database host
    :param db_port: Database port
    :param db_user: Database user
    :param db_password: Database password
    :param addons_path: List of addon paths
    """
    if addons_path is None:
        addons_path = []
    
    config_content = f"""[options]
db_host = {db_host}
db_port = {db_port}
db_user = {db_user}
db_password = {db_password}
addons_path = {','.join(addons_path)}
"""
    
    with open(config_path, 'w') as f:
        f.write(config_content)
    
    ui.echo(f"Odoo configuration file generated at {config_path}")
