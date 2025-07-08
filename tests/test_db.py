# Copyright 2023 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import tempfile
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from odoo_tools.cli.db import (
    _download_from_azure,
    _get_list_of_dumps,
    cli,
    ensure_db_container_up,
    execute_db_request,
    expand_path,
    get_db_container_port,
    get_db_list,
    get_default_parameters,
)


@patch("odoo_tools.cli.db.get_project_manifest_key")
def test_get_default_parameters_success(mock_get_key):
    """Test successful retrieval of default parameters."""
    mock_get_key.side_effect = ["fr", "my_project_odoo"]
    platform, customer = get_default_parameters()
    assert platform == "fr"
    assert customer == "my-project"


@patch("odoo_tools.cli.db.get_project_manifest_key")
def test_get_default_parameters_no_platform(mock_get_key):
    """Test error when no platform is found."""
    mock_get_key.return_value = None
    with pytest.raises(click.ClickException):
        get_default_parameters()


def test_expand_path_home_directory():
    """Test expanding home directory in path."""
    with patch("os.path.expanduser") as mock_expand:
        mock_expand.return_value = "/home/user/test"
        result = expand_path("~/test")
        mock_expand.assert_called_once_with("~/test")
        assert result == "/home/user/test"


def test_expand_path_absolute():
    """Test that absolute paths are not changed."""
    result = expand_path("/absolute/path")
    assert result == "/absolute/path"


@patch("odoo_tools.cli.db.run")
def test_download_from_azure(mock_run):
    """Test downloading from Azure."""
    _download_from_azure("fr", "customer", "int", "dump.pg.gpg")
    mock_run.assert_called_once_with(
        "celebrimbor_cli -p fr download -c customer -e int --name dump.pg.gpg"
    )


@patch("odoo_tools.cli.db.run")
def test_get_list_of_dumps(mock_run):
    """Test getting list of dumps from Azure."""
    mock_run.return_value = '[{"name": "dump1.pg.gpg"}, {"name": "dump2.pg.gpg"}]'
    result = _get_list_of_dumps("fr", "customer", "int")
    assert result == ["dump1.pg.gpg", "dump2.pg.gpg"]
    mock_run.assert_called_once_with("celebrimbor_cli -p fr list -c customer -e int -r")


@patch("odoo_tools.cli.db.run")
def test_get_db_container_port(mock_run):
    """Test getting database container port."""
    mock_run.return_value = "127.0.0.1:5434"
    result = get_db_container_port()
    assert result == "5434"


@patch("odoo_tools.cli.db.ensure_db_container_up")
@patch("odoo_tools.cli.db.get_db_container_port")
@patch("psycopg2.connect")
def test_execute_db_request(mock_connect, mock_port, mock_ensure):
    """Test executing database request."""
    mock_port.return_value = "5432"
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [("test_db",), ("another_db",)]
    mock_connection = MagicMock()
    mock_connection.__enter__.return_value = mock_connection
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
    mock_connect.return_value = mock_connection

    result = execute_db_request("postgres", "SELECT datname FROM pg_database")
    assert result == [("test_db",), ("another_db",)]


@patch("odoo_tools.cli.db.execute_db_request")
def test_get_db_list(mock_execute):
    """Test getting list of databases."""
    mock_execute.return_value = [("test_db",), ("another_db",)]
    result = get_db_list()
    assert result == ["test_db", "another_db"]


@patch("odoo_tools.cli.db.get_db_list")
def test_list_command_success(mock_get_db_list):
    """Test list command with databases."""
    mock_get_db_list.return_value = ["db1", "db2", "db3"]
    runner = CliRunner()
    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0
    assert "Databases:" in result.output
    assert "db1" in result.output
    assert "db2" in result.output
    assert "db3" in result.output


@patch("odoo_tools.cli.db.get_db_list")
def test_list_command_no_databases(mock_get_db_list):
    """Test list command with no databases."""
    mock_get_db_list.return_value = []
    runner = CliRunner()
    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0
    assert "No databases found" in result.output


@patch("odoo_tools.cli.db.get_db_list")
def test_list_command_error(mock_get_db_list):
    """Test list command with error."""
    mock_get_db_list.side_effect = Exception("Database error")
    runner = CliRunner()
    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 1
    assert "Failed to list databases" in result.output


@patch("odoo_tools.cli.db.execute_db_request")
@patch("odoo_tools.cli.db.get_db_list")
def test_list_versions_command(mock_get_db_list, mock_execute):
    """Test list-versions command."""
    from datetime import datetime

    mock_get_db_list.return_value = ["test_db"]
    mock_execute.return_value = [(datetime(2023, 1, 1), "1.0.0")]

    runner = CliRunner()
    result = runner.invoke(cli, ["list-versions"])
    assert result.exit_code == 0
    assert "DB Name" in result.output
    assert "Version" in result.output
    assert "test_db" in result.output


@patch("odoo_tools.cli.db.run")
@patch("odoo_tools.cli.db.expand_path")
def test_restore_dump_command(mock_expand, mock_run):
    """Test restore-dump command."""
    mock_expand.return_value = "/tmp/test.pg"

    runner = CliRunner()
    with tempfile.NamedTemporaryFile(suffix=".pg") as tmp_file:
        result = runner.invoke(
            cli, ["restore-dump", tmp_file.name, "--db-name", "test_db"]
        )
        assert result.exit_code == 0
        assert "Restoring" in result.output
        assert "Dump successfully restored" in result.output


@patch("odoo_tools.cli.db.get_default_parameters")
@patch("odoo_tools.cli.db._get_list_of_dumps")
@patch("odoo_tools.cli.db._download_from_azure")
@patch("odoo_tools.cli.db.make_dir")
@patch("odoo_tools.cli.db.cd")
@patch("odoo_tools.cli.db.run")
@patch("os.path.isfile")
def test_download_restore_command(
    mock_isfile,
    mock_run,
    mock_cd,
    mock_make_dir,
    mock_download,
    mock_get_dumps,
    mock_get_params,
):
    """Test download-restore command."""
    mock_get_params.return_value = ("fr", "customer")
    mock_get_dumps.return_value = ["latest_dump.pg.gpg"]
    mock_isfile.return_value = False

    runner = CliRunner()
    result = runner.invoke(cli, ["download-restore"])
    assert result.exit_code == 0


@patch("odoo_tools.cli.db.ensure_db_container_up")
@patch("odoo_tools.cli.db.get_db_container_port")
@patch("odoo_tools.cli.db.get_project_manifest_key")
@patch("odoo_tools.cli.db.run")
@patch("getpass.getuser")
def test_dump_command(mock_getuser, mock_run, mock_get_key, mock_port, mock_ensure):
    """Test dump command."""
    mock_getuser.return_value = "testuser"
    mock_get_key.return_value = "test_project"
    mock_port.return_value = "5432"

    runner = CliRunner()
    result = runner.invoke(cli, ["dump", "--db-name", "test_db"])
    assert result.exit_code == 0
    assert "Dump successfully generated" in result.output


@patch("odoo_tools.cli.db.get_default_parameters")
@patch("odoo_tools.cli.db.ensure_db_container_up")
@patch("odoo_tools.cli.db.get_db_container_port")
@patch("odoo_tools.cli.db.get_project_manifest_key")
@patch("odoo_tools.cli.db.run")
@patch("odoo_tools.cli.db.expand_path")
@patch("getpass.getuser")
@patch("os.remove")
def test_dump_and_share_command(
    mock_remove,
    mock_getuser,
    mock_expand,
    mock_run,
    mock_get_key,
    mock_port,
    mock_ensure,
    mock_get_params,
):
    """Test dump-and-share command."""
    mock_get_params.return_value = ("fr", "customer")
    mock_getuser.return_value = "testuser"
    mock_get_key.return_value = "test_project"
    mock_port.return_value = "5432"
    mock_expand.return_value = "/tmp"

    runner = CliRunner()
    result = runner.invoke(cli, ["dump-and-share", "--db-name", "test_db"])
    assert result.exit_code == 0
    assert "Dump uploaded" in result.output
    assert "Local dump file removed" in result.output
    mock_remove.assert_called_once()


@patch("odoo_tools.cli.db.get_default_parameters")
@patch("odoo_tools.cli.db.ensure_db_container_up")
@patch("odoo_tools.cli.db.get_db_container_port")
@patch("odoo_tools.cli.db.get_project_manifest_key")
@patch("odoo_tools.cli.db.run")
@patch("odoo_tools.cli.db.expand_path")
@patch("getpass.getuser")
def test_dump_and_share_keep_local(
    mock_getuser,
    mock_expand,
    mock_run,
    mock_get_key,
    mock_port,
    mock_ensure,
    mock_get_params,
):
    """Test dump-and-share command with keep local option."""
    mock_get_params.return_value = ("fr", "customer")
    mock_getuser.return_value = "testuser"
    mock_get_key.return_value = "test_project"
    mock_port.return_value = "5432"
    mock_expand.return_value = "/tmp"

    runner = CliRunner()
    result = runner.invoke(cli, ["dump-and-share", "--keep-local-dump"])
    assert result.exit_code == 0
    assert "Dump uploaded" in result.output
    assert "Local dump file removed" not in result.output


def test_cli_help():
    """Test CLI help command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Database management commands" in result.output


def test_list_command_help():
    """Test list command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--help"])
    assert result.exit_code == 0
    assert "List all databases" in result.output


def test_restore_dump_command_help():
    """Test restore-dump command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["restore-dump", "--help"])
    assert result.exit_code == 0
    assert "Restore a PostgreSQL dump" in result.output


def test_dump_command_help():
    """Test dump command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["dump", "--help"])
    assert result.exit_code == 0
    assert "Create a PostgreSQL dump" in result.output


@patch("odoo_tools.cli.db.run")
def test_ensure_db_container_up_already_running(mock_run):
    """Test when container is already running."""
    mock_run.return_value = "0.0.0.0:5432"

    with ensure_db_container_up():
        pass

    # Should only check port, not start/stop
    mock_run.assert_called_once_with("docker compose port db 5432")


@patch("odoo_tools.cli.db.run")
def test_ensure_db_container_up_needs_start(mock_run):
    """Test when container needs to be started."""
    # First call fails (not running), subsequent calls succeed
    mock_run.side_effect = [Exception("Not running"), None, "0.0.0.0:5432", None]

    with ensure_db_container_up():
        pass

    # Should check port, start container, check port again, stop container
    expected_calls = [
        "docker compose port db 5432",  # Check if running
        "docker compose up -d db",  # Start container
        "docker compose port db 5432",  # Check if started
        "docker compose stop db",  # Stop container
    ]
    actual_calls = [call[0][0] for call in mock_run.call_args_list]
    assert actual_calls == expected_calls
