"""Small window: Look, then copy what is missing. Nothing copies by itself."""

from __future__ import annotations

import json
import queue
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk

from ui.match import (
    ACTION_COPY,
    ACTION_SKIP,
    COPYING_TEXT,
    SKIP_TEXT,
    completed_pairs,
    copied_text,
    copy_item,
    file_name,
    folder_text,
    log_skip_if_new,
    look_status,
    phone_text,
    plan,
)
from ui.phone import Phone, PhoneError

ROOT = Path(__file__).resolve().parents[1]
CRASH_LOG = ROOT / "logs" / "window-crash.log"
STATE_PATH = Path(__file__).resolve().parent / "window-state.json"
DEFAULT_FOLDER = Path(r"E:\iPhone14_8-27-2026")


def log_exception(exc_type, exc, tb) -> None:
    CRASH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with CRASH_LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"\n--- {datetime.now().isoformat(timespec='seconds')} ---\n")
        traceback.print_exception(exc_type, exc, tb, file=handle)


def _sys_hook(exc_type, exc, tb) -> None:
    log_exception(exc_type, exc, tb)
    sys.__excepthook__(exc_type, exc, tb)


def _thread_hook(args) -> None:
    log_exception(args.exc_type, args.exc_value, args.exc_traceback)


def initial_folder() -> str:
    if DEFAULT_FOLDER.is_dir():
        return str(DEFAULT_FOLDER)
    if STATE_PATH.is_file():
        try:
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ""
        folder = data.get("folder")
        if isinstance(folder, str):
            return folder
    return ""


def save_folder(folder: str) -> None:
    STATE_PATH.write_text(json.dumps({"folder": folder}, indent=2) + "\n", encoding="utf-8")


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.queue: queue.Queue = queue.Queue()
        self.stop = threading.Event()
        self.worker: threading.Thread | None = None
        self.busy = False
        self.close_requested = False
        self.items = []

        root.title("iPhone photos")
        root.minsize(960, 480)
        root.geometry("1100x560")
        root.report_callback_exception = log_exception
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.bind("<Escape>", self._on_escape)

        self.phone_var = tk.StringVar(value="Phone: press Look")
        self.folder_var = tk.StringVar(value=initial_folder())
        self.count_var = tk.StringVar(
            value="On the phone: —    Exact match, will skip: —    Will copy: —"
        )
        self.status_var = tk.StringVar(value="Choose a folder, then press Look. Nothing copies until you ask.")

        frame = ttk.Frame(root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(3, weight=1)

        ttk.Label(frame, textvariable=self.phone_var).grid(row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(frame, text="Folder").grid(row=1, column=0, sticky="w", pady=(10, 0))
        folder = ttk.Entry(frame, textvariable=self.folder_var)
        folder.grid(row=1, column=1, sticky="ew", padx=8, pady=(10, 0))
        ttk.Button(frame, text="Browse", command=self._browse).grid(row=1, column=2, pady=(10, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=2, column=0, columnspan=3, sticky="ew", pady=10)
        self.look_button = ttk.Button(buttons, text="Look", command=self._look_clicked)
        self.look_button.pack(side=tk.LEFT)
        self.copy_button = ttk.Button(
            buttons, text="Copy what's missing", command=self._copy_clicked
        )
        self.copy_button.pack(side=tk.LEFT, padx=(8, 16))
        ttk.Label(buttons, textvariable=self.count_var).pack(side=tk.LEFT)

        list_frame = ttk.Frame(frame)
        list_frame.grid(row=3, column=0, columnspan=3, sticky="nsew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            list_frame,
            columns=("file", "phone", "folder", "status"),
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("file", text="File")
        self.tree.heading("phone", text="Phone")
        self.tree.heading("folder", text="In folder")
        self.tree.heading("status", text="Status")
        self.tree.column("file", width=160, stretch=False)
        self.tree.column("phone", width=320, stretch=True)
        self.tree.column("folder", width=380, stretch=True)
        self.tree.column("status", width=210, stretch=False)
        scroll_y = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scroll_x = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        ttk.Label(frame, textvariable=self.status_var).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(8, 0)
        )

    def _browse(self) -> None:
        if self.busy:
            return
        current = self.folder_var.get().strip()
        chosen = filedialog.askdirectory(initialdir=current or None)
        if not chosen:
            return
        self.folder_var.set(chosen)
        save_folder(chosen)

    def _look_clicked(self) -> None:
        if self.busy:
            return
        folder = self.folder_var.get().strip()
        if not folder or not Path(folder).is_dir():
            self.status_var.set("Choose a folder that exists.")
            return
        save_folder(folder)
        self._clear_rows()
        self.status_var.set("Looking…")
        self._start(lambda: self._look(folder))

    def _copy_clicked(self) -> None:
        if self.busy:
            return
        if not self.items:
            self.status_var.set("Press Look first.")
            return
        folder = self.folder_var.get().strip()
        if not folder or not Path(folder).is_dir():
            self.status_var.set("Choose a folder that exists.")
            return
        save_folder(folder)
        items = list(self.items)
        self.status_var.set("Copying…")
        self._start(lambda: self._copy(folder, items))

    def _clear_rows(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self.items = []
        self.row_ids = []
        self.count_var.set("On the phone: —    Exact match, will skip: —    Will copy: —")

    def _start(self, target) -> None:
        self.busy = True
        self.stop.clear()
        self._buttons()
        self.worker = threading.Thread(target=self._guard, args=(target,), daemon=False)
        self.worker.start()
        self.root.after(100, self._poll)

    def _buttons(self) -> None:
        state = tk.DISABLED if self.busy else tk.NORMAL
        self.look_button.configure(state=state)
        self.copy_button.configure(state=state)

    def _guard(self, target) -> None:
        try:
            target()
        except Exception:
            log_exception(*sys.exc_info())
            self.queue.put(
                ("status", "Something went wrong. The details are in logs\\window-crash.log.")
            )

    def _look(self, folder: str) -> None:
        destination = Path(folder)
        with Phone() as phone:
            try:
                name = phone.connect()
            except PhoneError as exc:
                self.queue.put(("phone_error", str(exc)))
                self.queue.put(("status", str(exc)))
                return
            self.queue.put(("phone", name))
            self.queue.put(("status", "Reading the camera roll…"))
            try:
                files = phone.list_dcim()
            except PhoneError as exc:
                self.queue.put(("phone_error", str(exc)))
                self.queue.put(("status", str(exc)))
                return
        items = plan(files, destination)
        self.queue.put(("plan", items))
        skips = sum(1 for item in items if item.action == ACTION_SKIP)
        copies = sum(1 for item in items if item.action == ACTION_COPY)
        self.queue.put(("counts", len(items), skips, copies))
        self.queue.put(("status", "Look finished. Nothing was copied."))

    def _copy(self, folder: str, items) -> None:
        destination = Path(folder)
        done = completed_pairs(destination)
        with Phone() as phone:
            try:
                name = phone.connect()
            except PhoneError as exc:
                self.queue.put(("phone_error", str(exc)))
                self.queue.put(("status", str(exc)))
                return
            self.queue.put(("phone", name))
            for index, item in enumerate(items):
                if self.stop.is_set():
                    self.queue.put(("status", "Stopped. Files already copied stay copied."))
                    return
                if item.action == ACTION_SKIP:
                    log_skip_if_new(destination, item, done)
                    self.queue.put(("row", index, SKIP_TEXT))
                    continue
                self.queue.put(("row", index, COPYING_TEXT))
                self.queue.put(("status", f"Copying {file_name(item.source_path)}"))
                try:
                    copy_item(destination, item, phone.iter_file(item.source_path, item.size))
                except Exception as exc:
                    log_exception(type(exc), exc, exc.__traceback__)
                    self.queue.put(("row", index, f"Failed: {exc}"))
                    self.queue.put(
                        ("status", f"Stopped on {file_name(item.source_path)}. Files already copied stay copied.")
                    )
                    return
                self.queue.put(("row", index, copied_text(item.dest_relative or "")))
        if self.stop.is_set():
            self.queue.put(("status", "Stopped. Files already copied stay copied."))
        else:
            self.queue.put(("status", "Done."))

    def _apply(self, message) -> None:
        kind = message[0]
        if kind == "phone":
            self.phone_var.set(f"Phone: {message[1]}")
        elif kind == "phone_error":
            self.phone_var.set(message[1])
        elif kind == "status":
            self.status_var.set(message[1])
        elif kind == "counts":
            _on_phone, skips, copies = message[1], message[2], message[3]
            self.count_var.set(
                f"On the phone: {message[1]}    Exact match, will skip: {skips}    Will copy: {copies}"
            )
        elif kind == "plan":
            self.items = message[1]
            self.row_ids = []
            self.tree.delete(*self.tree.get_children())
            for item in self.items:
                iid = self.tree.insert(
                    "",
                    tk.END,
                    values=(
                        file_name(item.source_path),
                        phone_text(item.source_path, item.size),
                        folder_text(item),
                        look_status(item),
                    ),
                )
                self.row_ids.append(iid)
        elif kind == "row":
            index, status = message[1], message[2]
            if 0 <= index < len(self.row_ids):
                self.tree.set(self.row_ids[index], "status", status)

    def _poll(self) -> None:
        try:
            while True:
                self._apply(self.queue.get_nowait())
        except queue.Empty:
            pass
        alive = self.worker is not None and self.worker.is_alive()
        if alive:
            self.root.after(100, self._poll)
            return
        self.busy = False
        self._buttons()
        if self.close_requested:
            self.root.destroy()

    def _on_escape(self, _event=None) -> None:
        if self.busy:
            self.stop.set()
            self.status_var.set("Stopping after the current file…")
            return
        self.root.destroy()

    def _on_close(self) -> None:
        if self.busy:
            self.stop.set()
            self.close_requested = True
            self.status_var.set("Stopping after the current file…")
            return
        self.root.destroy()


def main() -> None:
    sys.excepthook = _sys_hook
    threading.excepthook = _thread_hook
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
