from click.shell_completion import ShellComplete
from click.testing import CliRunner
from tfa.cli import cli

import json
import os
import re


os.environ["TFA_STORAGE"] = "./temp_test_accounts.json"


def test_add_account_success():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Using a known valid base32 secret key
        result = runner.invoke(cli, ["add", "testaccount", "JBSWY3DPEHPK3PXP"])

        assert result.exit_code == 0
        # Verify the account was added by listing accounts
        list_result = runner.invoke(cli, ["list"])
        assert "testaccount" in list_result.output
        # The output should contain the account name and an initial TOTP code
        assert re.match(r"\d{6}\n", result.output), result.output


def test_add_account_invalid_key():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["add", "testaccount", "INVALID-KEY"])

        assert result.exit_code == 1
        assert "Invalid secret key" in result.output


def test_add_duplicate_account():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Add first account
        runner.invoke(cli, ["add", "testaccount", "JBSWY3DPEHPK3PXP"])
        # Try to add duplicate
        result = runner.invoke(cli, ["add", "testaccount", "JBSWY3DPEHPK3PXP"])

        assert result.exit_code == 1
        assert "already exists" in result.output


def test_add_duplicate_account_with_force():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Add first account
        runner.invoke(cli, ["add", "testaccount", "JBSWY3DPEHPK3PXP"])
        # Add duplicate with force flag
        result = runner.invoke(
            cli, ["add", "testaccount", "JBSWY3DPEHPK3PXP", "--force"]
        )

        assert result.exit_code == 0
        assert re.match(r"\d{6}\n", result.output), result.output


def test_add_account_with_custom_issuer():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli, ["add", "testaccount", "JBSWY3DPEHPK3PXP", "--issuer", "Custom"]
        )

        assert result.exit_code == 0
        # Verify custom issuer by checking code output
        code_result = runner.invoke(cli, ["code", "testaccount"])
        assert re.match(r"\d{6}\n", code_result.output), code_result.output


def test_code_existing_account():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # First add an account
        runner.invoke(cli, ["add", "testaccount", "JBSWY3DPEHPK3PXP"])
        # Then get its code
        result = runner.invoke(cli, ["code", "testaccount"])

        assert result.exit_code == 0
        assert re.match(r"\d{6}\n", result.output), result.output


def test_code_nonexistent_account():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["code", "nonexistent"])

        assert result.exit_code == 1
        assert "does not exist" in result.output


def test_code_with_custom_issuer():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Add account with custom issuer
        runner.invoke(
            cli, ["add", "testaccount", "JBSWY3DPEHPK3PXP", "--issuer", "Custom"]
        )
        # Get code
        result = runner.invoke(cli, ["code", "testaccount"])

        assert result.exit_code == 0
        assert re.match(r"\d{6}\n", result.output), result.output


def test_remove_existing_account():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Add then remove an account
        runner.invoke(cli, ["add", "testaccount", "JBSWY3DPEHPK3PXP"])
        result = runner.invoke(cli, ["remove", "testaccount"])

        assert result.exit_code == 0
        # Verify account is gone
        list_result = runner.invoke(cli, ["list"])
        assert "testaccount" not in list_result.output


def test_remove_nonexistent_account():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["remove", "nonexistent"])

        assert result.exit_code == 1
        assert "does not exist" in result.output


def test_list_empty():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["list"])

        assert result.exit_code == 0
        assert result.output == ""


def test_list_multiple_accounts():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Add multiple accounts
        runner.invoke(cli, ["add", "account1", "JBSWY3DPEHPK3PXP"])
        runner.invoke(cli, ["add", "account2", "JBSWY3DPEHPK3PXP"])

        result = runner.invoke(cli, ["list"])

        assert result.exit_code == 0
        assert "account1" in result.output
        assert "account2" in result.output
        # Verify one account per line
        assert len(result.output.strip().split("\n")) == 2


def test_qr_existing_account():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Add an account
        runner.invoke(cli, ["add", "testaccount", "JBSWY3DPEHPK3PXP"])
        # Generate QR code
        result = runner.invoke(cli, ["qr", "testaccount"])

        assert result.exit_code == 0
        # QR code output should contain typical QR ASCII art characters
        assert "█" in result.output or "▄" in result.output


def test_qr_nonexistent_account():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["qr", "nonexistent"])

        assert result.exit_code == 1
        assert "does not exist" in result.output


def test_export_dash_writes_json_to_stdout():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["add", "testaccount", "JBSWY3DPEHPK3PXP"])

        result = runner.invoke(cli, ["export", "-"])

        assert result.exit_code == 0
        assert json.loads(result.output) == {
            "testaccount": {"issuer": "testaccount", "key": "JBSWY3DPEHPK3PXP"}
        }


def test_import_dash_reads_json_from_stdin():
    runner = CliRunner()
    with runner.isolated_filesystem():
        payload = json.dumps(
            {"testaccount": {"issuer": "testaccount", "key": "JBSWY3DPEHPK3PXP"}}
        )

        result = runner.invoke(cli, ["import", "-"], input=payload)

        assert result.exit_code == 0
        assert "Import complete: 1 accounts imported, 0 skipped." in result.output
        list_result = runner.invoke(cli, ["list"])
        assert "testaccount" in list_result.output


def test_subcommand_storage_overrides_env():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["add", "envaccount", "JBSWY3DPEHPK3PXP"])
        runner.invoke(
            cli, ["add", "optaccount", "JBSWY3DPEHPK3PXP", "--storage", "other.db"]
        )

        result = runner.invoke(cli, ["list", "--storage", "other.db"])

        assert result.output == "optaccount\n"


def test_group_storage_overrides_env():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["add", "envaccount", "JBSWY3DPEHPK3PXP"])
        runner.invoke(cli, ["--storage", "other.db", "add", "a", "JBSWY3DPEHPK3PXP"])

        result = runner.invoke(cli, ["--storage", "other.db", "list"])

        assert result.output == "a\n"


def test_subcommand_storage_overrides_group_storage():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["add", "a", "JBSWY3DPEHPK3PXP", "--storage", "a.db"])
        runner.invoke(cli, ["add", "b", "JBSWY3DPEHPK3PXP", "--storage", "b.db"])

        result = runner.invoke(cli, ["--storage", "a.db", "list", "--storage", "b.db"])

        assert result.output == "b\n"


def test_missing_storage_is_an_error(monkeypatch):
    monkeypatch.delenv("TFA_STORAGE")
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["list"])

        assert result.exit_code == 1
        assert "TFA_STORAGE environment variable not set" in result.output


def complete(args, incomplete):
    completer = ShellComplete(cli, {}, "tfa", "_TFA_COMPLETE")
    return [item.value for item in completer.get_completions(args, incomplete)]


def test_completion_uses_group_storage():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["add", "a", "JBSWY3DPEHPK3PXP", "--storage", "a.db"])

        assert complete(["--storage", "a.db", "code"], "") == ["a"]


def test_completion_prefers_subcommand_storage():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["add", "a", "JBSWY3DPEHPK3PXP", "--storage", "a.db"])
        runner.invoke(cli, ["add", "b", "JBSWY3DPEHPK3PXP", "--storage", "b.db"])

        args = ["--storage", "a.db", "code", "--storage", "b.db"]
        assert complete(args, "") == ["b"]


def test_completion_does_not_create_missing_storage():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert complete(["code", "--storage", "typo.db"], "") == []
        assert not os.path.exists("typo.db")


def test_completion_without_storage_returns_nothing(monkeypatch):
    monkeypatch.delenv("TFA_STORAGE")

    assert complete(["code"], "") == []
