import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import time
from datetime import datetime, timedelta
import sys
import random
import math

APP_NAME = "Planner"
DAILY_GOAL_SECONDS = int(6.5 * 3600)


def get_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        # Packaged app should persist data in user-space, not inside .app bundle.
        candidate = Path.home() / "Library" / "Application Support" / APP_NAME
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            pass
    return Path(__file__).resolve().parent


DATA_DIR = get_data_dir()
DATA_FILE = DATA_DIR / "tasks.json"
HISTORY_FILE = DATA_DIR / "history.json"
ENCOURAGEMENTS_FILE = DATA_DIR / "encouragements.json"
CARDS_DIR = DATA_DIR / "card_pool"
CARDS_STATE_FILE = DATA_DIR / "cards_state.json"
ICON_FILE = Path(__file__).with_name("planner_icon.png")


class FloatingTaskWidget:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Daily Tasks")
        self.root.geometry("440x560+100+80")
        self.root.minsize(360, 380)

        # Monet-inspired palette: soft water/sky/flower tones.
        self.bg = "#edf5f3"
        self.panel = "#f9f4ee"
        self.text = "#425165"
        self.muted = "#7b8898"
        self.accent = "#7aa7c7"
        self.line = "#d8e3df"
        self.soft_blue = "#dce8f1"
        self.soft_rose = "#f2e4e6"
        self.soft_green = "#e2efe7"

        self.root.configure(bg=self.bg)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.92)

        self.tasks: list[dict[str, object]] = []
        self.history: dict[str, dict[str, object]] = {}
        self.encouragements: list[str] = []
        self.card_state: dict[str, object] = {"unlocked": [], "awarded_dates": {}}
        self.card_images_cache: dict[str, tk.PhotoImage] = {}
        self.library_window: tk.Toplevel | None = None
        self.library_items_frame: tk.Frame | None = None
        self.library_count_label: tk.Label | None = None
        self.library_reflow_job: str | None = None
        self.preview_window: tk.Toplevel | None = None
        self.task_time_labels: dict[int, tk.Label] = {}
        self.timer_job: str | None = None
        self.show_completed = True
        self.goal_reached_today = False
        self.last_goal_date = datetime.now().strftime("%Y-%m-%d")
        self.celebration_window: tk.Toplevel | None = None
        self.firework_canvas: tk.Canvas | None = None
        self.firework_job: str | None = None
        self.firework_particles: list[dict[str, object]] = []
        self.firework_tick = 0
        self.icon_image: tk.PhotoImage | None = None
        self.default_font = ("TkDefaultFont", 11)
        self.done_font = ("TkDefaultFont", 11, "overstrike")
        self.set_app_icon()

        container = tk.Frame(self.root, bg=self.bg, padx=10, pady=10)
        container.pack(fill="both", expand=True)

        title = tk.Label(container, text="Daily Tasks", bg=self.bg, fg=self.text, font=("TkDefaultFont", 15, "bold"))
        title.pack(anchor="w", pady=(0, 6))

        input_row = tk.Frame(container, bg=self.bg)
        input_row.pack(fill="x", pady=(0, 6))

        self.task_var = tk.StringVar()
        self.entry = tk.Entry(
            input_row,
            textvariable=self.task_var,
            font=self.default_font,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=self.line,
            highlightcolor=self.accent,
            bg="#fdf9f3",
            fg=self.text,
            insertbackground=self.text,
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=5)
        self.entry.bind("<Return>", lambda _event: self.add_task())

        add_btn = tk.Button(
            input_row,
            text="Add",
            command=self.add_task,
            padx=12,
            relief="flat",
            bd=0,
            bg="#4b6f8e",
            fg=self.text,
            activebackground="#3e5f7a",
            activeforeground=self.text,
        )
        add_btn.pack(side="left", padx=(8, 0))

        hint = tk.Label(container, text="Enter to add. Click [ ] to complete.", bg=self.bg, fg=self.muted)
        hint.pack(anchor="w", pady=(0, 6))

        self.total_time_label = tk.Label(
            container,
            text="Total: 00:00:00",
            bg=self.bg,
            fg=self.text,
            font=("TkDefaultFont", 10, "bold"),
        )
        self.total_time_label.pack(anchor="w", pady=(0, 6))

        self.today_progress_label = tk.Label(
            container,
            text=f"Today: 00:00:00 / {self.format_seconds(DAILY_GOAL_SECONDS)}",
            bg=self.bg,
            fg=self.muted,
            font=("TkDefaultFont", 10),
        )
        self.today_progress_label.pack(anchor="w", pady=(0, 2))

        self.goal_message_label = tk.Label(
            container,
            text="Keep going. Goal is 6.5 hours today.",
            bg=self.bg,
            fg=self.muted,
            font=("TkDefaultFont", 10, "italic"),
            anchor="w",
            justify="left",
        )
        self.goal_message_label.pack(fill="x", pady=(0, 6))

        self.list_area = tk.Frame(container, bg=self.panel, relief="flat", bd=0)
        self.list_area.pack(fill="both", expand=True)
        self.list_canvas = tk.Canvas(
            self.list_area,
            bg=self.panel,
            highlightthickness=0,
            bd=0,
            relief="flat",
        )
        self.list_scrollbar = tk.Scrollbar(self.list_area, orient="vertical", command=self.list_canvas.yview)
        self.list_canvas.configure(yscrollcommand=self.list_scrollbar.set)
        self.list_canvas.pack(side="left", fill="both", expand=True)
        self.list_scrollbar.pack(side="right", fill="y")

        self.list_container = tk.Frame(self.list_canvas, bg=self.panel, relief="flat", bd=0)
        self.list_canvas_window = self.list_canvas.create_window((0, 0), window=self.list_container, anchor="nw")
        self.list_container.bind("<Configure>", self._on_task_frame_configure)
        self.list_canvas.bind("<Configure>", self._on_task_canvas_configure)
        self.list_area.bind("<Enter>", self._bind_task_scroll)
        self.list_area.bind("<Leave>", self._unbind_task_scroll)
        self.list_canvas.bind("<Enter>", self._bind_task_scroll)
        self.list_canvas.bind("<Leave>", self._unbind_task_scroll)

        self.status = tk.Label(container, text="Ready", bg=self.bg, fg=self.muted, anchor="w", font=("TkDefaultFont", 10))
        self.status.pack(fill="x", pady=(6, 6))

        footer = tk.Frame(container, bg=self.bg)
        footer.pack(fill="x")

        footer_row1 = tk.Frame(footer, bg=self.bg)
        footer_row1.pack(fill="x")

        footer_row2 = tk.Frame(footer, bg=self.bg)
        footer_row2.pack(fill="x", pady=(6, 0))

        self.toggle_done_btn = tk.Button(
            footer_row1,
            text="Hide Done",
            command=self.toggle_completed_visibility,
            relief="flat",
            bd=0,
            padx=10,
            bg=self.soft_blue,
            fg=self.text,
            activebackground="#ccdce8",
        )
        self.toggle_done_btn.pack(side="left", padx=(8, 0))

        import_btn = tk.Button(
            footer_row2,
            text="Import Data",
            command=self.import_data,
            relief="flat",
            bd=0,
            padx=10,
            bg=self.soft_green,
            fg=self.text,
            activebackground="#d2e3d8",
        )
        import_btn.pack(side="left", padx=(8, 0))

        export_btn = tk.Button(
            footer_row2,
            text="Export Data",
            command=self.export_data,
            relief="flat",
            bd=0,
            padx=10,
            bg=self.soft_blue,
            fg=self.text,
            activebackground="#ccdce8",
        )
        export_btn.pack(side="left", padx=(8, 0))

        history_btn = tk.Button(
            footer_row1,
            text="History",
            command=self.open_history_window,
            relief="flat",
            bd=0,
            padx=10,
            bg=self.soft_rose,
            fg=self.text,
            activebackground="#e8d5d8",
        )
        history_btn.pack(side="left", padx=(8, 0))

        library_btn = tk.Button(
            footer_row1,
            text="Library",
            command=self.open_library_window,
            relief="flat",
            bd=0,
            padx=10,
            bg="#e8f2dc",
            fg=self.text,
            activebackground="#dbeac8",
        )
        library_btn.pack(side="left", padx=(8, 0))

        self.load_tasks()
        self.load_history()
        self.load_encouragements()
        self.ensure_cards_dir()
        self.load_card_state()
        self.render_tasks()
        self.start_timer_loop()
        self.entry.focus_set()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self) -> None:
        for idx, _task in enumerate(self.tasks):
            self.pause_task(idx)
        self.save_tasks()
        self.save_history()
        if self.timer_job is not None:
            self.root.after_cancel(self.timer_job)
            self.timer_job = None
        if self.library_reflow_job is not None:
            self.root.after_cancel(self.library_reflow_job)
            self.library_reflow_job = None
        self.close_preview_window()
        if self.library_window is not None and self.library_window.winfo_exists():
            self.library_window.destroy()
        self.library_window = None
        self.close_celebration_window()
        self._unbind_task_scroll()
        self.root.destroy()

    def set_app_icon(self) -> None:
        if not ICON_FILE.exists():
            return
        try:
            self.icon_image = tk.PhotoImage(file=str(ICON_FILE))
            self.root.iconphoto(True, self.icon_image)
        except tk.TclError:
            self.icon_image = None

    def start_timer_loop(self) -> None:
        self.refresh_timer_labels()
        self.timer_job = self.root.after(1000, self.start_timer_loop)

    def _on_task_frame_configure(self, _event: object = None) -> None:
        self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all"))

    def _on_task_canvas_configure(self, event: tk.Event) -> None:
        self.list_canvas.itemconfigure(self.list_canvas_window, width=event.width)

    def _bind_task_scroll(self, _event: object = None) -> None:
        self.root.bind_all("<MouseWheel>", self._on_task_mousewheel)
        self.root.bind_all("<Button-4>", self._on_task_mousewheel)
        self.root.bind_all("<Button-5>", self._on_task_mousewheel)

    def _unbind_task_scroll(self, _event: object = None) -> None:
        self.root.unbind_all("<MouseWheel>")
        self.root.unbind_all("<Button-4>")
        self.root.unbind_all("<Button-5>")

    def _on_task_mousewheel(self, event: tk.Event) -> None:
        step = 0
        num = getattr(event, "num", None)
        delta = int(getattr(event, "delta", 0))
        if num == 4:
            step = -1
        elif num == 5:
            step = 1
        elif delta != 0:
            if sys.platform == "darwin":
                step = -delta
            else:
                step = -int(delta / 120)
                if step == 0:
                    step = -1 if delta > 0 else 1

        if step != 0:
            self.list_canvas.yview_scroll(step, "units")

    @staticmethod
    def now_ts() -> float:
        return time.time()

    @staticmethod
    def format_seconds(total_seconds: float) -> str:
        total = max(0, int(total_seconds))
        hours = total // 3600
        minutes = (total % 3600) // 60
        seconds = total % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def task_elapsed_seconds(self, task: dict[str, object]) -> float:
        elapsed = float(task.get("elapsed_seconds", 0))
        if not bool(task.get("running", False)):
            return elapsed
        started_at = task.get("started_at")
        if isinstance(started_at, (int, float)):
            elapsed += max(0, self.now_ts() - float(started_at))
        return elapsed

    def refresh_timer_labels(self) -> None:
        total = 0.0
        for idx, task in enumerate(self.tasks):
            elapsed = self.task_elapsed_seconds(task)
            total += elapsed
            label = self.task_time_labels.get(idx)
            if label is not None:
                label.config(text=f"Time: {self.format_seconds(elapsed)}")
        self.total_time_label.config(text=f"Total: {self.format_seconds(total)}")
        self.update_daily_goal_ui()

    def load_tasks(self) -> None:
        if not DATA_FILE.exists():
            self.tasks = []
            return

        try:
            raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            self.tasks = []
            return

        if not isinstance(raw, list):
            self.tasks = []
            return

        cleaned: list[dict[str, object]] = []
        for item in raw:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                txt = item["text"].strip()
                if txt:
                    done = bool(item.get("done", False))
                    elapsed_raw = item.get("elapsed_seconds", 0)
                    started_raw = item.get("started_at")
                    running_raw = item.get("running", False)

                    elapsed_seconds = float(elapsed_raw) if isinstance(elapsed_raw, (int, float)) else 0.0
                    running = bool(running_raw) and not done
                    started_at: float | None = None
                    if running and isinstance(started_raw, (int, float)):
                        started_at = float(started_raw)
                    elif isinstance(started_raw, (int, float)) and not done:
                        # Backward compatible: old data may store active start time without explicit running flag.
                        # Convert it to paused + accumulated elapsed time to avoid auto-running after startup.
                        elapsed_seconds += max(0, self.now_ts() - float(started_raw))
                        started_at = None

                    cleaned.append(
                        {
                            "text": txt,
                            "done": done,
                            "elapsed_seconds": elapsed_seconds,
                            "started_at": started_at,
                            "running": running,
                        }
                    )
        self.tasks = cleaned

    def load_history(self) -> None:
        if not HISTORY_FILE.exists():
            self.history = {}
            return
        try:
            raw = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            self.history = raw if isinstance(raw, dict) else {}
        except (json.JSONDecodeError, OSError):
            self.history = {}

    def load_encouragements(self) -> None:
        default_lines = [
            "你今天的专注很稳，继续保持。",
            "每一分钟投入都在累积优势。",
            "你不是在赶时间，你是在建立能力。",
            "达标是结果，稳定节奏才是核心。",
            "今天的你，已经比昨天更强一点。",
        ]
        if not ENCOURAGEMENTS_FILE.exists():
            self.encouragements = default_lines
            return
        try:
            raw = json.loads(ENCOURAGEMENTS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                lines = [str(item).strip() for item in raw if str(item).strip()]
                self.encouragements = lines if lines else default_lines
                return
        except (json.JSONDecodeError, OSError):
            pass
        self.encouragements = default_lines

    def ensure_cards_dir(self) -> None:
        try:
            CARDS_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

    def load_card_state(self) -> None:
        default_state: dict[str, object] = {"unlocked": [], "awarded_dates": {}}
        if not CARDS_STATE_FILE.exists():
            self.card_state = default_state
            return

        try:
            raw = json.loads(CARDS_STATE_FILE.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                self.card_state = default_state
                return
            unlocked = raw.get("unlocked", [])
            awarded_dates = raw.get("awarded_dates", {})
            if not isinstance(unlocked, list) or not isinstance(awarded_dates, dict):
                self.card_state = default_state
                return
            clean_unlocked = [str(x) for x in unlocked if str(x).strip()]
            clean_awarded_dates: dict[str, str] = {}
            for key, value in awarded_dates.items():
                k = str(key).strip()
                v = str(value).strip()
                if k and v:
                    clean_awarded_dates[k] = v
            self.card_state = {"unlocked": clean_unlocked, "awarded_dates": clean_awarded_dates}
        except (json.JSONDecodeError, OSError):
            self.card_state = default_state

    def save_card_state(self) -> None:
        try:
            CARDS_STATE_FILE.write_text(json.dumps(self.card_state, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def get_card_pool(self) -> list[str]:
        exts = {".png", ".gif", ".jpg", ".jpeg", ".bmp", ".webp"}
        try:
            files = [p.name for p in CARDS_DIR.iterdir() if p.is_file() and p.suffix.lower() in exts]
            return sorted(files)
        except OSError:
            return []

    def award_daily_card(self, date_key: str) -> str:
        pool = self.get_card_pool()
        if not pool:
            return f"Card folder is empty: {CARDS_DIR}"

        unlocked_raw = self.card_state.get("unlocked", [])
        unlocked = {str(x) for x in unlocked_raw if str(x).strip()}
        awarded_dates = self.card_state.get("awarded_dates", {})
        if isinstance(awarded_dates, dict):
            existing = awarded_dates.get(date_key)
            if isinstance(existing, str) and existing.strip():
                return f"Today's card: {existing}"

        remaining = [name for name in pool if name not in unlocked]
        if not remaining:
            if isinstance(awarded_dates, dict):
                awarded_dates[date_key] = "All cards collected"
            self.card_state["awarded_dates"] = awarded_dates
            self.save_card_state()
            self.render_library_cards()
            return "All cards are already collected."

        picked = random.choice(remaining)
        unlocked.add(picked)
        self.card_state["unlocked"] = sorted(unlocked)
        if isinstance(awarded_dates, dict):
            awarded_dates[date_key] = picked
        self.card_state["awarded_dates"] = awarded_dates
        self.save_card_state()
        self.render_library_cards()
        return f"New card unlocked: {picked}"

    def get_today_tracked_seconds(self) -> float:
        now = datetime.now()
        today_key = now.strftime("%Y-%m-%d")
        today_total = float(self.history.get(today_key, {}).get("total_seconds", 0.0))
        day_start_ts = datetime.combine(now.date(), datetime.min.time()).timestamp()
        now_ts = self.now_ts()

        for task in self.tasks:
            if not bool(task.get("running", False)):
                continue
            started_at = task.get("started_at")
            if not isinstance(started_at, (int, float)):
                continue
            active_start = max(float(started_at), day_start_ts)
            today_total += max(0.0, now_ts - active_start)
        return today_total

    def update_daily_goal_ui(self) -> None:
        today_key = datetime.now().strftime("%Y-%m-%d")
        if today_key != self.last_goal_date:
            self.last_goal_date = today_key
            self.goal_reached_today = False
            self.goal_message_label.config(
                text="Keep going. Goal is 6.5 hours today.",
                fg=self.muted,
            )
            self.today_progress_label.config(fg=self.muted)
            self.total_time_label.config(fg=self.text)

        today_seconds = self.get_today_tracked_seconds()
        self.today_progress_label.config(
            text=f"Today: {self.format_seconds(today_seconds)} / {self.format_seconds(DAILY_GOAL_SECONDS)}"
        )

        if today_seconds >= DAILY_GOAL_SECONDS:
            self.today_progress_label.config(fg="#2f7d4f")
            self.total_time_label.config(fg="#2f7d4f")
            if not self.goal_reached_today:
                self.goal_reached_today = True
                message = random.choice(self.encouragements) if self.encouragements else "Great work today."
                self.goal_message_label.config(text=f"Goal reached: {message}", fg="#2f7d4f")
                reward_text = self.award_daily_card(today_key)
                self.open_celebration_window(message, reward_text)
        else:
            self.today_progress_label.config(fg=self.muted)
            self.total_time_label.config(fg=self.text)
            if not self.goal_reached_today:
                remaining = DAILY_GOAL_SECONDS - today_seconds
                self.goal_message_label.config(
                    text=f"Keep going: {self.format_seconds(remaining)} left to reach 6.5h.",
                    fg=self.muted,
                )

    def open_celebration_window(self, message: str, reward_text: str) -> None:
        if self.celebration_window is not None and self.celebration_window.winfo_exists():
            self.celebration_window.lift()
            self.celebration_window.focus_force()
            return

        win = tk.Toplevel(self.root)
        win.title("Goal Reached")
        win.geometry("520x420")
        win.minsize(460, 360)
        win.configure(bg="#0f1a2b")
        self.celebration_window = win

        canvas = tk.Canvas(win, bg="#0f1a2b", highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        self.firework_canvas = canvas

        panel = tk.Frame(win, bg="#1b2b45", padx=12, pady=10)
        panel.pack(fill="x")

        tk.Label(
            panel,
            text="Today Goal Reached (6.5h)",
            bg="#1b2b45",
            fg="#f8d76f",
            font=("TkDefaultFont", 12, "bold"),
        ).pack(anchor="w")

        tk.Label(
            panel,
            text=message,
            bg="#1b2b45",
            fg="#eaf2ff",
            font=("TkDefaultFont", 11),
            wraplength=460,
            justify="left",
        ).pack(anchor="w", pady=(6, 8))

        tk.Label(
            panel,
            text=reward_text,
            bg="#1b2b45",
            fg="#8cf2bc",
            font=("TkDefaultFont", 11, "bold"),
            wraplength=460,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        tk.Button(
            panel,
            text="Close",
            command=self.close_celebration_window,
            relief="flat",
            bd=0,
            padx=12,
            bg="#f0c95a",
            fg="#1f2a3d",
            activebackground="#e0bc56",
        ).pack(anchor="e")

        win.protocol("WM_DELETE_WINDOW", self.close_celebration_window)
        self.start_fireworks()

    def close_celebration_window(self) -> None:
        if self.firework_job is not None:
            self.root.after_cancel(self.firework_job)
            self.firework_job = None
        self.firework_particles = []
        self.firework_canvas = None
        if self.celebration_window is not None and self.celebration_window.winfo_exists():
            self.celebration_window.destroy()
        self.celebration_window = None

    def start_fireworks(self) -> None:
        self.firework_particles = []
        self.firework_tick = 0
        self.animate_fireworks()

    def animate_fireworks(self) -> None:
        canvas = self.firework_canvas
        if canvas is None or not canvas.winfo_exists():
            self.firework_job = None
            return

        self.firework_tick += 1
        if self.firework_tick % 10 == 1:
            self.spawn_firework_burst()
            if random.random() < 0.25:
                self.spawn_firework_burst()

        alive_particles: list[dict[str, object]] = []
        for particle in self.firework_particles:
            life = int(particle["life"]) - 1
            if life <= 0:
                canvas.delete(int(particle["item"]))
                continue

            x = float(particle["x"]) + float(particle["dx"])
            y = float(particle["y"]) + float(particle["dy"])
            dx = float(particle["dx"]) * 0.985
            dy = float(particle["dy"]) + 0.12
            size = max(1.0, float(particle["size"]) * 0.985)
            item = int(particle["item"])
            canvas.coords(item, x - size, y - size, x + size, y + size)

            particle["x"] = x
            particle["y"] = y
            particle["dx"] = dx
            particle["dy"] = dy
            particle["size"] = size
            particle["life"] = life
            alive_particles.append(particle)

        self.firework_particles = alive_particles
        self.firework_job = self.root.after(50, self.animate_fireworks)

    def spawn_firework_burst(self) -> None:
        canvas = self.firework_canvas
        if canvas is None or not canvas.winfo_exists():
            return
        w = max(1, canvas.winfo_width())
        h = max(1, canvas.winfo_height())
        cx = random.randint(int(w * 0.15), int(w * 0.85))
        cy = random.randint(int(h * 0.15), int(h * 0.65))
        colors = ["#ffdb6e", "#ff7fa8", "#7cf7ff", "#8cff9c", "#ffd1f9", "#ff9b5f"]
        for _ in range(34):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(2.0, 6.8)
            size = random.uniform(1.8, 3.8)
            x = float(cx)
            y = float(cy)
            dx = math.cos(angle) * speed
            dy = math.sin(angle) * speed
            color = random.choice(colors)
            item = canvas.create_oval(x - size, y - size, x + size, y + size, fill=color, outline="")
            self.firework_particles.append(
                {
                    "x": x,
                    "y": y,
                    "dx": dx,
                    "dy": dy,
                    "size": size,
                    "life": random.randint(20, 34),
                    "item": item,
                }
            )

    def pause_task(self, idx: int) -> None:
        task = self.tasks[idx]
        if not bool(task.get("running", False)):
            return
        elapsed = float(task.get("elapsed_seconds", 0))
        started_at = task.get("started_at")
        if isinstance(started_at, (int, float)):
            start_ts = float(started_at)
            end_ts = self.now_ts()
            elapsed += max(0, end_ts - start_ts)
            self.add_interval_to_history(start_ts, end_ts, str(task.get("text", "Untitled Task")))
        task["elapsed_seconds"] = elapsed
        task["started_at"] = None
        task["running"] = False

    def add_interval_to_history(self, start_ts: float, end_ts: float, task_text: str) -> None:
        if end_ts <= start_ts:
            return

        cursor = datetime.fromtimestamp(start_ts)
        end_dt = datetime.fromtimestamp(end_ts)

        while cursor < end_dt:
            next_midnight = datetime.combine(cursor.date() + timedelta(days=1), datetime.min.time())
            segment_end = min(next_midnight, end_dt)
            seconds = (segment_end - cursor).total_seconds()
            if seconds > 0:
                date_key = cursor.strftime("%Y-%m-%d")
                day = self.history.setdefault(date_key, {"total_seconds": 0.0, "tasks": {}})
                day["total_seconds"] = float(day.get("total_seconds", 0.0)) + seconds
                tasks = day.setdefault("tasks", {})
                tasks[task_text] = float(tasks.get(task_text, 0.0)) + seconds
            cursor = segment_end

    def pause_all_running_except(self, keep_idx: int) -> None:
        for idx, _task in enumerate(self.tasks):
            if idx != keep_idx:
                self.pause_task(idx)

    def toggle_run_task(self, idx: int) -> None:
        task = self.tasks[idx]
        if bool(task.get("done", False)):
            self.status.config(text="Completed task cannot start. Uncheck first.")
            return

        if bool(task.get("running", False)):
            self.pause_task(idx)
            self.status.config(text=f'Paused: "{task["text"]}"')
        else:
            self.pause_all_running_except(idx)
            task["running"] = True
            task["started_at"] = self.now_ts()
            self.status.config(text=f'Started: "{task["text"]}"')
        self.save_tasks()
        self.save_history()
        self.render_tasks()

    def save_tasks(self) -> None:
        try:
            DATA_FILE.write_text(json.dumps(self.tasks, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def save_history(self) -> None:
        try:
            HISTORY_FILE.write_text(json.dumps(self.history, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def add_task(self) -> None:
        text = self.task_var.get().strip()
        if not text:
            self.status.config(text="Please type a task first.")
            return

        self.tasks.append(
            {
                "text": text,
                "done": False,
                "elapsed_seconds": 0.0,
                "started_at": None,
                "running": False,
            }
        )
        self.task_var.set("")
        self.save_tasks()
        self.render_tasks()
        self.status.config(text=f'Added: "{text}"')

    def toggle_task(self, idx: int) -> None:
        task = self.tasks[idx]
        done = bool(task.get("done", False))

        if done:
            task["done"] = False
            task["running"] = False
            task["started_at"] = None
            self.status.config(text=f'Reopened: "{task["text"]}"')
        else:
            self.pause_task(idx)
            task["done"] = True
            self.status.config(text=f'Completed: "{task["text"]}"')
        self.save_tasks()
        self.save_history()
        self.render_tasks()

    def delete_task(self, idx: int) -> None:
        self.pause_task(idx)
        self.tasks.pop(idx)
        self.save_tasks()
        self.save_history()
        self.render_tasks()

    def toggle_completed_visibility(self) -> None:
        self.show_completed = not self.show_completed
        self.toggle_done_btn.config(text=("Hide Done" if self.show_completed else "Show Done"))
        self.render_tasks()
        self.status.config(text=("Showing completed tasks." if self.show_completed else "Hiding completed tasks."))

    def import_data(self) -> None:
        selected_files = filedialog.askopenfilenames(
            title="Select tasks.json and/or history.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )

        src_tasks: Path | None = None
        src_history: Path | None = None

        for raw_path in selected_files:
            p = Path(raw_path)
            name = p.name.lower()
            if name == "tasks.json":
                src_tasks = p
            elif name == "history.json":
                src_history = p

        if src_tasks is None and src_history is None:
            source_dir = filedialog.askdirectory(title="Or select folder with tasks.json/history.json")
            if not source_dir:
                self.status.config(text="Import cancelled.")
                return
            src = Path(source_dir)
            candidate_tasks = src / "tasks.json"
            candidate_history = src / "history.json"
            if candidate_tasks.exists():
                src_tasks = candidate_tasks
            if candidate_history.exists():
                src_history = candidate_history

        copied: list[str] = []

        try:
            if src_tasks is not None and src_tasks.exists():
                DATA_FILE.write_text(src_tasks.read_text(encoding="utf-8"), encoding="utf-8")
                copied.append("tasks")
            if src_history is not None and src_history.exists():
                HISTORY_FILE.write_text(src_history.read_text(encoding="utf-8"), encoding="utf-8")
                copied.append("history")
        except OSError:
            self.status.config(text="Import failed: file permission error.")
            return

        if not copied:
            self.status.config(text="No tasks.json/history.json found in selected folder.")
            return

        self.load_tasks()
        self.load_history()
        self.load_encouragements()
        self.render_tasks()
        self.status.config(text=f"Imported: {', '.join(copied)}.")

    def export_data(self) -> None:
        target_dir = filedialog.askdirectory(title="Select export folder")
        if not target_dir:
            self.status.config(text="Export cancelled.")
            return

        # Ensure the latest in-memory state is written before export.
        self.save_tasks()
        self.save_history()

        dst = Path(target_dir)
        dst_tasks = dst / "tasks.json"
        dst_history = dst / "history.json"
        exported: list[str] = []

        try:
            if DATA_FILE.exists():
                dst_tasks.write_text(DATA_FILE.read_text(encoding="utf-8"), encoding="utf-8")
                exported.append("tasks")
            if HISTORY_FILE.exists():
                dst_history.write_text(HISTORY_FILE.read_text(encoding="utf-8"), encoding="utf-8")
                exported.append("history")
        except OSError:
            self.status.config(text="Export failed: file permission error.")
            return

        if not exported:
            self.status.config(text="No data files available to export.")
            return

        self.status.config(text=f"Exported: {', '.join(exported)}.")

    def load_card_thumbnail(self, card_name: str, max_w: int, max_h: int) -> tk.PhotoImage | None:
        img_path = CARDS_DIR / card_name
        cache_key = f"{img_path}:{max_w}x{max_h}"
        if cache_key in self.card_images_cache:
            return self.card_images_cache[cache_key]

        img: tk.PhotoImage | None = None
        try:
            from PIL import Image, ImageTk  # type: ignore

            with Image.open(img_path) as pil_img:
                pil_copy = pil_img.copy()
                pil_copy.thumbnail((max_w, max_h))
            img = ImageTk.PhotoImage(pil_copy)
        except Exception:
            try:
                raw = tk.PhotoImage(file=str(img_path))
                w = max(1, raw.width())
                h = max(1, raw.height())
                sx = max(1, math.ceil(w / max_w))
                sy = max(1, math.ceil(h / max_h))
                img = raw.subsample(sx, sy)
            except tk.TclError:
                img = None

        if img is not None:
            self.card_images_cache[cache_key] = img
        return img

    def refresh_library_summary(self) -> None:
        if self.library_count_label is None or not self.library_count_label.winfo_exists():
            return
        pool = self.get_card_pool()
        unlocked_raw = self.card_state.get("unlocked", [])
        unlocked = [x for x in unlocked_raw if isinstance(x, str)]
        owned = len([x for x in unlocked if x in pool])
        total = len(pool)
        self.library_count_label.config(text=f"Collected {owned} / {total}")

    def render_library_cards(self) -> None:
        if self.library_items_frame is None or not self.library_items_frame.winfo_exists():
            return

        frame = self.library_items_frame
        for child in frame.winfo_children():
            child.destroy()

        pool = self.get_card_pool()
        unlocked_raw = self.card_state.get("unlocked", [])
        unlocked = {str(x) for x in unlocked_raw if str(x).strip()}
        ordered = sorted(pool, key=lambda x: (x not in unlocked, x.lower()))

        if not ordered:
            hint = tk.Label(
                frame,
                text=f"No card images yet.\nPut images into:\n{CARDS_DIR}",
                bg="#f6f9ef",
                fg="#5f6f52",
                justify="center",
                padx=16,
                pady=24,
            )
            hint.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")
            self.refresh_library_summary()
            return

        viewport_w = frame.winfo_width()
        if viewport_w <= 0:
            viewport_w = 860
        if viewport_w >= 1180:
            columns = 4
        elif viewport_w >= 820:
            columns = 3
        else:
            columns = 2

        column_frames: list[tk.Frame] = []
        column_heights = [0 for _ in range(columns)]
        for i in range(columns):
            frame.grid_columnconfigure(i, weight=1, uniform="libcol")
            col = tk.Frame(frame, bg="#f6f9ef")
            col.grid(row=0, column=i, sticky="n", padx=6)
            column_frames.append(col)

        thumb_w = 220

        for idx, card_name in enumerate(ordered):
            owned = card_name in unlocked

            target_col = min(range(columns), key=lambda i: column_heights[i])
            parent_col = column_frames[target_col]
            card = tk.Frame(
                parent_col,
                bg=("#fffdf4" if owned else "#ececec"),
                highlightthickness=1,
                highlightbackground=("#e7d78f" if owned else "#d4d4d4"),
                bd=0,
                padx=8,
                pady=8,
                cursor=("hand2" if owned else "arrow"),
            )
            card.pack(fill="x", pady=8)

            if owned:
                # Keep original aspect ratio to create a Pinterest-like masonry wall.
                thumb = self.load_card_thumbnail(card_name, thumb_w, 360)
            else:
                thumb = None

            if thumb is not None and owned:
                img_label = tk.Label(card, image=thumb, bg="#fffdf4")
                img_label.image = thumb
                img_label.pack(anchor="center")
                preview_h = max(120, thumb.height())
            else:
                placeholder = tk.Canvas(
                    card,
                    width=thumb_w,
                    height=140,
                    bg=("#f8f1ce" if owned else "#d7d7d7"),
                    highlightthickness=0,
                    bd=0,
                )
                placeholder.create_text(
                    100,
                    65,
                    text=("Preview unavailable" if owned else "Locked"),
                    fill=("#6a613f" if owned else "#777777"),
                    font=("TkDefaultFont", 11, "bold"),
                )
                placeholder.pack(anchor="center")
                preview_h = 140

            name_label = tk.Label(
                card,
                text=card_name,
                bg=("#fffdf4" if owned else "#ececec"),
                fg=("#3f4f63" if owned else "#777777"),
                anchor="w",
                wraplength=thumb_w - 10,
                justify="left",
                font=("TkDefaultFont", 10, "bold"),
            )
            name_label.pack(fill="x", pady=(8, 2))

            state_label = tk.Label(
                card,
                text=("Collected" if owned else "Not collected"),
                bg=("#f8edbd" if owned else "#dedede"),
                fg=("#5a4f1c" if owned else "#666666"),
                padx=6,
                pady=2,
                font=("TkDefaultFont", 9),
            )
            state_label.pack(anchor="w")

            column_heights[target_col] += preview_h + 88

            if owned:
                hover_bg = "#f9f2d5"
                normal_bg = "#fffdf4"

                def on_enter(_event: object, c=card, n=name_label) -> None:
                    c.config(bg=hover_bg, highlightbackground="#d8c270")
                    n.config(bg=hover_bg)

                def on_leave(_event: object, c=card, n=name_label) -> None:
                    c.config(bg=normal_bg, highlightbackground="#e7d78f")
                    n.config(bg=normal_bg)

                def on_click(_event: object, name=card_name) -> None:
                    self.open_card_preview(name)

                bind_widgets: list[tk.Widget] = [card, name_label, state_label]
                if thumb is not None:
                    bind_widgets.append(img_label)
                else:
                    bind_widgets.append(placeholder)
                for widget in bind_widgets:
                    widget.bind("<Enter>", on_enter)
                    widget.bind("<Leave>", on_leave)
                    widget.bind("<Button-1>", on_click)

        self.refresh_library_summary()

    def open_card_preview(self, card_name: str) -> None:
        self.close_preview_window()
        win = tk.Toplevel(self.root)
        win.title(f"Card - {card_name}")
        win.geometry("620x520")
        win.minsize(460, 360)
        win.configure(bg="#131f30")
        self.preview_window = win

        body = tk.Frame(win, bg="#131f30", padx=12, pady=12)
        body.pack(fill="both", expand=True)

        img = self.load_card_thumbnail(card_name, 560, 400)
        if img is not None:
            img_label = tk.Label(body, image=img, bg="#131f30")
            img_label.image = img
            img_label.pack(fill="both", expand=True)
        else:
            fallback = tk.Label(
                body,
                text="Preview unavailable.\nInstall Pillow for broader image support.",
                bg="#243650",
                fg="#eaf2ff",
                pady=40,
            )
            fallback.pack(fill="both", expand=True)

        info = tk.Frame(win, bg="#1d314a", padx=12, pady=8)
        info.pack(fill="x")
        tk.Label(
            info,
            text=card_name,
            bg="#1d314a",
            fg="#f4d981",
            font=("TkDefaultFont", 11, "bold"),
            anchor="w",
        ).pack(side="left")
        tk.Button(
            info,
            text="Close",
            command=self.close_preview_window,
            relief="flat",
            bd=0,
            padx=10,
            bg="#efc95a",
            fg="#263247",
        ).pack(side="right")

        win.protocol("WM_DELETE_WINDOW", self.close_preview_window)

    def close_preview_window(self) -> None:
        if self.preview_window is not None and self.preview_window.winfo_exists():
            self.preview_window.destroy()
        self.preview_window = None

    def open_library_window(self) -> None:
        if self.library_window is not None and self.library_window.winfo_exists():
            self.library_window.lift()
            self.library_window.focus_force()
            self.render_library_cards()
            return

        win = tk.Toplevel(self.root)
        win.title("Card Library")
        win.geometry("860x620")
        win.minsize(700, 460)
        win.configure(bg="#eaf1df")
        self.library_window = win

        header = tk.Frame(win, bg="#314a36", padx=14, pady=10)
        header.pack(fill="x")
        tk.Label(
            header,
            text="Card Library",
            bg="#314a36",
            fg="#f9f3d3",
            font=("TkDefaultFont", 14, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text=f"Card folder: {CARDS_DIR}",
            bg="#314a36",
            fg="#dcead7",
            font=("TkDefaultFont", 9),
            wraplength=820,
            justify="left",
        ).pack(anchor="w", pady=(2, 0))

        toolbar = tk.Frame(win, bg="#dce8ce", padx=12, pady=8)
        toolbar.pack(fill="x")
        self.library_count_label = tk.Label(
            toolbar,
            text="Collected 0 / 0",
            bg="#dce8ce",
            fg="#2b4531",
            font=("TkDefaultFont", 11, "bold"),
        )
        self.library_count_label.pack(side="left")

        tk.Button(
            toolbar,
            text="Refresh",
            command=self.render_library_cards,
            relief="flat",
            bd=0,
            padx=10,
            bg="#f5e6b3",
            fg="#4a3a17",
            activebackground="#e8d695",
        ).pack(side="right")

        body = tk.Frame(win, bg="#eaf1df")
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        canvas = tk.Canvas(body, bg="#f6f9ef", highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(body, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        items_frame = tk.Frame(canvas, bg="#f6f9ef")
        canvas_window = canvas.create_window((0, 0), window=items_frame, anchor="nw")
        self.library_items_frame = items_frame

        def _on_items_configure(_event: object = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event: tk.Event) -> None:
            canvas.itemconfigure(canvas_window, width=event.width)

        items_frame.bind("<Configure>", _on_items_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.bind("<Configure>", self._schedule_library_reflow, add="+")

        self.render_library_cards()
        win.protocol("WM_DELETE_WINDOW", self._on_close_library_window)

    def _schedule_library_reflow(self, _event: object = None) -> None:
        if self.library_reflow_job is not None:
            self.root.after_cancel(self.library_reflow_job)
        self.library_reflow_job = self.root.after(120, self.render_library_cards)

    def _on_close_library_window(self) -> None:
        if self.library_reflow_job is not None:
            self.root.after_cancel(self.library_reflow_job)
            self.library_reflow_job = None
        self.close_preview_window()
        if self.library_window is not None and self.library_window.winfo_exists():
            self.library_window.destroy()
        self.library_window = None
        self.library_items_frame = None
        self.library_count_label = None

    def open_history_window(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Time History")
        win.geometry("560x420")
        win.minsize(480, 320)
        win.configure(bg=self.bg)

        wrap = tk.Frame(win, padx=10, pady=10, bg=self.bg)
        wrap.pack(fill="both", expand=True)

        tk.Label(
            wrap,
            text="Daily Time Distribution",
            font=("TkDefaultFont", 13, "bold"),
            bg=self.bg,
            fg=self.text,
        ).pack(anchor="w", pady=(0, 8))

        body = tk.Frame(wrap, bg=self.bg)
        body.pack(fill="both", expand=True)

        date_list = tk.Listbox(
            body,
            exportselection=False,
            bg=self.panel,
            fg=self.text,
            highlightthickness=1,
            highlightbackground=self.line,
            relief="flat",
        )
        date_list.pack(side="left", fill="y")

        details = tk.Text(
            body,
            wrap="word",
            bg=self.panel,
            fg=self.text,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.line,
        )
        details.pack(side="left", fill="both", expand=True, padx=(8, 0))
        details.config(state="disabled")

        sorted_dates = sorted(self.history.keys(), reverse=True)
        if not sorted_dates:
            details.config(state="normal")
            details.insert("1.0", "No history yet.\nStart a task and pause/complete it to generate records.")
            details.config(state="disabled")
            return

        display_dates: list[str] = []
        for d in sorted_dates:
            total_seconds = float(self.history.get(d, {}).get("total_seconds", 0.0))
            reached = total_seconds >= DAILY_GOAL_SECONDS
            date_list.insert("end", f"{d} {'★' if reached else ''}".rstrip())
            display_dates.append(d)

        def show_selected(_event: object = None) -> None:
            sel = date_list.curselection()
            if not sel:
                return
            date_key = display_dates[sel[0]]
            day = self.history.get(date_key, {})
            total_seconds = float(day.get("total_seconds", 0.0))
            tasks = day.get("tasks", {})
            reached = total_seconds >= DAILY_GOAL_SECONDS

            lines = [
                f"Date: {date_key}",
                f"Total: {self.format_seconds(total_seconds)}",
                f"Goal 6.5h: {'Reached ★' if reached else 'Not reached'}",
                "",
                "Task Breakdown:",
            ]
            if isinstance(tasks, dict) and tasks:
                for task_name, sec in sorted(tasks.items(), key=lambda x: float(x[1]), reverse=True):
                    lines.append(f"- {task_name}: {self.format_seconds(float(sec))}")
            else:
                lines.append("- No data")

            details.config(state="normal")
            details.delete("1.0", "end")
            details.insert("1.0", "\n".join(lines))
            details.config(state="disabled")

        date_list.bind("<<ListboxSelect>>", show_selected)
        date_list.selection_set(0)
        show_selected()

    def render_tasks(self) -> None:
        for child in self.list_container.winfo_children():
            child.destroy()
        self.task_time_labels = {}

        if not self.tasks:
            empty = tk.Label(self.list_container, text="No tasks yet.", bg=self.panel, fg=self.muted)
            empty.pack(anchor="w", padx=10, pady=10)
            self._on_task_frame_configure()
            self.refresh_timer_labels()
            return

        visible_indices = [i for i, task in enumerate(self.tasks) if self.show_completed or not bool(task["done"])]
        if not visible_indices:
            empty = tk.Label(self.list_container, text="No visible tasks.", bg=self.panel, fg=self.muted)
            empty.pack(anchor="w", padx=10, pady=10)
            self._on_task_frame_configure()
            self.refresh_timer_labels()
            return

        for pos, idx in enumerate(visible_indices):
            task = self.tasks[idx]
            row = tk.Frame(self.list_container, bg=self.panel, padx=8, pady=6)
            row.pack(fill="x")
            row.grid_columnconfigure(1, weight=1)

            done = bool(task["done"])
            txt = str(task["text"])

            mark = "[x]" if done else "[ ]"
            toggle_btn = tk.Button(
                row,
                text=mark,
                width=3,
                command=lambda i=idx: self.toggle_task(i),
                relief="flat",
                bd=0,
                bg=self.soft_blue,
                fg=self.text,
                activebackground="#cfdeea",
            )
            toggle_btn.grid(row=0, column=0, sticky="nw", rowspan=2)

            label = tk.Label(
                row,
                text=txt,
                bg=self.panel,
                fg=(self.muted if done else self.text),
                font=(self.done_font if done else self.default_font),
                anchor="w",
            )
            label.grid(row=0, column=1, sticky="ew", padx=(8, 8))
            label.bind("<Button-1>", lambda _event, i=idx: self.toggle_task(i))

            timer_label = tk.Label(row, text="", bg=self.panel, fg=self.muted, anchor="w", font=("TkDefaultFont", 10))
            timer_label.grid(row=1, column=1, sticky="w", padx=(8, 8))
            self.task_time_labels[idx] = timer_label

            run_btn_text = "Pause" if bool(task.get("running", False)) else "Start"
            run_btn = tk.Button(
                row,
                text=run_btn_text,
                command=lambda i=idx: self.toggle_run_task(i),
                width=6,
                relief="flat",
                bd=0,
                bg=(self.soft_rose if done else self.soft_green),
                fg=self.text,
            )
            run_btn.grid(row=0, column=2, padx=(4, 4), sticky="ne", rowspan=2)
            if done:
                run_btn.config(state="disabled")

            del_btn = tk.Button(
                row,
                text="Del",
                command=lambda i=idx: self.delete_task(i),
                relief="flat",
                bd=0,
                bg=self.soft_rose,
                fg=self.text,
                activebackground="#e8d5d8",
            )
            del_btn.grid(row=0, column=3, sticky="ne", rowspan=2)

            if pos < len(visible_indices) - 1:
                tk.Frame(self.list_container, bg=self.line, height=1).pack(fill="x", padx=8)

        self._on_task_frame_configure()
        self.refresh_timer_labels()


if __name__ == "__main__":
    root = tk.Tk()
    FloatingTaskWidget(root)
    root.mainloop()
