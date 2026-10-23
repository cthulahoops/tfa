import binascii
import click
import hashlib
import json
import os
import pyotp
import qrcode
import sys
import zxingcpp

from pathlib import Path
from PIL import Image, UnidentifiedImageError

from .storage import AccountStorage, DEFAULTS
from importlib.metadata import version

try:
    __version__ = version("tfa")
except ImportError:
    __version__ = "unknown"


def storage_option(function):
    return click.option(
        "--storage",
        type=click.Path(dir_okay=False, path_type=Path),
        help="Path to the account database. Overrides TFA_STORAGE.",
    )(function)


def get_storage_path(ctx, storage_path=None):
    if storage_path is not None:
        return storage_path

    # Check the subcommand's --storage, then the group's. Uses params rather
    # than ctx.obj because group callbacks don't run during shell completion.
    while ctx is not None:
        if ctx.params.get("storage") is not None:
            return ctx.params["storage"]
        ctx = ctx.parent

    env_storage = os.environ.get("TFA_STORAGE")
    if env_storage:
        return Path(env_storage)

    raise click.ClickException(
        "TFA_STORAGE environment variable not set. Set it to the path where you "
        "want to store your TOTP secrets, or pass --storage. Example: "
        "export TFA_STORAGE=~/.config/tfa/accounts.db"
    )


def get_storage(ctx, storage_path=None):
    return AccountStorage(get_storage_path(ctx, storage_path))


def make_totp(account):
    algorithm = account.get("algorithm", DEFAULTS["algorithm"])
    if algorithm.upper() not in ("SHA1", "SHA256", "SHA512"):
        raise ValueError(f"Unsupported algorithm: {algorithm}")
    return pyotp.TOTP(
        account["key"],
        digits=account.get("digits", DEFAULTS["digits"]),
        interval=account.get("period", DEFAULTS["period"]),
        digest=getattr(hashlib, algorithm.lower()),
    )


def read_qr(image_file):
    """Read an otpauth:// QR code image and return (account, issuer)."""
    try:
        image = Image.open(image_file)
    except UnidentifiedImageError:
        raise click.ClickException(f"{image_file.name} is not a recognised image.")

    uris = [
        result.text
        for result in zxingcpp.read_barcodes(image)
        if result.text.startswith("otpauth://")
    ]
    if not uris:
        raise click.ClickException(f"No otpauth QR code found in {image_file.name}.")
    if len(uris) > 1:
        raise click.ClickException(f"Multiple QR codes found in {image_file.name}.")

    try:
        otp = pyotp.parse_uri(uris[0])
    except ValueError as error:
        raise click.ClickException(f"Invalid otpauth URI: {error}")
    if not isinstance(otp, pyotp.TOTP):
        raise click.ClickException("Only TOTP QR codes are supported.")

    account = {
        "key": otp.secret,
        "digits": otp.digits,
        "period": otp.interval,
        "algorithm": otp.digest().name.upper(),
    }
    return account, otp.issuer


def complete_account_name(ctx, param, incomplete):
    try:
        path = get_storage_path(ctx)
    except click.ClickException:
        return []
    # Don't create an empty database for a mistyped --storage path. A .json
    # path is stored in its .db sibling (see AccountStorage).
    if not path.exists() and not path.with_suffix(".db").exists():
        return []
    return [k for k in AccountStorage(path) if k.startswith(incomplete)]


@click.group()
@click.version_option(version=__version__)
@storage_option
def cli(storage):
    pass


@cli.command(help="Show a TOTP code for a given account.")
@click.argument("account_name", shell_complete=complete_account_name)
@storage_option
@click.pass_context
def code(ctx, account_name, storage):
    storage = get_storage(ctx, storage)
    try:
        account = storage[account_name]
    except KeyError:
        click.echo(f"Account {account_name!r} does not exist.")
        sys.exit(1)
    click.echo(f"{make_totp(account).now()}")


@cli.command(
    help=(
        "Add a new account from SECRET_KEY, or from a QR code image with --qr "
        "(use '-' to read the image from stdin)."
    ),
    name="add",
)
@click.argument("account_name")
@click.argument("secret_key", required=False)
@click.option(
    "--qr",
    "qr_image",
    type=click.File("rb"),
    help="Read the account from an otpauth:// QR code image.",
)
@click.option(
    "--issuer",
)
@click.option("--force", "-f", is_flag=True)
@storage_option
@click.pass_context
def add_account(
    ctx, account_name, secret_key, qr_image=None, issuer=None, force=False, storage=None
):
    if (secret_key is None) == (qr_image is None):
        raise click.UsageError("Provide exactly one of SECRET_KEY or --qr.")

    if qr_image is not None:
        account, qr_issuer = read_qr(qr_image)
    else:
        account, qr_issuer = {"key": secret_key, **DEFAULTS}, None
    account["issuer"] = issuer or qr_issuer or account_name

    accounts = get_storage(ctx, storage)
    if account_name in accounts and not force:
        click.echo(
            f"Account {account_name!r} already exists. Use --force to overwrite."
        )
        sys.exit(1)
    try:
        initial_code = make_totp(account).now()
        click.echo(f"{initial_code}")
    except binascii.Error as error:
        click.echo(f"Invalid secret key: {error}")
        sys.exit(1)

    accounts[account_name] = account


@cli.command(help="Remove an account.", name="remove")
@click.argument("account_name", shell_complete=complete_account_name)
@storage_option
@click.pass_context
def remove_account(ctx, account_name, storage):
    accounts = get_storage(ctx, storage)
    try:
        del accounts[account_name]
    except KeyError:
        click.echo(f"Account {account_name!r} does not exist.")
        sys.exit(1)


@cli.command(help="List all accounts.", name="list")
@storage_option
@click.pass_context
def list_accounts(ctx, storage):
    for name in get_storage(ctx, storage):
        click.echo(name)


@cli.command(help="Display a QR code for an account.")
@click.argument("account_name", shell_complete=complete_account_name)
@storage_option
@click.pass_context
def qr(ctx, account_name, storage):
    storage = get_storage(ctx, storage)
    try:
        account = storage[account_name]
    except KeyError:
        click.echo(f"Account {account_name!r} does not exist.")
        sys.exit(1)

    url = make_totp(account).provisioning_uri(issuer_name=account["issuer"])
    qr = qrcode.QRCode()
    qr.add_data(url)
    qr.print_ascii()


@cli.command(
    help=(
        "Import accounts from FILE, or from stdin when FILE is '-'. Adds accounts; "
        "use --force to replace existing accounts."
    ),
    name="import",
)
@click.argument(
    "json_file", metavar="FILE", type=click.Path(dir_okay=False, path_type=Path)
)
@click.option("--force", "-f", is_flag=True, help="Replace existing accounts")
@storage_option
@click.pass_context
def import_accounts(ctx, json_file, force, storage):
    """Import accounts from a JSON file into the TFA database."""
    try:
        if str(json_file) == "-":
            json_accounts = json.load(sys.stdin)
        else:
            with json_file.open("r") as f:
                json_accounts = json.load(f)

        storage = get_storage(ctx, storage)

        imported = 0
        skipped = 0

        for name, details in json_accounts.items():
            if name in storage and not force:
                click.echo(f"Skipping existing account: {name}")
                skipped += 1
                continue

            # Validate the account data
            if not isinstance(details, dict) or "key" not in details:
                click.echo(f"Skipping invalid account data for: {name}")
                skipped += 1
                continue

            if "issuer" not in details:
                details["issuer"] = name

            try:
                make_totp(details).now()
            except (binascii.Error, ValueError) as e:
                click.echo(f"Skipping account with invalid key: {name} ({e})")
                skipped += 1
                continue

            storage[name] = details
            imported += 1

        click.echo(f"Import complete: {imported} accounts imported, {skipped} skipped.")

    except json.JSONDecodeError:
        click.echo(f"Error: {json_file} is not a valid JSON file.", err=True)
        sys.exit(1)
    except PermissionError:
        click.echo(f"Error: Permission denied when reading {json_file}", err=True)
        sys.exit(1)
    except FileNotFoundError:
        click.echo(f"Error: File {json_file} not found", err=True)
        sys.exit(1)
    except IOError as e:
        click.echo(f"I/O error when reading {json_file}: {e}", err=True)
        sys.exit(1)


@cli.command(
    help="Export accounts to FILE, or to stdout when FILE is omitted or '-'.",
    name="export",
)
@click.argument(
    "json_file",
    metavar="FILE",
    type=click.Path(dir_okay=False, path_type=Path),
    required=False,
)
@click.option("--force", "-f", is_flag=True, help="Overwrite existing file")
@storage_option
@click.pass_context
def export_accounts(ctx, json_file, force, storage):
    """Export accounts from the TFA database to a JSON file or stdout."""
    storage = get_storage(ctx, storage)
    accounts = {}

    for name in storage:
        accounts[name] = storage[name]

    if not accounts:
        click.echo("No accounts to export.")
        return

    if not json_file or str(json_file) == "-":
        click.echo(json.dumps(accounts, indent=2))
        return

    if json_file.exists() and not force:
        click.echo(
            f"File {json_file} already exists. Use --force to overwrite.", err=True
        )
        sys.exit(1)

    try:
        with json_file.open("w") as f:
            json.dump(accounts, f, indent=2)

        click.echo(f"Successfully exported {len(accounts)} accounts to {json_file}")

    except PermissionError:
        click.echo(f"Error: Permission denied when writing to {json_file}", err=True)
        sys.exit(1)
    except IOError as e:
        click.echo(f"I/O error when writing to {json_file}: {e}", err=True)
        sys.exit(1)


@cli.command(help="Show instructions for enabling shell completion")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]), default="bash")
def completion(shell):
    """Show instructions for enabling shell completion for tfa."""
    click.echo(f"# To enable {shell} completion for tfa, run the following commands:")

    if shell == "bash":
        click.echo("# Add completion script:")
        click.echo("mkdir -p ~/.local/share/bash-completion/completions/")
        click.echo(
            "_TFA_COMPLETE=bash_source tfa > ~/.local/share/bash-completion/completions/tfa"
        )
        click.echo("")
        click.echo("# Then restart your shell or source the file:")
        click.echo(". ~/.local/share/bash-completion/completions/tfa")
    elif shell == "zsh":
        click.echo("# Add completion script:")
        click.echo("mkdir -p ~/.zfunc")
        click.echo("_TFA_COMPLETE=zsh_source tfa > ~/.zfunc/_tfa")
        click.echo("")
        click.echo("# Add to your ~/.zshrc if not already there:")
        click.echo("fpath+=~/.zfunc")
        click.echo("autoload -Uz compinit && compinit")
    elif shell == "fish":
        click.echo("# Add completion script:")
        click.echo("mkdir -p ~/.config/fish/completions")
        click.echo(
            "_TFA_COMPLETE=fish_source tfa > ~/.config/fish/completions/tfa.fish"
        )
