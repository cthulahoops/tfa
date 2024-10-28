import os
from pathlib import Path
import json
import click


class AccountStorage:
    def __init__(self, keyfile=None):
        self.keyfile = keyfile or get_keyfile()
        self.accounts = self._get_accounts()

    def _get_accounts(self):
        if not self.keyfile.exists():
            return {}

        return json.load(self.keyfile.open("r"))

    def _save_accounts(self):
        json.dump(self.accounts, self.keyfile.open("w"))

    def __getitem__(self, account_name):
        return self.accounts[account_name]

    def __setitem__(self, account_name, account):
        self.accounts[account_name] = account
        self._save_accounts()

    def __contains__(self, account_name):
        return account_name in self.accounts

    def __delitem__(self, account_name):
        del self.accounts[account_name]
        self._save_accounts()

    def __iter__(self):
        return iter(self.accounts)


def get_keyfile():
    keyfile = os.environ.get("TFA_STORAGE")
    if not keyfile:
        click.echo("Please define a TFA_STORAGE an envionment variable.")
        exit()

    return Path(keyfile)
