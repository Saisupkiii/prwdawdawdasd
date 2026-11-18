"""Lightweight dark gaming overlay + booster (Windows).

Run: python main.py
"""
import os
import subprocess
import threading
import time

import customtkinter as ctk
import psutil

POWER_HIGH = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
TARGETS = [
    ("chrome.exe", "Chrome"),
    ("msedge.exe", "Edge"),
    ("firefox.exe", "Firefox"),
    ("Discord.exe", "Discord"),
    ("steamwebhelper.exe", "Steam WebHelper"),
    ("EpicGamesLauncher.exe", "Epic Games Launcher"),
    ("OneDrive.exe", "OneDrive"),
    ("Spotify.exe", "Spotify"),
]


def run_hidden(cmd):
    """Run a shell command without flashing a console window."""
    try:
        subprocess.run(
            cmd, shell=True, timeout=20,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except Exception:
        return False


NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
SMI_CANDIDATES = ["nvidia-smi", r"C:\Windows\System32\nvidia-smi.exe"]


def nvidia_stats():
    """Return (temp_c, load_pct) or (None, None) if nvidia-smi is missing."""
    for exe in SMI_CANDIDATES:
        try:
            out = subprocess.check_output(
                [exe, "--query-gpu=temperature.gpu,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                stderr=subprocess.DEVNULL, timeout=3,
                creationflags=NO_WINDOW,
            ).decode(errors="ignore").strip().splitlines()[0]
            temp, load = [s.strip() for s in out.split(",")[:2]]
            return int(temp), int(load)
        except Exception:
            continue
    return None, None


class Overlay(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.88)
        self.geometry("260x230+60+60")
        self.configure(fg_color="#121212")

        self.selected = {exe: ctk.BooleanVar(value=True) for exe, _ in TARGETS}
        self.mini = False

        self._build_stats()
        self._build_controls()
        self.bind("<Button-1>", self._drag_start)
        self.bind("<B1-Motion>", self._drag_move)
        psutil.cpu_percent(None)  # prime the sampler
        self.after(1500, self._tick)

    # ---------- UI ----------
    def _build_stats(self):
        self.stats = ctk.CTkFrame(self, corner_radius=0, fg_color="#121212")
        self.stats.pack(fill="x", padx=8, pady=(6, 0))
        self.lbl = {}
        for key, text in [("cpu", "CPU  —"), ("ram", "RAM  —"),
                          ("gpu", "GPU  —"), ("ping", "PING —")]:
            l = ctk.CTkLabel(self.stats, text=text, anchor="w",
                             font=("Consolas", 13), text_color="#d8d8d8")
            l.pack(fill="x")
            self.lbl[key] = l
        # Compact mode shows only one line.
        self.mini_lbl = ctk.CTkLabel(self.stats, text="", anchor="w",
                                     font=("Consolas", 13), text_color="#8ef")

    def _build_controls(self):
        self.body = ctk.CTkFrame(self, corner_radius=0, fg_color="#121212")
        self.body.pack(fill="both", expand=True, padx=8, pady=6)

        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x")
        self.ip = ctk.CTkEntry(row, placeholder_text="1.1.1.1", width=110,
                               fg_color="#1e1e1e", border_color="#333")
        self.ip.insert(0, "1.1.1.1")
        self.ip.pack(side="left")
        ctk.CTkButton(row, text="▽", width=36, fg_color="#222", hover_color="#333",
                      command=self.toggle_mini).pack(side="right")
        ctk.CTkButton(row, text="✕", width=36, fg_color="#3a1515", hover_color="#5a2020",
                      command=self.destroy).pack(side="right", padx=4)

        ctk.CTkButton(self.body, text="⚠ Закрыть процессы", height=30,
                      fg_color="#222", hover_color="#333",
                      command=self.open_checklist).pack(fill="x", pady=(8, 4))
        ctk.CTkButton(self.body, text="⚡ Boost FPS", height=34,
                      fg_color="#7b3fe4", hover_color="#8f56f0",
                      font=("Segoe UI", 14, "bold"),
                      command=self.boost).pack(fill="x")
        self.status = ctk.CTkLabel(self.body, text="", text_color="#7a7a7a",
                                   font=("Segoe UI", 11))
        self.status.pack(pady=4)

    def open_checklist(self):
        win = ctk.CTkToplevel(self)
        win.title("Что закрыть")
        win.geometry("300x330")
        win.attributes("-topmost", True)
        for exe, name in TARGETS:
            ctk.CTkCheckBox(win, text=f"{name}  ({exe})", variable=self.selected[exe],
                            fg_color="#7b3fe4").pack(anchor="w", padx=16, pady=4)
        ctk.CTkButton(win, text="Закрыть выбранные", fg_color="#7b3fe4",
                      hover_color="#8f56f0",
                      command=lambda: (self.close_selected(), win.destroy())
                      ).pack(pady=10)

    # ---------- window ----------
    def _drag_start(self, e):
        self._off = (e.x_root - self.winfo_x(), e.y_root - self.winfo_y())

    def _drag_move(self, e):
        self.geometry(f"+{e.x_root - self._off[0]}+{e.y_root - self._off[1]}")

    def toggle_mini(self):
        self.mini = not self.mini
        if self.mini:
            self.body.pack_forget()
            for l in self.lbl.values():
                l.pack_forget()
            self.mini_lbl.pack(fill="x")
            self.geometry("260x40")
        else:
            self.mini_lbl.pack_forget()
            for l in self.lbl.values():
                l.pack(fill="x")
            self.body.pack(fill="both", expand=True, padx=8, pady=6)
            self.geometry("260x230")
            self.stats.pack(fill="x", padx=8, pady=(6, 0))

    # ---------- stats ----------
    def _tick(self):
        threading.Thread(target=self._refresh, daemon=True).start()
        self.after(1500, self._tick)

    def _refresh(self):
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        temp, load = nvidia_stats()
        ip = self.ip.get().strip() or "1.1.1.1"
        ping = run_ping(f"-n 1 -w 800 {ip}")

        gpu_txt = f"{temp}°C | {load}%" if temp is not None else "n/a"
        vals = {
            "cpu": f"CPU  {cpu:4.0f}%",
            "ram": f"RAM  {ram.percent:4.0f}%  {ram.used / 1024**3:.1f}/{ram.total / 1024**3:.1f} GB",
            "gpu": f"GPU  {gpu_txt}",
            "ping": f"PING {ping if ping is not None else 'timeout'} ms",
        }
        try:
            for k, v in vals.items():
                self.lbl[k].configure(text=v)
            self.mini_lbl.configure(text=f"CPU {cpu:.0f}% | {gpu_txt} | {ping} ms")
        except Exception:
            pass  # window closed mid-update

    # ---------- boost ----------
    def close_selected(self):
        closed = 0
        for exe, _ in TARGETS:
            if not self.selected[exe].get():
                continue
            for p in psutil.process_iter(["name"]):
                if (p.info["name"] or "").lower() == exe.lower():
                    try:
                        p.terminate()
                        closed += 1
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
        self.status.configure(text=f"Закрыто процессов: {closed}")

    def boost(self):
        def work():
            self.close_selected()
            run_hidden("ipconfig /flushdns")
            ok = run_hidden(f"powercfg /setactive {POWER_HIGH}")
            msg = "Готово: DNS сброшен, план High Performance" if ok \
                else "Готово, но план питания не применён"
            self.status.configure(text=msg)
        threading.Thread(target=work, daemon=True).start()


def run_ping(args):
    """Return latency in ms or None."""
    try:
        out = subprocess.run(
            f"ping {args}", shell=True, capture_output=True, text=True, timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
        for tok in out.split():
            if tok.startswith("=") and tok[1:].rstrip("ms").isdigit():
                return int(tok[1:].rstrip("ms"))
            if "Время=" in tok or "time=" in tok.lower():
                nums = "".join(c for c in tok.split("=")[-1] if c.isdigit())
                if nums:
                    return int(nums)
        for line in out.splitlines():
            if "TTL" in line:
                nums = "".join(c for c in line.split("=")[-1] if c.isdigit())
                if nums:
                    return int(nums)
    except Exception:
        pass
    return None


if __name__ == "__main__":
    Overlay().mainloop()
