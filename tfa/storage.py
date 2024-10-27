import os
from pathlib import Path
import json
import sys


def get_keyfile():
    keyfile = os.environ.get("TFA_STORAGE")
    if not keyfile:
        click.echo("Please define a TFA_STORAGE an envionment variable.")
        exit()

    return Path(keyfile)


def get_storage():
    keyfile = os.environ.get("TFA_STORAGE")
    if not keyfile:
        click.echo("Please define a TFA_STORAGE an envionment variable.")
        exit()

    keypath = Path(keyfile)

    if not keypath.exists():
        return {}

    return json.load(keypath.open("r"))


def get_account(account_name):
    accounts = get_storage()
    try:
        return accounts[account_name]
    except KeyError:
        click.echo(
            f"Account {account_name!r} not found. Available accounts:",
            err=True,
        )
        for account in accounts:
            print(account)
        sys.exit(1)


def save_accounts(accounts):
    json.dump(accounts, get_keyfile().open("w"))
