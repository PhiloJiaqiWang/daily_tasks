import json
from pathlib import Path
import tkinter as tk
import time
from datetime import datetime, timedelta

DATA_FILE = Path(__file__).with_name("tasks.json")
HISTORY_FILE = Path(__file__).with_name("history.json")


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
        self.task_time_labels: dict[int, tk.Label] = {}
        self.timer_job: str | None = None
        self.show_completed = True
        self.default_font = ("TkDefaultFont", 11)
        self.done_font = ("TkDefaultFont", 11, "overstrike")

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

        self.list_container = tk.Frame(container, bg=self.panel, relief="flat", bd=0)
        self.list_container.pack(fill="both", expand=True)

        self.status = tk.Label(container, text="Ready", bg=self.bg, fg=self.muted, anchor="w", font=("TkDefaultFont", 10))
        self.status.pack(fill="x", pady=(6, 6))

        footer = tk.Frame(container, bg=self.bg)
        footer.pack(fill="x")

        self.toggle_done_btn = tk.Button(
            footer,
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

        history_btn = tk.Button(
            footer,
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

        self.load_tasks()
        self.load_history()
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
        self.root.destroy()

    def start_timer_loop(self) -> None:
        self.refresh_timer_labels()
        self.timer_job = self.root.after(1000, self.start_timer_loop)

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

        for d in sorted_dates:
            date_list.insert("end", d)

        def show_selected(_event: object = None) -> None:
            sel = date_list.curselection()
            if not sel:
                return
            date_key = date_list.get(sel[0])
            day = self.history.get(date_key, {})
            total_seconds = float(day.get("total_seconds", 0.0))
            tasks = day.get("tasks", {})

            lines = [f"Date: {date_key}", f"Total: {self.format_seconds(total_seconds)}", "", "Task Breakdown:"]
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
            self.refresh_timer_labels()
            return

        visible_indices = [i for i, task in enumerate(self.tasks) if self.show_completed or not bool(task["done"])]
        if not visible_indices:
            empty = tk.Label(self.list_container, text="No visible tasks.", bg=self.panel, fg=self.muted)
            empty.pack(anchor="w", padx=10, pady=10)
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

        self.refresh_timer_labels()


if __name__ == "__main__":
    root = tk.Tk()
    FloatingTaskWidget(root)
    root.mainloop()
