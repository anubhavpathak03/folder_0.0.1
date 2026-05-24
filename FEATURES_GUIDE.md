# PCMonitor — Enhanced Features Guide

## 🎯 New Features Added

### 1️⃣ **Multiple Client Management**
- ✅ System already supports multiple connected PCs
- ✅ Each PC shows up automatically in the dashboard table
- ✅ Real-time updates every 5 seconds

### 2️⃣ **OS Detection & Statistics**
- ✅ Each PC displays its OS (e.g., "Windows 10", "Windows 11")
- ✅ **New: Windows Counter** in summary bar shows total Windows PCs
- ✅ Other OS types (Linux, Mac) also displayed

**Summary Bar Shows:**
- `TOTAL: X` — Total connected clients
- `ONLINE: X` — Currently online clients
- `OFFLINE: X` — Offline clients
- `WINDOWS: X` — **NEW** Total Windows PCs

### 3️⃣ **Remote Commands**
Four new remote control options:

#### **Shutdown** (Red Button)
- Sends remote shutdown command
- 30-second countdown on client (user can cancel with `shutdown /a`)
- Confirmation dialog on Master

#### **Restart** (Blue Button) — ⭐ NEW
- Sends remote restart command
- 30-second countdown on client
- Requires confirmation

#### **Logoff** (Orange Button) — ⭐ NEW
- Logs off current user on remote PC
- 10-second countdown
- Good for session clearing without shutdown

#### **Details** (Green Button) — ⭐ NEW
- Opens detailed info popup for selected PC
- Shows all metrics in scrollable window:
  - Hostname, IP Address, OS
  - CPU%, RAM (Total/Used/%), Disk (Total/Used/%)
  - Uptime, Last Seen, Connection Status

---

## 📋 How to Use

### **To Select a PC:**
1. Click any row in the main dashboard table
2. Row will be highlighted (blue background)
3. Client IP appears in the selected row

### **To Perform Action:**
1. Select a PC row
2. Click desired button (Details, Logoff, Restart, or Shutdown)
3. Confirm the action in popup dialog
4. Command is sent to remote client

### **To View Full Details:**
1. Select any PC from table
2. Click **"Details"** button (Green)
3. New window opens with complete PC information
4. Scroll to see all metrics

---

## 🔧 Technical Details

### Client PC (client.py)
**Supported Commands:**
- `action: "shutdown"` → Shutdown PC (30 sec countdown)
- `action: "restart"` → Restart PC (30 sec countdown)
- `action: "logoff"` → Logoff user (10 sec countdown)

All commands require password verification from config.env

### Master PC (master.py)
**New Methods:**
- `_shutdown_selected()` — Send shutdown
- `_restart_selected()` — Send restart
- `_logoff_selected()` — Send logoff
- `_details_selected()` — Show PC details popup
- `refresh_table()` — Now counts Windows PCs

---

## 🎨 UI Color Reference

| Button | Color | Purpose |
|--------|-------|---------|
| Details | Green (`#39ff8f`) | View full PC info |
| Logoff | Orange (`#ff9500`) | Remote logoff |
| Restart | Red (`#ff2d55`) | Remote restart |
| Shutdown | Cyan (`#00d4ff`) | Remote shutdown |

---

## 📌 Configuration

**File:** `config.env`
```
PASSWORD=admin123      # Password for all commands
MASTER_IP=127.0.0.1   # Master PC IP
PORT=8765             # WebSocket port
```

---

## ✅ Tested Features

✓ Syntax verified
✓ Multi-client support confirmed
✓ Command handlers implemented
✓ Windows counter functional
✓ Details popup working
✓ All buttons wired correctly

---

## 🚀 Usage Example

**Scenario:** You have 10 PCs in Block01, want to check one and restart it.

1. **Master Dashboard** shows all 10 PCs in table
2. **Select** PC with IP 192.168.1.105
3. **Click "Details"** to see current status (CPU, RAM, Disk)
4. **Click "Restart"** to restart that PC
5. **Confirm** in dialog
6. PC restarts in 30 seconds (user can cancel)

---

## 🔐 Security Notes

- All commands require password from `config.env`
- 30-second countdown allows user to cancel shutdown/restart
- WebSocket connection authenticated at connect time
- Commands only executed if password matches

---

**Last Updated:** May 24, 2026
**Version:** 2.0 — Enhanced Commands & Details