import click
import sqlite_utils

DEFAULTS = {"digits": 6, "period": 30, "algorithm": "SHA1"}


class AccountStorage:
    def __init__(self, keyfile):
        self.keyfile = keyfile

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
                {
                    "name": str,
                    "issuer": str,
                    "account": str,
                    "key": str,
                    "digits": int,
                    "period": int,
                    "algorithm": str,
                },
                pk="name",
            )
        else:
            columns = self.db["accounts"].columns_dict
            if "account" not in columns:
                self.db["accounts"].add_column("account", str)
            for column, default in DEFAULTS.items():
                if column not in columns:
                    self.db["accounts"].add_column(column, type(default))

    def __getitem__(self, account_name):
        try:
            account = self.db["accounts"].get(account_name)
        except sqlite_utils.db.NotFoundError:
            raise KeyError(account_name)
        return {
            "issuer": account["issuer"],
            "account": account["account"],
            "key": account["key"],
            **{
                column: account[column] if account[column] is not None else default
                for column, default in DEFAULTS.items()
            },
        }

    def __setitem__(self, account_name, account):
        self.db["accounts"].upsert(
            {
                "name": account_name,
                "issuer": account["issuer"],
                "account": account.get("account"),
                "key": account["key"],
                **{
                    column: account.get(column, default)
                    for column, default in DEFAULTS.items()
                },
            },
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
