# Copyright 2023 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from __future__ import annotations

import re
from typing import Union

import requests


# TODO: detect if a given package is on pypi or not
# pkg_info = requests.get(f"https://pypi.org/pypi/{addon_name}/json")
# pkg_info.status_code == 404 if not found


def get_last_pypi_version(pkg_name: str, odoo: bool = True) -> str:
    """Retrieves the latest version of a python package on PyPI.

    Calls the API and retrieves the ``info.version`` key.

    :param pkg_name: the name of a PyPI package
    :param odoo: flag for Odoo packages handling

    :return: ``version`` if the package is listed, ``None`` otherwise
    """
    uri = f"https://pypi.org/pypi/{pkg_name}/json"
    try:
        response = requests.get(uri)
        response.raise_for_status()
        data = response.json()
        return data["info"]["version"]
    except (requests.RequestException, KeyError):
        # API will return 404 if package doesn't exist
        # KeyError if the response structure is unexpected
        return ""


def odoo_name_to_pkg_name(odoo_name: str, odoo_version: str = "", odoo_serie: str = "") -> str:
    """Transform a standard Odoo module name to PyPI package name.

    :param odoo_name: module name as in Odoo addons
    :param odoo_version: the Odoo version number
    :param odoo_serie: the Odoo serie (major.minor version)

    :return: PyPI package name
    """
    pkg_name = f"odoo-addon-{odoo_name.replace('_', '-')}"
    if odoo_serie:
        pkg_name = f"odoo{odoo_serie}-addon-{odoo_name.replace('_', '-')}"
    return pkg_name


def pkg_name_to_odoo_name(pkg_name: str, odoo_version: str = "") -> str:
    """Transform a PyPI package name to a standard Odoo module name.

    :param pkg_name: PyPI package name
    :param odoo_version: the Odoo version number

    :return: Odoo module name
    """
    # Regular expression to match patterns like:
    # - odoo-addon-module-name
    # - odoo16-addon-module-name
    pattern = r"^odoo(?:\d+)?-addon-(.+)$"
    match = re.match(pattern, pkg_name)
    if match:
        return match.group(1).replace("-", "_")
    return pkg_name
