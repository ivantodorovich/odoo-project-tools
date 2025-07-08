# Copyright 2023 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from __future__ import annotations

import configparser
import pathlib
import shutil
import subprocess
from importlib.resources import files, abc
from os import PathLike
from typing import Any, Union

PKG_NAME = "odoo_tools"


def get_file_path(filepath: str) -> abc.Traversable:
    return files(PKG_NAME) / filepath


def get_template_path(filepath: str) -> abc.Traversable:
    return get_file_path("templates/" + filepath)


def get_cache_path() -> pathlib.Path:
    return pathlib.Path.home() / ".cache" / "otools"


def copy_file(src_path: Union[str, PathLike[str]], dest_path: Union[str, PathLike[str]]) -> None:
    shutil.copy(src_path, dest_path)


class SmartDict(dict[str, Any]):
    """Dotted notation dict."""

    def __getattr__(self, attrib: str) -> Any:
        val = self.get(attrib)
        return self.__class__(val) if type(val) is dict else val


def parse_ini_cfg(ini_content: str, header: str) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    # header might get stripped when reading content from output
    # (eg: when using bumpversion)
    header = f"[{header}]"
    if header not in ini_content:
        ini_content = header + "\n" + ini_content
    config.read_string(ini_content)
    return config


def get_ini_cfg_key(cfg_content: str, header: str, key: str) -> str:
    cfg = parse_ini_cfg(cfg_content, header)
    return cfg.get(header, key)


def get_docker_image_commit_hashes() -> tuple[str | None, str | None]:
    """Retrieve the odoo core and odoo enterprise commit hashes used in the project image"""
    with open("Dockerfile") as fobj:
        for line in fobj:
            if line.startswith("FROM ghcr.io/camptocamp/odoo-enterprise"):
                image = line.strip().split()[1]
                break
    process = subprocess.run(
        [
            "docker",
            "run",
            "--quiet",
            "--rm",
            "--pull",
            "always",
            "--entrypoint",
            "printenv",
            image,
        ],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    variables = {}
    for line in process.stdout.splitlines():
        try:
            name, value = line.strip().split("=", maxsplit=1)
        except ValueError:
            # not formatted as an environment variable, we can ignore
            continue
        variables[name] = value
    odoo_hash = variables.get("CORE_HASH")
    enterprise_hash = variables.get("ENTERPRISE_HASH")
    return odoo_hash, enterprise_hash
