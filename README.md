# TFA CLI Tool

A command-line tool for managing two-factor authentication (2FA) TOTP codes.

## Why did I build this?

* I wanted to understand how TOTP codes work. I don't like trusting access to my accounts to a black box which I don't understand.
* I don't keep my phone with me all the time.
* I'm worried about losing access to my accounts if I lose my phone.

This project succeeded in its main goal: I now have a good understanding of how TOTP codes
work.


## Should you use this?

Maybe? Standard practice is to keep two-factor authentication codes on your phone, not your
computer. This separation is intentional - if someone gains access to your computer, they
still won't have your 2FA codes. By storing codes on your computer with this tool, you're
reducing that security boundary. The security model assumes phones have better protection
against unauthorised access than computers do.

The secret database is not encrypted. Secrets are stored in an sqlite database. You should
keep backups, and probably use the qr code feature to add accounts to an authenticator app.

I'm also not a security expert. I'm just a programmer who wanted to understand TOTP. Maybe you
should use a standard tool instead.

Use at your own risk.

## Installation

```bash
uv tool install tfa
```

or

```bash
pip install tfa
```

There is no default location for the database because the point is to make secret management
less opaque than typical authentication apps. You must explicitly choose where to store your
secrets by setting a path in your shell configuration:

```bash
export TFA_STORAGE=~/.config/tfa/accounts.db
```

If TFA_STORAGE is not set, the tool will display an error message and exit.

## Migrating from JSON

If you're upgrading from a previous version that used JSON storage, TFA will automatically
detect this and provide migration instructions. To migrate your accounts:

```bash
tfa import ~/.config/tfa/accounts.json
export TFA_STORAGE=~/.config/tfa/accounts.db
```

After verifying that all your accounts were successfully migrated, you can safely remove the
old JSON file.

## Usage

### Add a new account
```bash
tfa add <account_name> <secret_key>

# With custom issuer name
tfa add <account_name> <secret_key> --issuer "Custom Name"

# Force overwrite existing account
tfa add <account_name> <secret_key> -f
```

### Get TOTP code
```bash
tfa code <account_name>
```

### List accounts
```bash
tfa list
```

### Remove account
```bash
tfa remove <account_name>
```

### Generate QR Code
Generate a QR code to scan with other authenticator apps:

```bash
tfa qr <account_name>
```

### Import/Export Accounts

Export accounts to JSON (useful for backups):

```bash
# Export to a file
tfa export backup.json

# Export to stdout
tfa export
```

Import accounts from JSON:

```bash
# Import accounts
tfa import backup.json

# Force overwrite existing accounts
tfa import backup.json --force
```

## Examples

```bash
# Add a new GitHub account
tfa add github JBSWY3DPEHPK3PXP --issuer "GitHub"

# Get current code
tfa code github
# Output: GitHub: 123456

# List all accounts
tfa list
# Output: github

# Generate QR code
tfa qr github
```
