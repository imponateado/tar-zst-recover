# tar-zst-recover

A Python script to recover files from corrupted `.tar.zst` archives (or files with wrong/corrupted compression headers).

## The problem this solves

You have a `.tar.zst` file that:
- Returns `unsupported format` when you try to decompress it
- Has its magic bytes corrupted (e.g. from using `>>` instead of `>` when creating the archive, appending to an existing file)
- Still has visible `ustar` signatures when inspecting raw bytes — meaning the data is recoverable

## How it works

1. **Scans** the entire file in 1MB chunks looking for `ustar`, `zstd` and `gzip` signatures — without loading the file into RAM
2. **Tests** each `ustar` occurrence with multiple byte offsets (since `ustar` sits at byte 257 of a tar header block, not at byte 0)
3. **Extracts** in a loop: when tar hits a corrupted block and stops, the script finds the next valid `ustar` and resumes from there — recovering as many files as possible

## Usage

Place the script in the same directory as your corrupted file and edit the filename at the top:

```python
FILE = "homebkp.tar.zst"  # change to your filename
```

Then run:

```bash
python3 recover.py
```

The script will:
- Scan the file and report found signatures
- Test offset combinations automatically
- Ask for confirmation before extracting
- Save everything to `~/recovered/`
- Write a full log to `~/recovered/extract.log`

## Requirements

- Python 3.6+
- `tar` and `dd` (standard on Linux/macOS)
- `zstd` (only needed if the file actually contains a valid zstd stream)

## Origin

This script was born from a real recovery session where a `.tar.zst` backup was corrupted because it was created with `>>` (append) instead of `>`, prepending unrelated data before the actual zstd stream. The recovery process was figured out step by step by inspecting raw bytes and testing offset combinations until the tar data was accessible.

Developed with assistance from [Claude](https://claude.ai).

## License

MIT — see [LICENSE](LICENSE).
