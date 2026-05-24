"""
CLIENT PC — PC Monitor System
- Collects own PC info (CPU, RAM, Disk, OS, etc.)
- Sends info to Master via WebSocket every 5 seconds
- tkinter GUI: shows its own stats
- pystray: system tray icon (close = hide, not exit)
- Auto startup on login via registry
"""

import asyncio
import json
import threading
import queue
import socket
import platform
import winreg
import sys
import os
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

import websockets
import psutil
import pystray
from PIL import Image, ImageDraw
from dotenv import dotenv_values

# ── Config ─────────────────────────────────────────────────
config      = dotenv_values("config.env")
PASSWORD    = config.get("PASSWORD", "admin123")
MASTER_IP   = config.get("MASTER_IP", "127.0.0.1")
PORT        = int(config.get("PORT", "8765"))
SEND_EVERY  = 5   # seconds

# ── Shared State ───────────────────────────────────────────
latest_info = {}
ui_queue    = queue.Queue()

# ── PC Info Collection ─────────────────────────────────────
def get_pc_info():
    try:
        hostname = socket.gethostname()
        try:
            ip = socket.gethostbyname(hostname)
        except:
            ip = "127.0.0.1"

        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")

        boot_ts  = psutil.boot_time()
        uptime_s = datetime.now().timestamp() - boot_ts
        uptime   = format_uptime(uptime_s)

        os_info  = f"{platform.system()} {platform.release()}"

        return {
            "hostname":     hostname,
            "ip":           ip,
            "os":           os_info,
            "cpu_percent":  round(cpu, 1),
            "ram_total_gb": round(ram.total  / (1024**3), 1),
            "ram_used_gb":  round(ram.used   / (1024**3), 1),
            "ram_percent":  round(ram.percent, 1),
            "disk_total_gb":round(disk.total / (1024**3), 1),
            "disk_used_gb": round(disk.used  / (1024**3), 1),
            "disk_percent": round(disk.percent, 1),
            "uptime":       uptime,
            "password":     PASSWORD
        }
    except Exception as e:
        print(f"Error collecting info: {e}")
        return {}

def format_uptime(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h > 0: return f"{h}h {m}m"
    return f"{m}m"

# ── WebSocket Client ───────────────────────────────────────
async def ws_client():
    uri = f"ws://{MASTER_IP}:{PORT}"
    reconnect_delay = 5

    while True:
        try:
            print(f"Connecting to {uri}...")
            ui_queue.put(("status", "CONNECTING..."))

            async with websockets.connect(uri, ping_interval=20) as ws:
                # Send auth
                info = get_pc_info()
                await ws.send(json.dumps({"password": PASSWORD}))

                resp = json.loads(await ws.recv())
                if resp.get("auth") != "OK":
                    print("Auth failed!")
                    ui_queue.put(("status", "AUTH FAILED"))
                    await asyncio.sleep(reconnect_delay)
                    continue

                print("Connected and authenticated!")
                ui_queue.put(("status", "CONNECTED"))

                # Start concurrent sender and receiver tasks so server can send commands
                async def sender():
                    while True:
                        info = get_pc_info()
                        latest_info.update(info)
                        try:
                            await ws.send(json.dumps(info))
                        except Exception:
                            break
                        ui_queue.put(("update", dict(info)))
                        await asyncio.sleep(SEND_EVERY)

                async def receiver():
                    while True:
                        try:
                            msg = await ws.recv()
                        except Exception:
                            break
                        try:
                            cmd = json.loads(msg)
                        except Exception:
                            continue
                        # handle incoming server commands
                        action = cmd.get("action")
                        if cmd.get("password") != PASSWORD:
                            continue  # Password verification for all commands
                        
                        try:
                            import subprocess
                            if action == "shutdown":
                                print(f"[!] Shutdown command received from {MASTER_IP}")
                                if os.name == "nt":
                                    subprocess.Popen(["shutdown", "/s", "/t", "30", "/c", "Remote shutdown initiated"])
                                else:
                                    subprocess.Popen(["shutdown", "-h", "+1"])
                            elif action == "restart":
                                print(f"[!] Restart command received from {MASTER_IP}")
                                if os.name == "nt":
                                    subprocess.Popen(["shutdown", "/r", "/t", "30", "/c", "Remote restart initiated"])
                                else:
                                    subprocess.Popen(["shutdown", "-r", "+1"])
                            elif action == "logoff":
                                print(f"[!] Logoff command received from {MASTER_IP}")
                                if os.name == "nt":
                                    subprocess.Popen(["shutdown", "/l", "/t", "10"])
                                else:
                                    subprocess.Popen(["pkill", "-u", os.getenv("USER")])
                        except Exception as e:
                            print(f"Failed to execute {action}: {e}")

                send_task = asyncio.create_task(sender())
                recv_task = asyncio.create_task(receiver())
                # wait until either task ends (connection lost)
                await asyncio.wait([send_task, recv_task], return_when=asyncio.FIRST_COMPLETED)

        except (websockets.exceptions.ConnectionClosed,
                ConnectionRefusedError, OSError) as e:
            print(f"Disconnected: {e} — retry in {reconnect_delay}s")
            ui_queue.put(("status", "DISCONNECTED — RETRYING..."))
            await asyncio.sleep(reconnect_delay)
        except Exception as e:
            print(f"Unexpected error: {e}")
            await asyncio.sleep(reconnect_delay)

def run_client_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(ws_client())

# ── System Tray ────────────────────────────────────────────
def create_tray_icon(connected=False):
    img  = Image.new("RGB", (64, 64), color=(8, 12, 20))
    draw = ImageDraw.Draw(img)
    clr  = (57, 255, 143) if connected else (255, 45, 85)
    draw.rectangle([4, 4, 60, 60], outline=clr, width=2)
    draw.ellipse([22, 18, 42, 38], fill=clr)
    draw.rectangle([20, 42, 44, 54], fill=(0, 150, 180))
    return img

def make_tray(root):
    def show(icon, item):
        root.after(0, root.deiconify)

    def quit_app(icon, item):
        icon.stop()
        root.after(0, root.destroy)

    icon = pystray.Icon(
        "PC Monitor Client",
        create_tray_icon(False),
        "PC Monitor — Client",
        menu=pystray.Menu(
            pystray.MenuItem("Show Info", show, default=True),
            pystray.MenuItem("Quit", quit_app)
        )
    )
    t = threading.Thread(target=icon.run, daemon=True)
    t.start()
    return icon

# ── Startup Registry ───────────────────────────────────────
def add_to_startup():
    try:
        app_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "PCMonitorClient", 0, winreg.REG_SZ, f'"{app_path}"')
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Startup reg failed: {e}")

# ── tkinter GUI ────────────────────────────────────────────
class ClientApp:
    def __init__(self, root):
        self.root  = root
        self.root.title("PC Monitor — This PC")
        self.root.geometry("460x520")
        self.root.resizable(False, False)
        self.root.configure(bg="#080b10")
        self.root.protocol("WM_DELETE_WINDOW", self.hide)

        self._build_ui()
        self._poll_queue()

    def hide(self):
        self.root.withdraw()

    def _build_ui(self):
        BG   = "#080b10"
        S1   = "#0d1118"
        S2   = "#111720"
        BRD  = "#1c2535"
        ACC  = "#00d4ff"
        DIM  = "#3a4a5a"
        TEXT = "#b0c4d8"
        GRN  = "#39ff8f"

        # Header
        hdr = tk.Frame(self.root, bg=S1, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="THIS PC — MONITOR",
                 font=("Courier", 13, "bold"),
                 fg=ACC, bg=S1).pack(side="left", padx=16, pady=12)

        self.lbl_clock = tk.Label(hdr, text="—",
                 font=("Courier", 9), fg=DIM, bg=S1)
        self.lbl_clock.pack(side="right", padx=14)
        self._tick()

        # Status
        self.status_bar = tk.Frame(self.root, bg=S2, height=32)
        self.status_bar.pack(fill="x")
        self.status_bar.pack_propagate(False)

        tk.Label(self.status_bar, text="MASTER:", font=("Courier", 9),
                 fg=DIM, bg=S2).pack(side="left", padx=14, pady=6)
        tk.Label(self.status_bar, text=f"{MASTER_IP}:{PORT}",
                 font=("Courier", 9), fg=ACC, bg=S2).pack(side="left")

        self.lbl_conn = tk.Label(self.status_bar, text="● CONNECTING...",
                 font=("Courier", 9), fg="#ff9500", bg=S2)
        self.lbl_conn.pack(side="right", padx=14)

        # Info Cards
        cards = tk.Frame(self.root, bg=BG)
        cards.pack(fill="both", expand=True, padx=14, pady=10)

        self.labels = {}
        fields = [
            ("HOSTNAME",    "hostname"),
            ("IP ADDRESS",  "ip"),
            ("OS",          "os"),
            ("UPTIME",      "uptime"),
        ]

        for i, (label, key) in enumerate(fields):
            row = tk.Frame(cards, bg=S2,
                           highlightbackground=BRD,
                           highlightthickness=1)
            row.pack(fill="x", pady=3)

            tk.Label(row, text=label, font=("Courier", 9),
                     fg=DIM, bg=S2, width=14, anchor="w"
                     ).pack(side="left", padx=12, pady=8)

            lbl = tk.Label(row, text="—", font=("Courier", 10, "bold"),
                           fg=TEXT, bg=S2, anchor="w")
            lbl.pack(side="left", fill="x", expand=True, padx=4)
            self.labels[key] = lbl

        # Metrics
        metrics_title = tk.Label(cards, text="// LIVE METRICS",
                    font=("Courier", 9), fg=DIM, bg=BG)
        metrics_title.pack(anchor="w", pady=(10,4))

        metrics = [
            ("CPU",  "cpu_percent",  "%"),
            ("RAM",  "ram_percent",  "%"),
            ("DISK", "disk_percent", "%"),
        ]

        for label, key, unit in metrics:
            frame = tk.Frame(cards, bg=S2,
                             highlightbackground=BRD,
                             highlightthickness=1)
            frame.pack(fill="x", pady=3)

            tk.Label(frame, text=label, font=("Courier", 9),
                     fg=DIM, bg=S2, width=6, anchor="w"
                     ).pack(side="left", padx=12, pady=8)

            # Progress bar
            bar_bg = tk.Frame(frame, bg="#1c2535", height=10, width=200)
            bar_bg.pack(side="left", padx=6, pady=12)
            bar_bg.pack_propagate(False)

            bar_fill = tk.Frame(bar_bg, bg=ACC, height=10, width=0)
            bar_fill.place(x=0, y=0, height=10)

            val_lbl = tk.Label(frame, text="—",
                     font=("Courier", 10, "bold"),
                     fg=TEXT, bg=S2, width=8)
            val_lbl.pack(side="left", padx=6)

            self.labels[key]          = val_lbl
            self.labels[key + "_bar"] = (bar_fill, bar_bg)

        # RAM detail
        self.lbl_ram_detail = tk.Label(cards, text="",
            font=("Courier", 9), fg=DIM, bg=BG)
        self.lbl_ram_detail.pack(anchor="w", pady=2)

        # Disk detail
        self.lbl_disk_detail = tk.Label(cards, text="",
            font=("Courier", 9), fg=DIM, bg=BG)
        self.lbl_disk_detail.pack(anchor="w", pady=2)

    def update_ui(self, info):
        simple = ["hostname", "ip", "os", "uptime"]
        for k in simple:
            if k in self.labels and k in info:
                self.labels[k].config(text=str(info[k]))

        for key in ["cpu_percent", "ram_percent", "disk_percent"]:
            val = info.get(key, 0)
            if key in self.labels:
                self.labels[key].config(text=f"{val:.1f}%")
            bar_key = key + "_bar"
            if bar_key in self.labels:
                fill, bg = self.labels[bar_key]
                bg.update_idletasks()
                w = bg.winfo_width()
                fw = int(w * val / 100)
                color = (
                    "#39ff8f" if val < 60 else
                    "#ff9500" if val < 85 else
                    "#ff2d55"
                )
                fill.config(width=fw, bg=color)

        self.lbl_ram_detail.config(
            text=f"RAM: {info.get('ram_used_gb',0):.1f} GB used / {info.get('ram_total_gb',0):.1f} GB total")
        self.lbl_disk_detail.config(
            text=f"Disk: {info.get('disk_used_gb',0):.1f} GB used / {info.get('disk_total_gb',0):.1f} GB total")

    def set_status(self, status):
        color = {
            "CONNECTED":          "#39ff8f",
            "CONNECTING...":      "#ff9500",
            "DISCONNECTED — RETRYING...": "#ff2d55",
            "AUTH FAILED":        "#ff2d55",
        }.get(status, "#ff9500")
        dot = "●"
        self.lbl_conn.config(text=f"{dot} {status}", fg=color)

    def _poll_queue(self):
        try:
            while True:
                msg, data = ui_queue.get_nowait()
                if msg == "update":
                    self.update_ui(data)
                elif msg == "status":
                    self.set_status(data)
        except queue.Empty:
            pass
        self.root.after(300, self._poll_queue)

    def _tick(self):
        self.lbl_clock.config(
            text=datetime.now().strftime("%H:%M:%S  %d/%m/%Y"))
        self.root.after(1000, self._tick)

# ── Main ───────────────────────────────────────────────────
def main():
    add_to_startup()

    # Start WebSocket client in background thread
    loop = asyncio.new_event_loop()
    client_thread = threading.Thread(
        target=run_client_loop, args=(loop,), daemon=True)
    client_thread.start()

    # tkinter GUI
    root = tk.Tk()
    app  = ClientApp(root)
    make_tray(root)

    root.mainloop()

if __name__ == "__main__":
    main()