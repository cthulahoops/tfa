from click.shell_completion import ShellComplete
from click.testing import CliRunner
from tfa.cli import cli, provisioning_uri

import json
import os
import pyotp
import pytest
import qrcode
import re
import sqlite_utils


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
            "testaccount": {
                "issuer": "testaccount",
                "account": None,
                "key": "JBSWY3DPEHPK3PXP",
                "digits": 6,
                "period": 30,
                "algorithm": "SHA1",
            }
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


QR_URI = (
    "otpauth://totp/Example?secret=CHIVQ7QDIO7ZHFKA6BWMIU4BVCIA3AKYJDX2TQQ%3D"
    "&digits=8&issuer=TEST%20DO%20NOT%20USE&algorithm=SHA256&period=240"
)


def write_qr(path, data=QR_URI):
    qrcode.make(data).save(path)


def test_add_from_qr_stores_all_parameters():
    runner = CliRunner()
    with runner.isolated_filesystem():
        write_qr("qr.png")

        result = runner.invoke(cli, ["add", "family", "--qr", "qr.png"])

        assert result.exit_code == 0, result.output
        expected = pyotp.parse_uri(QR_URI).now()
        assert result.output == f"{expected}\n"
        export = json.loads(runner.invoke(cli, ["export"]).output)
        assert export["family"] == {
            "issuer": "TEST DO NOT USE",
            "account": "Example",
            "key": "CHIVQ7QDIO7ZHFKA6BWMIU4BVCIA3AKYJDX2TQQ=",
            "digits": 8,
            "period": 240,
            "algorithm": "SHA256",
        }


def test_code_uses_stored_parameters():
    runner = CliRunner()
    with runner.isolated_filesystem():
        write_qr("qr.png")
        runner.invoke(cli, ["add", "family", "--qr", "qr.png"])

        result = runner.invoke(cli, ["code", "family"])

        assert result.output == f"{pyotp.parse_uri(QR_URI).now()}\n"


def test_add_from_qr_on_stdin():
    runner = CliRunner()
    with runner.isolated_filesystem():
        write_qr("qr.png")
        with open("qr.png", "rb") as f:
            image = f.read()

        result = runner.invoke(cli, ["add", "family", "--qr", "-"], input=image)

        assert result.exit_code == 0, result.output


def test_add_from_qr_issuer_option_wins():
    runner = CliRunner()
    with runner.isolated_filesystem():
        write_qr("qr.png")

        runner.invoke(cli, ["add", "family", "--qr", "qr.png", "--issuer", "Mine"])

        export = json.loads(runner.invoke(cli, ["export"]).output)
        assert export["family"]["issuer"] == "Mine"


def test_add_requires_key_or_qr():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["add", "family"])

        assert result.exit_code == 2
        assert "exactly one of SECRET_KEY or --qr" in result.output


def test_add_rejects_key_and_qr():
    runner = CliRunner()
    with runner.isolated_filesystem():
        write_qr("qr.png")

        result = runner.invoke(
            cli, ["add", "family", "JBSWY3DPEHPK3PXP", "--qr", "qr.png"]
        )

        assert result.exit_code == 2


def test_add_from_qr_without_otpauth_uri():
    runner = CliRunner()
    with runner.isolated_filesystem():
        write_qr("qr.png", "https://example.com")

        result = runner.invoke(cli, ["add", "family", "--qr", "qr.png"])

        assert result.exit_code == 1
        assert "No otpauth QR code found" in result.output


def test_add_from_qr_not_an_image():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("qr.png", "w") as f:
            f.write("not an image")

        result = runner.invoke(cli, ["add", "family", "--qr", "qr.png"])

        assert result.exit_code == 1
        assert "not a readable image" in result.output


def test_qr_round_trips_parameters():
    runner = CliRunner()
    with runner.isolated_filesystem():
        write_qr("in.png")
        runner.invoke(cli, ["add", "family", "--qr", "in.png"])
        account = json.loads(runner.invoke(cli, ["export"]).output)["family"]

        uri = provisioning_uri("family", account)
        assert uri.startswith("otpauth://totp/TEST%20DO%20NOT%20USE:Example?")
        assert "period=240" in uri
        assert "digits=8" in uri
        assert "algorithm=SHA256" in uri


def test_add_from_qr_keeps_label_account():
    runner = CliRunner()
    with runner.isolated_filesystem():
        write_qr(
            "qr.png",
            "otpauth://totp/GitHub:adam%40example.com?secret=JBSWY3DPEHPK3PXP"
            "&issuer=GitHub",
        )
        runner.invoke(cli, ["add", "github", "--qr", "qr.png"])

        account = json.loads(runner.invoke(cli, ["export"]).output)["github"]

        assert account["account"] == "adam@example.com"
        assert provisioning_uri("github", account).startswith(
            "otpauth://totp/GitHub:adam%40example.com?"
        )


@pytest.mark.parametrize("label", ["GitHub:", "", "GitHub:%20%20adam"], ids=repr)
def test_add_from_qr_label_account_edge_cases(label):
    runner = CliRunner()
    with runner.isolated_filesystem():
        write_qr("qr.png", f"otpauth://totp/{label}?secret=JBSWY3DPEHPK3PXP")
        runner.invoke(cli, ["add", "github", "--qr", "qr.png"])

        account = json.loads(runner.invoke(cli, ["export"]).output)["github"]

        assert account["account"] == ("adam" if "adam" in label else None)


def test_add_account_option_wins_over_qr_label():
    runner = CliRunner()
    with runner.isolated_filesystem():
        write_qr("qr.png")

        runner.invoke(cli, ["add", "family", "--qr", "qr.png", "--account", "me"])

        export = json.loads(runner.invoke(cli, ["export"]).output)
        assert export["family"]["account"] == "me"


def test_add_with_secret_and_account():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(
            cli,
            [
                "add",
                "github",
                "JBSWY3DPEHPK3PXP",
                "--issuer",
                "GitHub",
                "--account",
                "a@b.c",
            ],
        )

        account = json.loads(runner.invoke(cli, ["export"]).output)["github"]

        assert provisioning_uri("github", account).startswith(
            "otpauth://totp/GitHub:a%40b.c?"
        )


def test_qr_label_falls_back_to_account_name():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["add", "github", "JBSWY3DPEHPK3PXP", "--issuer", "GitHub"])

        account = json.loads(runner.invoke(cli, ["export"]).output)["github"]

        assert account["account"] is None
        assert provisioning_uri("github", account).startswith(
            "otpauth://totp/GitHub:github?"
        )


def test_import_keeps_label_account():
    runner = CliRunner()
    with runner.isolated_filesystem():
        payload = json.dumps({"github": {"key": "JBSWY3DPEHPK3PXP", "account": "me"}})

        runner.invoke(cli, ["import", "-"], input=payload)

        export = json.loads(runner.invoke(cli, ["export"]).output)
        assert export["github"]["account"] == "me"


def test_add_duplicate_detected_by_name_not_issuer():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["add", "a", "JBSWY3DPEHPK3PXP", "--issuer", "X"])

        result = runner.invoke(cli, ["add", "a", "JBSWY3DPEHPK3PXP", "--issuer", "X"])

        assert result.exit_code == 1
        assert "already exists" in result.output


def test_existing_database_is_migrated():
    runner = CliRunner()
    with runner.isolated_filesystem():
        db = sqlite_utils.Database("old.db")
        db["accounts"].insert(
            {"name": "old", "issuer": "old", "key": "JBSWY3DPEHPK3PXP"}, pk="name"
        )

        result = runner.invoke(cli, ["--storage", "old.db", "code", "old"])

        assert result.exit_code == 0, result.output
        assert result.output == f"{pyotp.TOTP('JBSWY3DPEHPK3PXP').now()}\n"
        assert "account" in db["accounts"].columns_dict


def test_add_from_qr_truncated_image():
    runner = CliRunner()
    with runner.isolated_filesystem():
        write_qr("qr.png")
        with open("qr.png", "rb") as f:
            image = f.read()
        with open("qr.png", "wb") as f:
            f.write(image[: len(image) // 2])

        result = runner.invoke(cli, ["add", "family", "--qr", "qr.png"])

        assert result.exit_code == 1
        assert "not a readable image" in result.output


def test_add_from_qr_zero_period():
    runner = CliRunner()
    with runner.isolated_filesystem():
        write_qr("qr.png", "otpauth://totp/a?secret=JBSWY3DPEHPK3PXP&period=0")

        result = runner.invoke(cli, ["add", "family", "--qr", "qr.png"])

        assert result.exit_code == 1
        assert "period must be a positive integer" in result.output
        assert runner.invoke(cli, ["list"]).output == ""


def test_add_from_qr_rejects_steam():
    runner = CliRunner()
    with runner.isolated_filesystem():
        write_qr("qr.png", "otpauth://totp/a?secret=JBSWY3DPEHPK3PXP&encoder=steam")

        result = runner.invoke(cli, ["add", "family", "--qr", "qr.png"])

        assert result.exit_code == 1
        assert "unsupported encoder" in result.output


def test_add_from_qr_lowercase_algorithm():
    runner = CliRunner()
    with runner.isolated_filesystem():
        write_qr("qr.png", QR_URI.replace("SHA256", "sha256"))

        result = runner.invoke(cli, ["add", "family", "--qr", "qr.png"])

        assert result.exit_code == 0, result.output
        assert result.output == f"{pyotp.parse_uri(QR_URI).now()}\n"


@pytest.mark.parametrize(
    "fields",
    [
        {"digits": "8"},
        {"digits": None},
        {"period": "60"},
        {"period": 0},
        {"period": 30.5},
        {"algorithm": None},
        {"algorithm": 5},
        {"algorithm": "MD5"},
    ],
)
def test_import_skips_invalid_parameters(fields):
    runner = CliRunner()
    with runner.isolated_filesystem():
        payload = json.dumps(
            {
                "bad": {"key": "JBSWY3DPEHPK3PXP", **fields},
                "good": {"key": "JBSWY3DPEHPK3PXP"},
            }
        )

        result = runner.invoke(cli, ["import", "-"], input=payload)

        assert result.exit_code == 0, result.output
        assert "Skipping invalid account: bad" in result.output
        assert runner.invoke(cli, ["list"]).output == "good\n"
