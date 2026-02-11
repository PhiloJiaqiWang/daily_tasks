# Daily Tasks Widget

A floating desktop task widget (Tkinter) for macOS-focused daily planning with per-task timing and history tracking.

## Features

- Add tasks for the day
- Mark tasks complete with strikethrough (`[ ]` / `[x]`)
- Start/Pause per-task timer (manual start; add does not auto-start)
- Auto-pause other running tasks when starting a new one
- Total accumulated time across all tasks
- Daily history view (`History` button):
  - total time per day
  - task-level time distribution per day
- Toggle completed task visibility (`Hide Done` / `Show Done`)
- Floating widget behavior:
  - always on top
  - semi-transparent
- Monet-inspired custom UI theme

## Data Files

The app stores data in the project folder:

- `tasks.json`: current task list and live timer state
- `history.json`: historical time records by date

## Requirements

- Python 3.10+ (recommended: Python 3.12)
- Tkinter available in your Python environment

For macOS, if your default Python has old Tk (for example Tk 8.5), use Homebrew Python:

```bash
brew install python@3.12 python-tk@3.12
```

Then run with:

```bash
/opt/homebrew/bin/python3.12 app.py
```

If your `python3` already points to a modern Tk build, this also works:

```bash
python3 app.py
```

## Usage

1. Type a task and click `Add` (or press Enter).
2. Click `Start` to begin timing that task.
3. Click `Pause` to stop timing.
4. Click `[ ]` to mark completed (timer stops and task is struck through).
5. Click `History` to view day-by-day breakdown.
6. Click `Hide Done` to hide completed tasks, and `Show Done` to reveal them.

## Build macOS App (Dock Icon)

To change the Dock icon from the default Python icon to your planner icon:

1. Put your icon image in this folder as `planner_icon.png`.
2. Install PyInstaller:

```bash
python3 -m pip install pyinstaller
```

3. Build the app:

```bash
./build_macos_app.sh
```

4. Open `dist/Planner.app` (this app uses your custom Dock icon).

## Notes

- Timing is accumulated (pause/resume does not reset).
- History is persisted even if completed tasks are removed from the current list.
- On app close, running tasks are paused and saved.
