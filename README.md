# ag-tokens-inspector

A command line tool that scans your local machine and reports how many tokens
[Antigravity](https://antigravity.google) has consumed.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- Antigravity (CLI and/or IDE) with existing conversations on this machine

## Installation

```bash
uv tool install ag-tokens-inspector
```

To upgrade later:

```bash
uv tool upgrade ag-tokens-inspector
```

To uninstall:

```bash
uv tool uninstall ag-tokens-inspector
```

## Usage

Report the usage of all conversations:

```bash
ag-tokens-inspector
```

Limit the report to a date range (both bounds are inclusive and optional):

```bash
ag-tokens-inspector --from 2026-01-01 --to 2026-01-31
ag-tokens-inspector --from 20260101
ag-tokens-inspector --to 2026/01/31
```

### Options

| Option         | Description                                                            |
| -------------- | ---------------------------------------------------------------------- |
| `--from DATE`  | Start date, inclusive. Formats: `yyyyMMdd`, `yyyy-MM-dd`, `yyyy/MM/dd` |
| `--to DATE`    | End date, inclusive. Same formats as `--from`                          |
| `-h`, `--help` | Show the help message and exit                                         |

`--from` must not be later than `--to`.

## How it works

The tool looks for conversations under your home directory in:

- `~/.gemini/antigravity/conversations`
- `~/.gemini/antigravity-cli/conversations`
- `~/.gemini/antigravity-ide/conversations`
- `~/.antigravity-ide/conversations`

Then it:

1. Reads model call records directly from SQLite (`.db`) conversation databases.
2. For legacy encrypted (`.pb`) conversations that have no `.db`, queries the
   local Antigravity Language Server over RPC.
3. Prints a summary report of token usage.

> [!NOTE]
> Legacy `.pb` conversations can only be included while the Antigravity IDE is
> running. Otherwise they are skipped and a note is printed. Start the IDE and
> rerun the command to include them.
