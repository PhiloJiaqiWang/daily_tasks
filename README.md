# Planner (Daily Tasks + Rewards)

A floating Tkinter planner focused on daily execution, time tracking, and motivation loops.

## Current Features

### Task + Time Tracking
- Add daily tasks
- Start/Pause timer per task
- Auto-pause other running tasks when starting a new one
- Mark complete with `[ ]` / `[x]`
- Hide/Show completed tasks
- Total tracked time across all tasks

### Task Memo (Per Task Notes)
- Click a task title to open a memo-style editor window
- Notes are saved to that specific task
- `Cmd+S` / `Ctrl+S` support in memo window
- Memo auto-saves on memo close / app close

### Motivation System (Step Goals)
- Daily milestone ladder:
  - `2h`: startup success
  - `5h`: strong progress
  - `6.5h`: full goal
- Dynamic progress text/status based on current milestone
- Full goal (`6.5h`) still triggers celebration flow

### Celebration + Encouragement
- Fireworks popup on first full-goal completion of the day
- Random encouragement message from `encouragements.json`
- Popup can be manually closed

### Card Rewards + Library
- On first daily `6.5h` completion, unlock 1 random non-duplicate card
- Card pool is loaded from `card_pool/`
- Collection state persisted in `cards_state.json`
- Dedicated `Library` window with:
  - masonry/Pinterest-like thumbnail layout
  - responsive column count
  - hover interaction
  - click-to-preview card viewer

### History + Data
- `History` window shows per-day total + task breakdown
- Days that hit `6.5h` show a star (`★`)
- Import/Export `tasks.json` and `history.json`

## Data Files

When running from source (`python app.py`), data is stored in this project folder.

When running packaged app (`Planner.app`), data is stored in:
`~/Library/Application Support/Planner`

Main files:
- `tasks.json`: task list, timer state, task memo content
- `history.json`: per-day tracked time records
- `encouragements.json`: random encouragement text pool
- `cards_state.json`: unlocked cards + per-day card awards
- `card_pool/`: your collectible card image folder

## Requirements

- Python `3.10+` (recommended `3.12`)
- Tkinter available

Optional but recommended:
- Pillow (`pip install pillow`) for broader image format support and better card thumbnail handling

## Run

```bash
/opt/homebrew/bin/python3.12 app.py
```

Or:

```bash
python3 app.py
```

## Card Setup

1. Put card images into `card_pool/`
2. Supported extensions: `.png`, `.gif`, `.jpg`, `.jpeg`, `.bmp`, `.webp`
3. Reach daily `6.5h` to unlock one random new card

## Build macOS App

```bash
python3 -m pip install pyinstaller
./build_macos_app.sh
```

Built app output:
- `dist/Planner.app`

## Update Progress

### Completed
- Base task/timer system
- Daily history + star markers
- 6.5h celebration popup with fireworks
- Custom encouragement file support
- Random non-duplicate card rewards
- Interactive card library (masonry layout + preview)
- Per-task memo editor and persistence
- Step-goal motivation (`2h / 5h / 6.5h`)

### In Progress / Next
- Optional sound effects toggle
- More configurable milestone rewards
- Optional privacy presets for local-only data handling
