from click.testing import CliRunner
from tfa.cli import cli

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
