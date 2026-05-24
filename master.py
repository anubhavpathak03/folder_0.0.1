"""
MASTER PC — PC Monitor System
- WebSocket Server: receives info from all clients
- tkinter GUI: shows all connected clients dashboard
- pystray: system tray icon (close = hide, not exit)
- Auto startup on login via registry
"""

import asyncio
import json
import threading
import queue
import socket
import winreg
import sys
import os
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from datetime import datetime

import websockets
import pystray
from PIL import Image, ImageDraw
from dotenv import dotenv_values

# ── Config ─────────────────────────────────────────────────
config   = dotenv_values("config.env")
PASSWORD = config.get("PASSWORD", "admin123")
PORT     = int(config.get("PORT", "8765"))

# ── Shared State ───────────────────────────────────────────
clients_data = {}   # {ip: {hostname, cpu, ram, disk, ...}}
clients_lock = threading.Lock()
ui_queue     = queue.Queue()   # Thread-safe GUI updates
clients_ws = {}       # {ip: websocket}
server_loop = None    # asyncio event loop for server (set in run_server_loop)

# ── PC Info Helpers ────────────────────────────────────────
def format_uptime(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h > 0: return f"{h}h {m}m"
    return f"{m}m"

# ── WebSocket Server ───────────────────────────────────────
async def handle_client(websocket):
    client_ip = websocket.remote_address[0]
    print(f"[+] Client connected: {client_ip}")

    try:
        # Auth check
        auth_msg = await asyncio.wait_for(websocket.recv(), timeout=10)
        data = json.loads(auth_msg)

        if data.get("password") != PASSWORD:
            await websocket.send(json.dumps({"auth": "FAIL"}))
            return

        await websocket.send(json.dumps({"auth": "OK"}))
        # keep reference to websocket so server GUI can send commands
        with clients_lock:
            clients_ws[client_ip] = websocket
        print(f"[✓] Authenticated: {client_ip}")

        # Receive info loop
        async for message in websocket:
            try:
                info = json.loads(message)
                info["last_seen"] = datetime.now().strftime("%H:%M:%S")
                info["connected"] = True

                with clients_lock:
                    clients_data[client_ip] = info

                # Tell GUI to refresh
                ui_queue.put(("refresh", None))

            except json.JSONDecodeError:
                pass

    except (websockets.exceptions.ConnectionClosed, asyncio.TimeoutError):
        pass
    finally:
        # Mark client as disconnected
        with clients_lock:
            if client_ip in clients_data:
                clients_data[client_ip]["connected"] = False
            # remove websocket ref
            if client_ip in clients_ws:
                try:
                    del clients_ws[client_ip]
                except KeyError:
                    pass
        ui_queue.put(("refresh", None))
        print(f"[-] Client disconnected: {client_ip}")

def run_server_loop(loop):
    asyncio.set_event_loop(loop)
    global server_loop
    server_loop = loop
    server_ip = "0.0.0.0"

    async def start():
        async with websockets.serve(handle_client, server_ip, PORT):
            print(f"[✓] WebSocket server running on port {PORT}")
            await asyncio.Future()  # Run forever

    loop.run_until_complete(start())

# ── System Tray Icon ───────────────────────────────────────
def create_tray_icon():
    img = Image.new("RGB", (64, 64), color=(8, 12, 20))
    draw = ImageDraw.Draw(img)
    draw.rectangle([4, 4, 60, 60], outline=(0, 212, 255), width=2)
    draw.rectangle([10, 14, 54, 38], fill=(0, 80, 120))
    draw.rectangle([20, 42, 44, 54], fill=(0, 212, 255))
    return img

def make_tray(root):
    def show(icon, item):
        root.after(0, root.deiconify)

    def quit_app(icon, item):
        icon.stop()
        root.after(0, root.destroy)

    icon = pystray.Icon(
        "PC Monitor Master",
        create_tray_icon(),
        "PC Monitor — Master",
        menu=pystray.Menu(
            pystray.MenuItem("Show Dashboard", show, default=True),
            pystray.MenuItem("Quit", quit_app)
        )
    )
    t = threading.Thread(target=icon.run, daemon=True)
    t.start()
    return icon

# Send a command to a client identified by IP. Uses the server event loop to schedule send.
def send_command_to_client(ip, cmd: dict):
    """Send a JSON command to a connected client via its websocket.
    Returns True if scheduled, False otherwise.
    """
    with clients_lock:
        ws = clients_ws.get(ip)
    if not ws:
        print(f"No active websocket for {ip}")
        return False

    if server_loop is None:
        print("Server loop not available to send command")
        return False

    try:
        fut = asyncio.run_coroutine_threadsafe(ws.send(json.dumps(cmd)), server_loop)
        # optionally wait briefly for result (non-blocking here)
        return True
    except Exception as e:
        print(f"Failed to send command to {ip}: {e}")
        return False

# ── Startup Registry ───────────────────────────────────────
def add_to_startup():
    try:
        app_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "PCMonitorMaster", 0, winreg.REG_SZ, f'"{app_path}"')
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Startup registration failed: {e}")

# ── tkinter GUI ────────────────────────────────────────────
class MasterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PC Monitor — Master Dashboard")
        self.root.geometry("1100x600")
        self.root.minsize(800, 400)
        self.root.configure(bg="#080b10")

        # Close = hide to tray
        self.root.protocol("WM_DELETE_WINDOW", self.hide)

        self._build_ui()
        self._poll_queue()

    def hide(self):
        self.root.withdraw()

    def _build_ui(self):
        # ── Header
        hdr = tk.Frame(self.root, bg="#0d1118", height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="INDUS CTRL  —  PC MONITOR",
                 font=("Courier", 14, "bold"),
                 fg="#00d4ff", bg="#0d1118").pack(side="left", padx=20, pady=12)

        self.lbl_clock = tk.Label(hdr, text="—",
                 font=("Courier", 10), fg="#3a4a5a", bg="#0d1118")
        self.lbl_clock.pack(side="right", padx=20)
        self._tick()

        self.lbl_status = tk.Label(hdr,
                 text="● SERVER RUNNING",
                 font=("Courier", 10), fg="#39ff8f", bg="#0d1118")
        self.lbl_status.pack(side="right", padx=12)

        # ── Summary bar
        self.summary_bar = tk.Frame(self.root, bg="#111720", height=36)
        self.summary_bar.pack(fill="x")
        self.summary_bar.pack_propagate(False)

        self.lbl_total = tk.Label(self.summary_bar, text="TOTAL: 0",
            font=("Courier", 10), fg="#00d4ff", bg="#111720")
        self.lbl_total.pack(side="left", padx=20, pady=8)

        self.lbl_online = tk.Label(self.summary_bar, text="ONLINE: 0",
            font=("Courier", 10), fg="#39ff8f", bg="#111720")
        self.lbl_online.pack(side="left", padx=20)

        self.lbl_offline = tk.Label(self.summary_bar, text="OFFLINE: 0",
            font=("Courier", 10), fg="#ff2d55", bg="#111720")
        self.lbl_offline.pack(side="left", padx=20)

        self.lbl_windows = tk.Label(self.summary_bar, text="WINDOWS: 0",
            font=("Courier", 10), fg="#00d4ff", bg="#111720")
        self.lbl_windows.pack(side="left", padx=20)

        tk.Label(self.summary_bar, text="Auto-refresh every 5s",
            font=("Courier", 9), fg="#3a4a5a", bg="#111720").pack(side="right", padx=20)

        # ── Table
        frame = tk.Frame(self.root, bg="#080b10")
        frame.pack(fill="both", expand=True, padx=12, pady=10)

        cols = ("Hostname", "IP Address", "OS", "CPU %",
                "RAM Used", "RAM %", "Disk %", "Uptime", "Last Seen", "Status")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.Treeview",
            background="#0d1118", foreground="#b0c4d8",
            fieldbackground="#0d1118", rowheight=28,
            font=("Courier", 10))
        style.configure("Dark.Treeview.Heading",
            background="#111720", foreground="#3a4a5a",
            font=("Courier", 9, "bold"), relief="flat")
        style.map("Dark.Treeview",
            background=[("selected", "#1c2535")])

        self.tree = ttk.Treeview(frame, columns=cols,
                                  show="headings", style="Dark.Treeview")

        widths = [140, 130, 130, 70, 100, 70, 70, 80, 90, 90]
        for col, w in zip(cols, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="center")

        # Tag colors
        self.tree.tag_configure("online",  foreground="#39ff8f")
        self.tree.tag_configure("offline", foreground="#ff2d55")

        sb = ttk.Scrollbar(frame, orient="vertical",
                           command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Action buttons
        btn_frame = tk.Frame(self.root, bg="#080b10")
        btn_frame.pack(fill="x", padx=12, pady=(0,10))

        tk.Button(btn_frame, text="Details", command=self._details_selected,
                  bg="#0d1118", fg="#39ff8f", relief="raised").pack(side="left", padx=6)
        tk.Button(btn_frame, text="Logoff Selected", command=self._logoff_selected,
                  bg="#0d1118", fg="#ff9500", relief="raised").pack(side="right", padx=6)
        tk.Button(btn_frame, text="Restart Selected", command=self._restart_selected,
                  bg="#0d1118", fg="#ff2d55", relief="raised").pack(side="right", padx=6)
        tk.Button(btn_frame, text="Shutdown Selected", command=self._shutdown_selected,
                  bg="#0d1118", fg="#00d4ff", relief="raised").pack(side="right", padx=6)

    def _shutdown_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Please select a client row to shutdown.")
            return
        item = sel[0]
        vals = self.tree.item(item, "values")
        ip = vals[1]

        if not messagebox.askyesno("Confirm Shutdown", f"Shutdown remote PC at {ip}?"):
            return

        # send shutdown command with password
        ok = send_command_to_client(ip, {"action": "shutdown", "password": PASSWORD})
        if not ok:
            messagebox.showerror("Send Failed", f"Could not send shutdown to {ip}.")
        else:
            messagebox.showinfo("Sent", f"Shutdown command scheduled for {ip}.")

    def _restart_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Please select a client row to restart.")
            return
        item = sel[0]
        vals = self.tree.item(item, "values")
        ip = vals[1]

        if not messagebox.askyesno("Confirm Restart", f"Restart remote PC at {ip}?"):
            return

        ok = send_command_to_client(ip, {"action": "restart", "password": PASSWORD})
        if not ok:
            messagebox.showerror("Send Failed", f"Could not send restart to {ip}.")
        else:
            messagebox.showinfo("Sent", f"Restart command scheduled for {ip}.")

    def _logoff_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Please select a client row to logoff.")
            return
        item = sel[0]
        vals = self.tree.item(item, "values")
        ip = vals[1]

        if not messagebox.askyesno("Confirm Logoff", f"Logoff user on PC at {ip}?"):
            return

        ok = send_command_to_client(ip, {"action": "logoff", "password": PASSWORD})
        if not ok:
            messagebox.showerror("Send Failed", f"Could not send logoff to {ip}.")
        else:
            messagebox.showinfo("Sent", f"Logoff command scheduled for {ip}.")

    def _details_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Please select a client row to view details.")
            return
        item = sel[0]
        vals = self.tree.item(item, "values")
        ip = vals[1]

        with clients_lock:
            info = clients_data.get(ip, {})

        if not info:
            messagebox.showinfo("No Data", f"No data available for {ip}")
            return

        # Create details window
        details_win = tk.Toplevel(self.root)
        details_win.title(f"PC Details — {info.get('hostname', ip)}")
        details_win.geometry("500x500")
        details_win.resizable(True, True)
        details_win.configure(bg="#080b10")

        # Create frame with scrollbar
        canvas = tk.Canvas(details_win, bg="#080b10", highlightthickness=0)
        scrollbar = ttk.Scrollbar(details_win, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg="#080b10")

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Title
        tk.Label(scroll_frame, text=f"Details: {info.get('hostname', 'Unknown')}",
                 font=("Courier", 12, "bold"), fg="#00d4ff", bg="#080b10").pack(anchor="w", padx=12, pady=10)

        # Details
        details_fields = [
            ("Hostname", info.get("hostname", "—")),
            ("IP Address", ip),
            ("OS", info.get("os", "—")),
            ("CPU Usage", f"{info.get('cpu_percent', 0):.1f}%"),
            ("RAM Total", f"{info.get('ram_total_gb', 0):.1f} GB"),
            ("RAM Used", f"{info.get('ram_used_gb', 0):.1f} GB"),
            ("RAM Usage", f"{info.get('ram_percent', 0):.1f}%"),
            ("Disk Total", f"{info.get('disk_total_gb', 0):.1f} GB"),
            ("Disk Used", f"{info.get('disk_used_gb', 0):.1f} GB"),
            ("Disk Usage", f"{info.get('disk_percent', 0):.1f}%"),
            ("Uptime", info.get("uptime", "—")),
            ("Last Seen", info.get("last_seen", "—")),
            ("Status", "ONLINE" if info.get("connected") else "OFFLINE"),
        ]

        for label, value in details_fields:
            frame = tk.Frame(scroll_frame, bg="#111720", highlightbackground="#1c2535", highlightthickness=1)
            frame.pack(fill="x", padx=10, pady=3)

            tk.Label(frame, text=label, font=("Courier", 9), fg="#3a4a5a", bg="#111720", width=20, anchor="w").pack(side="left", padx=10, pady=6)
            tk.Label(frame, text=str(value), font=("Courier", 9, "bold"), fg="#b0c4d8", bg="#111720", anchor="w").pack(side="left", fill="x", expand=True, padx=5)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        total, online, offline, windows_count = 0, 0, 0, 0

        with clients_lock:
            data = dict(clients_data)

        for ip, info in data.items():
            total += 1
            conn = info.get("connected", False)
            if conn: online += 1
            else:    offline += 1

            # Count Windows PCs
            os_info = info.get("os", "")
            if "Windows" in os_info:
                windows_count += 1

            status = "ONLINE" if conn else "OFFLINE"
            tag    = "online" if conn else "offline"

            ram_used = f"{info.get('ram_used_gb',0):.1f}/{info.get('ram_total_gb',0):.1f} GB"

            self.tree.insert("", "end", values=(
                info.get("hostname", "—"),
                ip,
                info.get("os", "—"),
                f"{info.get('cpu_percent', 0):.1f}%",
                ram_used,
                f"{info.get('ram_percent', 0):.1f}%",
                f"{info.get('disk_percent', 0):.1f}%",
                info.get("uptime", "—"),
                info.get("last_seen", "—"),
                status
            ), tags=(tag,))

        self.lbl_total.config(text=f"TOTAL: {total}")
        self.lbl_online.config(text=f"ONLINE: {online}")
        self.lbl_offline.config(text=f"OFFLINE: {offline}")
        self.lbl_windows.config(text=f"WINDOWS: {windows_count}")

    def _poll_queue(self):
        """Check ui_queue every 200ms and refresh if needed"""
        try:
            while True:
                msg, _ = ui_queue.get_nowait()
                if msg == "refresh":
                    self.refresh_table()
        except queue.Empty:
            pass
        self.root.after(200, self._poll_queue)

    def _tick(self):
        self.lbl_clock.config(
            text=datetime.now().strftime("%H:%M:%S  %d/%m/%Y"))
        self.root.after(1000, self._tick)

# ── Main ───────────────────────────────────────────────────
def main():
    add_to_startup()

    # Start WebSocket server in background thread
    loop = asyncio.new_event_loop()
    server_thread = threading.Thread(
        target=run_server_loop, args=(loop,), daemon=True)
    server_thread.start()

    # tkinter GUI
    root = tk.Tk()
    app  = MasterApp(root)
    make_tray(root)

    root.mainloop()

if __name__ == "__main__":
    main()