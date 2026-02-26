# Global Install

Goal: make `runllm` executable from any directory.

## Recommended

Use `pipx`, which installs CLI tools in isolated environments and exposes commands globally.

```bash
pipx install runllm
```

If you are in this repo and want to test local code globally:

```bash
pipx install --editable .
```

If you want to install only the current local snapshot (not live-editable), use:

```bash
pipx install .
```

## Alternative

Install with user site packages:

```bash
python -m pip install --user runllm
```

Then ensure your user scripts directory is on `PATH`.

## PATH quick checks

macOS/Linux:

```bash
which runllm
```

Windows PowerShell:

```powershell
Get-Command runllm
```

If command is missing, restart your shell after install and verify PATH includes your Python scripts directory.
