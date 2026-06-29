# Codex Usage Widget for Mac

This package includes a simple macOS launcher so teammates can run the same widget without touching the Windows scripts.

## How to Run

1. Unzip the whole folder.
2. Double-click `start-mac.command`.
3. If macOS blocks it, right-click `start-mac.command` and choose Open.

The first launch creates a local `.venv` folder and installs Pillow. Later launches are faster.

## Requirements

- Codex has been installed and used at least once on this Mac.
- `python3` is available.

## Data

The widget reads local files under `~/.codex` and displays:

- 5-hour remaining quota
- 7-day remaining quota

It does not upload data and does not display conversation content.

## Quit

Click the top-right close button, or right-click the widget and choose quit.
