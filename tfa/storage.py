import os
from pathlib import Path
import click
import sqlite_utils


class AccountStorage:
    def __init__(self, keyfile=None):
        self.keyfile = keyfile or get_keyfile()

        if self.keyfile.suffix == ".json":
            self.db_path = self.keyfile.with_suffix(".db")

            if self.keyfile.exists():
                click.echo(
                    "Notice: Transitioning from JSON to SQLite database format.",
                    err=True,
                )
                click.echo(f"Your data will be stored in: {self.db_path}", err=True)
                click.echo("To migrate existing accounts, run:", err=True)
                click.echo(f"  tfa import {self.keyfile}", err=True)
                click.echo(
                    f"You can then safely remove {self.keyfile} after verifying the migration.",
                    err=True,
                )
                click.echo(
                    f"You should also update your TFA_STORAGE environment variable to {self.db_path}",
                    err=True,
                )
        else:
            self.db_path = self.keyfile

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite_utils.Database(self.db_path)

        if "accounts" not in self.db.table_names():
            self.db["accounts"].create(
                {"name": str, "issuer": str, "key": str}, pk="name"
            )

    def __getitem__(self, account_name):
        try:
            account = self.db["accounts"].get(account_name)
        except sqlite_utils.db.NotFoundError:
            raise KeyError(account_name)
        return {"issuer": account["issuer"], "key": account["key"]}

    def __setitem__(self, account_name, account):
        self.db["accounts"].upsert(
            {"name": account_name, "issuer": account["issuer"], "key": account["key"]},
            pk="name",
        )

    def __contains__(self, account_name):
        try:
            return self.db["accounts"].get(account_name)
        except sqlite_utils.db.NotFoundError:
            return False

    def __delitem__(self, account_name):
        if account_name not in self:
            raise KeyError(account_name)
        self.db["accounts"].delete(account_name)

    def __iter__(self):
        return (row["name"] for row in self.db["accounts"].rows)


def get_keyfile():
    keyfile = os.environ.get("TFA_STORAGE")
    if not keyfile:
        click.echo("Error: TFA_STORAGE environment variable not set.", err=True)
        click.echo(
            "Please set it to the path where you want to store your TOTP secrets:",
            err=True,
        )
        click.echo("  export TFA_STORAGE=~/.config/tfa/accounts.db", err=True)

    return Path(keyfile)
