"""
Travian Account Manager
A desktop tool for planning and managing your Travian account.
Data is stored in CSV files. No passwords required.

Folder structure:
  travian_data/
    accounts.csv                        ← registry of all accounts
    EU2_Deonnar/                        ← one subfolder per account
      villages.csv                      ← village list (coord_x, coord_y separate)
      snapshots/                        ← historical snapshots for graphing
        2024-01-15_123456_villages.csv
        ...
"""

import tkinter as tk
from tkinter import messagebox, simpledialog
import csv
import shutil
from datetime import datetime
from pathlib import Path

# ─── Constants ────────────────────────────────────────────────────────────────

DATA_DIR      = Path("travian_data")
ACCOUNTS_FILE = DATA_DIR / "accounts.csv"

TRIBES   = ["Romans", "Teutons", "Gauls", "Egyptians", "Huns", "Spartans", "Natars"]
STATUSES = ["active", "archived"]

TRIBE_ICON = {
    "Romans":    "🦅",
    "Teutons":   "🪓",
    "Gauls":     "🌿",
    "Egyptians": "𓂀",
    "Huns":      "🏹",
    "Spartans":  "🛡",
    "Natars":    "💀",
}

# Color palette — dark strategy-game aesthetic
BG_DARK        = "#0f1117"
BG_MID         = "#161b27"
BG_PANEL       = "#1c2333"
BG_HOVER       = "#242d42"
ACCENT         = "#c8963e"
ACCENT_DIM     = "#7a5a22"
TEXT_PRIMARY   = "#e8dcc8"
TEXT_SECONDARY = "#8a9ab5"
TEXT_MUTED     = "#4a5568"
BORDER         = "#2a3450"
GREEN_ACCENT   = "#27ae60"
ARCHIVED_COL   = "#5a6a8a"
VILLAGE_SEL    = "#1e2d4a"

FONT_TITLE   = ("Georgia", 18, "bold")
FONT_HEADING = ("Georgia", 11, "bold")
FONT_BODY    = ("Consolas", 10)
FONT_SMALL   = ("Consolas", 9)


# ─── Path helpers ─────────────────────────────────────────────────────────────

def account_key(server: str, account: str) -> str:
    return f"{server.upper()}_{account}"

def account_dir(server: str, account: str) -> Path:
    return DATA_DIR / account_key(server, account)

def snapshots_dir(server: str, account: str) -> Path:
    return account_dir(server, account) / "snapshots"

def villages_file(server: str, account: str) -> Path:
    return account_dir(server, account) / "villages.csv"


# ─── Data layer ───────────────────────────────────────────────────────────────

ACCOUNT_FIELDS = ["server", "account", "tribe", "status"]
VILLAGE_FIELDS = ["village_name", "coord_x", "coord_y", "population"]

def ensure_data_dir():
    DATA_DIR.mkdir(exist_ok=True)
    if not ACCOUNTS_FILE.exists():
        with open(ACCOUNTS_FILE, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=ACCOUNT_FIELDS).writeheader()

def load_accounts() -> list:
    ensure_data_dir()
    with open(ACCOUNTS_FILE, newline="") as f:
        return list(csv.DictReader(f))

def _rewrite_accounts(accounts: list):
    with open(ACCOUNTS_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ACCOUNT_FIELDS)
        w.writeheader()
        w.writerows(accounts)

def save_new_account(server: str, account: str, tribe: str, status: str = "active"):
    ensure_data_dir()
    accounts = load_accounts()
    key = account_key(server, account)
    if any(account_key(a["server"], a["account"]) == key for a in accounts):
        return
    accounts.append({"server": server.upper(), "account": account,
                     "tribe": tribe, "status": status})
    _rewrite_accounts(accounts)
    # Create folder skeleton
    adir = account_dir(server, account)
    adir.mkdir(parents=True, exist_ok=True)
    snapshots_dir(server, account).mkdir(exist_ok=True)
    vfile = villages_file(server, account)
    if not vfile.exists():
        with open(vfile, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=VILLAGE_FIELDS).writeheader()

def update_account_status(server: str, account: str, new_status: str):
    accounts = load_accounts()
    key = account_key(server, account)
    for a in accounts:
        if account_key(a["server"], a["account"]) == key:
            a["status"] = new_status
    _rewrite_accounts(accounts)

def get_account(server: str, account: str):
    for a in load_accounts():
        if account_key(a["server"], a["account"]) == account_key(server, account):
            return a
    return None

# ── Villages ──────────────────────────────────────────────────────────────────

def load_villages(server: str, account: str) -> list:
    vfile = villages_file(server, account)
    if not vfile.exists():
        return []
    with open(vfile, newline="") as f:
        return list(csv.DictReader(f))

def _rewrite_villages(server: str, account: str, villages: list):
    with open(villages_file(server, account), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=VILLAGE_FIELDS)
        w.writeheader()
        w.writerows(villages)

def add_village(server: str, account: str, name: str,
                coord_x: str = "", coord_y: str = "", population: str = ""):
    villages = load_villages(server, account)
    villages.append({"village_name": name, "coord_x": coord_x,
                     "coord_y": coord_y, "population": population})
    _rewrite_villages(server, account, villages)

def take_snapshot(server: str, account: str):
    src = villages_file(server, account)
    if not src.exists():
        return None
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dst = snapshots_dir(server, account) / f"{stamp}_villages.csv"
    shutil.copy2(src, dst)
    return dst


# ─── Styled widget helpers ─────────────────────────────────────────────────────

def styled_button(parent, text, command=None, accent=False, small=False, danger=False):
    if danger:
        bg, fg = "#3a1010", "#e05555"
    elif accent:
        bg, fg = ACCENT, BG_DARK
    else:
        bg, fg = BG_HOVER, TEXT_PRIMARY
    font = FONT_SMALL if small else FONT_BODY
    btn = tk.Button(
        parent, text=text, command=command,
        bg=bg, fg=fg, font=font, relief="flat", cursor="hand2",
        padx=10, pady=4,
        activebackground=ACCENT_DIM if accent else BORDER,
        activeforeground=TEXT_PRIMARY, bd=0
    )
    return btn

def section_label(parent, text, bg=BG_PANEL):
    return tk.Label(parent, text=text.upper(),
                    font=("Consolas", 8, "bold"), bg=bg, fg=TEXT_MUTED, anchor="w")

def nav_button(parent, text, command=None):
    btn = tk.Button(
        parent, text=f"  {text}", command=command,
        bg=BG_PANEL, fg=TEXT_SECONDARY, font=FONT_BODY,
        relief="flat", anchor="w", cursor="hand2",
        padx=8, pady=6,
        activebackground=BG_HOVER, activeforeground=ACCENT, bd=0
    )
    btn.bind("<Enter>", lambda e: btn.config(bg=BG_HOVER, fg=ACCENT))
    btn.bind("<Leave>", lambda e: btn.config(bg=BG_PANEL, fg=TEXT_SECONDARY))
    return btn

def make_separator(parent, bg=None):
    return tk.Frame(parent, bg=bg or BORDER, height=1)

def styled_entry(parent, var, width=None):
    kwargs = dict(textvariable=var, bg=BG_MID, fg=TEXT_PRIMARY,
                  insertbackground=ACCENT, font=FONT_BODY,
                  relief="flat", bd=0, highlightthickness=1,
                  highlightbackground=BORDER, highlightcolor=ACCENT)
    if width:
        kwargs["width"] = width
    return tk.Entry(parent, **kwargs)


# ─── Add Account Dialog ───────────────────────────────────────────────────────

class AddAccountDialog(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.result = None
        self.title("Add Account")
        self.configure(bg=BG_DARK)
        self.resizable(False, False)
        self.grab_set()
        self._build()
        self.wait_window()

    def _build(self):
        pad = tk.Frame(self, bg=BG_DARK)
        pad.pack(padx=28, pady=24, fill="both")

        tk.Label(pad, text="New Account", font=FONT_HEADING,
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, 16))

        # Server & account name
        for label, attr in [("Server name (e.g. EU2)", "server_var"),
                             ("Account / player name",  "account_var")]:
            var = tk.StringVar()
            setattr(self, attr, var)
            tk.Label(pad, text=label, font=FONT_SMALL,
                     bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor="w")
            styled_entry(pad, var).pack(fill="x", pady=(2, 10), ipady=4)

        # Tribe selector
        tk.Label(pad, text="Tribe", font=FONT_SMALL,
                 bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor="w")
        self.tribe_var = tk.StringVar(value=TRIBES[0])
        tribe_frame = tk.Frame(pad, bg=BG_DARK)
        tribe_frame.pack(fill="x", pady=(2, 10))
        # Two columns
        col_a = tk.Frame(tribe_frame, bg=BG_DARK)
        col_b = tk.Frame(tribe_frame, bg=BG_DARK)
        col_a.pack(side="left", padx=(0, 16))
        col_b.pack(side="left")
        for i, t in enumerate(TRIBES):
            col = col_a if i < 4 else col_b
            icon = TRIBE_ICON.get(t, "")
            tk.Radiobutton(col, text=f"{icon} {t}", variable=self.tribe_var, value=t,
                           bg=BG_DARK, fg=TEXT_SECONDARY, selectcolor=BG_MID,
                           activebackground=BG_DARK, activeforeground=ACCENT,
                           font=FONT_SMALL, cursor="hand2").pack(anchor="w")

        # Status selector
        tk.Label(pad, text="Status", font=FONT_SMALL,
                 bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor="w", pady=(6, 0))
        self.status_var = tk.StringVar(value="active")
        sf = tk.Frame(pad, bg=BG_DARK)
        sf.pack(fill="x", pady=(2, 16))
        for s in STATUSES:
            tk.Radiobutton(sf, text=s.capitalize(), variable=self.status_var, value=s,
                           bg=BG_DARK, fg=TEXT_SECONDARY, selectcolor=BG_MID,
                           activebackground=BG_DARK, activeforeground=ACCENT,
                           font=FONT_SMALL, cursor="hand2").pack(side="left", padx=(0, 16))

        btn_row = tk.Frame(pad, bg=BG_DARK)
        btn_row.pack(fill="x")
        styled_button(btn_row, "Create Account", command=self._submit, accent=True).pack(side="left")
        styled_button(btn_row, "Cancel", command=self.destroy, small=True).pack(side="left", padx=8)

    def _submit(self):
        server  = self.server_var.get().strip().upper()
        account = self.account_var.get().strip()
        if not server or not account:
            messagebox.showwarning("Missing info",
                "Please fill in both server and account name.", parent=self)
            return
        self.result = (server, account, self.tribe_var.get(), self.status_var.get())
        self.destroy()


# ─── Add Village Dialog ───────────────────────────────────────────────────────

class AddVillageDialog(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.result = None
        self.title("Add Village")
        self.configure(bg=BG_DARK)
        self.resizable(False, False)
        self.grab_set()
        self._build()
        self.wait_window()

    def _build(self):
        pad = tk.Frame(self, bg=BG_DARK)
        pad.pack(padx=28, pady=24)

        tk.Label(pad, text="Add Village", font=FONT_HEADING,
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, 16))

        self.name_var = tk.StringVar()
        self.x_var    = tk.StringVar()
        self.y_var    = tk.StringVar()
        self.pop_var  = tk.StringVar()

        tk.Label(pad, text="Village name", font=FONT_SMALL,
                 bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor="w")
        styled_entry(pad, self.name_var).pack(fill="x", pady=(2, 10), ipady=4)

        # X and Y coordinates side by side
        coord_row = tk.Frame(pad, bg=BG_DARK)
        coord_row.pack(fill="x", pady=(0, 10))
        for label, var, side in [("Coord X", self.x_var, "left"),
                                  ("Coord Y", self.y_var, "right")]:
            col = tk.Frame(coord_row, bg=BG_DARK)
            col.pack(side=side, fill="x", expand=True,
                     padx=(0 if side == "left" else 8, 0))
            tk.Label(col, text=label, font=FONT_SMALL,
                     bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor="w")
            styled_entry(col, var, width=10).pack(fill="x", ipady=4)

        tk.Label(pad, text="Population (optional)", font=FONT_SMALL,
                 bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor="w")
        styled_entry(pad, self.pop_var).pack(fill="x", pady=(2, 14), ipady=4)

        btn_row = tk.Frame(pad, bg=BG_DARK)
        btn_row.pack(fill="x")
        styled_button(btn_row, "Add Village", command=self._submit, accent=True).pack(side="left")
        styled_button(btn_row, "Cancel", command=self.destroy, small=True).pack(side="left", padx=8)

    def _submit(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing info", "Village name is required.", parent=self)
            return
        self.result = {
            "village_name": name,
            "coord_x":      self.x_var.get().strip(),
            "coord_y":      self.y_var.get().strip(),
            "population":   self.pop_var.get().strip(),
        }
        self.destroy()


# ─── Login Screen ─────────────────────────────────────────────────────────────

class LoginScreen(tk.Frame):
    def __init__(self, master, on_login):
        super().__init__(master, bg=BG_DARK)
        self.on_login = on_login
        self._accounts = []
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        header = tk.Frame(self, bg=BG_DARK)
        header.pack(pady=(50, 10))
        tk.Label(header, text="⚔", font=("Georgia", 36), bg=BG_DARK, fg=ACCENT).pack()
        tk.Label(header, text="TRAVIAN MANAGER", font=("Georgia", 22, "bold"),
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack()
        tk.Label(header, text="Account Planning & Management Tool",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_SECONDARY).pack(pady=(4, 0))

        panel = tk.Frame(self, bg=BG_PANEL)
        panel.pack(padx=80, pady=20, fill="both", expand=True)
        inner = tk.Frame(panel, bg=BG_PANEL)
        inner.pack(fill="both", expand=True, padx=20, pady=20)

        tk.Label(inner, text="SELECT ACCOUNT", font=("Consolas", 9, "bold"),
                 bg=BG_PANEL, fg=TEXT_MUTED).pack(anchor="w")
        tk.Label(inner, text="Double-click to open  ·  🟢 Active  ·  🔵 Archived",
                 font=FONT_SMALL, bg=BG_PANEL, fg=TEXT_MUTED).pack(anchor="w", pady=(0, 10))

        list_frame = tk.Frame(inner, bg=BORDER)
        list_frame.pack(fill="both", expand=True)
        scrollbar = tk.Scrollbar(list_frame, bg=BG_MID, troughcolor=BG_DARK,
                                  relief="flat", bd=0, width=10)
        scrollbar.pack(side="right", fill="y")
        self.account_list = tk.Listbox(
            list_frame, bg=BG_MID, fg=TEXT_PRIMARY, font=FONT_BODY,
            selectbackground=ACCENT_DIM, selectforeground=TEXT_PRIMARY,
            relief="flat", bd=0, highlightthickness=0,
            yscrollcommand=scrollbar.set, activestyle="none"
        )
        self.account_list.pack(fill="both", expand=True, padx=1, pady=1)
        scrollbar.config(command=self.account_list.yview)
        self.account_list.bind("<Double-Button-1>", self._on_double_click)

        self._refresh_accounts()

        btn_row = tk.Frame(inner, bg=BG_PANEL)
        btn_row.pack(fill="x", pady=(12, 0))
        styled_button(btn_row, "+ Add Account", command=self._add_account,
                      accent=True).pack(side="left")
        styled_button(btn_row, "Open", command=self._open_selected).pack(side="left", padx=8)
        styled_button(btn_row, "Archive / Restore", command=self._toggle_status,
                      small=True).pack(side="left")
        styled_button(btn_row, "Remove", command=self._remove_account,
                      small=True, danger=True).pack(side="right")

        tk.Label(self, text=f"Data folder: {DATA_DIR.resolve()}",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(pady=(0, 16))

    def _refresh_accounts(self):
        self.account_list.delete(0, tk.END)
        self._accounts = load_accounts()
        for a in self._accounts:
            icon = "🟢" if a.get("status") == "active" else "🔵"
            ticon = TRIBE_ICON.get(a.get("tribe", ""), "")
            self.account_list.insert(
                tk.END,
                f"  {icon}  [{a['server']}]  {a['account']}   {ticon} {a.get('tribe','')}"
            )

    def _selected(self):
        sel = self.account_list.curselection()
        return self._accounts[sel[0]] if sel else None

    def _add_account(self):
        dlg = AddAccountDialog(self)
        if dlg.result:
            save_new_account(*dlg.result)
            self._refresh_accounts()

    def _toggle_status(self):
        a = self._selected()
        if not a:
            messagebox.showinfo("No Selection", "Select an account first.")
            return
        new = "archived" if a.get("status") == "active" else "active"
        update_account_status(a["server"], a["account"], new)
        self._refresh_accounts()

    def _remove_account(self):
        a = self._selected()
        if not a:
            return
        if not messagebox.askyesno("Remove Account",
                f"Remove [{a['server']}] {a['account']} from the list?\n\n"
                "Note: the data folder will NOT be deleted.", parent=self):
            return
        accounts = [x for x in load_accounts()
                    if account_key(x["server"], x["account"]) !=
                       account_key(a["server"], a["account"])]
        _rewrite_accounts(accounts)
        self._refresh_accounts()

    def _on_double_click(self, _e):
        self._open_selected()

    def _open_selected(self):
        a = self._selected()
        if not a:
            messagebox.showinfo("No Selection", "Please select an account first.")
            return
        self.on_login(a["server"], a["account"])


# ─── Main Application Window ──────────────────────────────────────────────────

class MainApp(tk.Frame):
    def __init__(self, master, server, account, on_logout):
        super().__init__(master, bg=BG_DARK)
        self.server  = server
        self.account = account
        self.on_logout = on_logout
        self.selected_village = None

        self.account_data = get_account(server, account) or {}
        self.tribe  = self.account_data.get("tribe", "")
        self.status = self.account_data.get("status", "active")
        self.is_archived = (self.status == "archived")

        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        self._build_topbar()
        body = tk.Frame(self, bg=BG_DARK)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        self._build_left_panel(body)
        self._build_center(body)
        self._build_right_panel(body)

    # ── Top bar ──────────────────────────────────────────────────────────────

    def _build_topbar(self):
        bar = tk.Frame(self, bg=BG_MID, height=46)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        tk.Label(bar, text="⚔  TRAVIAN MANAGER", font=("Georgia", 12, "bold"),
                 bg=BG_MID, fg=ACCENT).pack(side="left", padx=16)

        tribe_icon = TRIBE_ICON.get(self.tribe, "")
        for label, value, col in [
            ("Server: ", self.server, ACCENT),
            ("  Account: ", self.account, TEXT_PRIMARY),
            (f"  {tribe_icon} ", self.tribe, TEXT_SECONDARY),
        ]:
            tk.Label(bar, text=label, font=FONT_SMALL, bg=BG_MID, fg=TEXT_MUTED).pack(side="left")
            tk.Label(bar, text=value, font=("Consolas", 10, "bold"),
                     bg=BG_MID, fg=col).pack(side="left")

        status_col = GREEN_ACCENT if not self.is_archived else ARCHIVED_COL
        tk.Label(bar, text=f"  ● {self.status.upper()}",
                 font=("Consolas", 9, "bold"), bg=BG_MID, fg=status_col).pack(side="left", padx=8)

        styled_button(bar, "⇦ Logout", command=self.on_logout,
                      small=True).pack(side="right", padx=12, pady=8)

        if self.is_archived:
            banner = tk.Frame(self, bg="#1e1010")
            banner.pack(fill="x")
            tk.Label(banner,
                     text="🔵  ARCHIVED  —  This server has ended. Data is read-only.",
                     font=FONT_SMALL, bg="#1e1010", fg="#c07070").pack(pady=5)

        make_separator(self).pack(fill="x")

    # ── Left panel ───────────────────────────────────────────────────────────

    def _build_left_panel(self, parent):
        self.left_panel = tk.Frame(parent, bg=BG_PANEL, width=215)
        self.left_panel.grid(row=0, column=0, sticky="nsew")
        self.left_panel.pack_propagate(False)
        self._rebuild_account_nav()

    def _rebuild_account_nav(self):
        for w in self.left_panel.winfo_children():
            w.destroy()

        pad = tk.Frame(self.left_panel, bg=BG_PANEL)
        pad.pack(fill="both", expand=True)

        section_label(pad, "Account Overview").pack(fill="x", padx=12, pady=(14, 4))

        for label, cmd in [
            ("📊  Production Info",  self._show_production_info),
            ("⚔   Deployed Troops", self._show_deployed_troops),
            ("🗺   Troop Locations", self._show_troop_locations),
            ("⚡  Net Production",   self._show_net_production),
        ]:
            nav_button(pad, label, command=cmd).pack(fill="x")

        make_separator(pad).pack(fill="x", padx=8, pady=10)

        self.village_nav_frame = tk.Frame(pad, bg=BG_PANEL)
        self.village_nav_frame.pack(fill="x")

        make_separator(pad).pack(fill="x", padx=8, pady=6)

        snap_btn = styled_button(pad, "📸 Take Snapshot",
                                 command=self._take_snapshot,
                                 small=True,
                                 accent=(not self.is_archived))
        snap_btn.pack(fill="x", padx=8, pady=(0, 8))
        if self.is_archived:
            snap_btn.config(state="disabled", fg=TEXT_MUTED, bg=BG_HOVER)

    def _show_village_submenu(self, village_name):
        for w in self.village_nav_frame.winfo_children():
            w.destroy()

        vhdr = tk.Frame(self.village_nav_frame, bg=VILLAGE_SEL)
        vhdr.pack(fill="x")
        tk.Label(vhdr, text=f"🏘 {village_name}", font=("Georgia", 10, "bold"),
                 bg=VILLAGE_SEL, fg=ACCENT, anchor="w").pack(fill="x", padx=12, pady=6)

        section_label(self.village_nav_frame, "Village Menu").pack(fill="x", padx=12, pady=(6, 4))

        for label, cmd in [
            ("⚙   Setup",          lambda: self._show_village_setup(village_name)),
            ("🔄  Trade Routes",    lambda: self._show_trade_routes(village_name)),
            ("📋  Set Trade Route", lambda: self._show_set_trade_route(village_name)),
            ("🪖  Troops Sent Out", lambda: self._show_troops_sent_out(village_name)),
        ]:
            nav_button(self.village_nav_frame, label, command=cmd).pack(fill="x")

    # ── Center ───────────────────────────────────────────────────────────────

    def _build_center(self, parent):
        self.center = tk.Frame(parent, bg=BG_DARK)
        self.center.grid(row=0, column=1, sticky="nsew", padx=1)
        self._show_welcome()

    def _clear_center(self):
        for w in self.center.winfo_children():
            w.destroy()

    def _content_header(self, title, subtitle=""):
        hdr = tk.Frame(self.center, bg=BG_DARK)
        hdr.pack(fill="x", padx=24, pady=(24, 0))
        tk.Label(hdr, text=title, font=FONT_TITLE, bg=BG_DARK, fg=TEXT_PRIMARY).pack(anchor="w")
        if subtitle:
            tk.Label(hdr, text=subtitle, font=FONT_SMALL,
                     bg=BG_DARK, fg=TEXT_MUTED).pack(anchor="w", pady=(2, 0))
        make_separator(self.center).pack(fill="x", padx=24, pady=12)

    def _placeholder_card(self, title, description):
        card = tk.Frame(self.center, bg=BG_PANEL)
        card.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        inner = tk.Frame(card, bg=BG_PANEL)
        inner.pack(expand=True)
        tk.Label(inner, text="[ Placeholder ]", font=("Consolas", 11, "bold"),
                 bg=BG_PANEL, fg=TEXT_MUTED).pack(pady=(60, 8))
        tk.Label(inner, text=title, font=FONT_HEADING,
                 bg=BG_PANEL, fg=TEXT_SECONDARY).pack()
        tk.Label(inner, text=description, font=FONT_SMALL, bg=BG_PANEL,
                 fg=TEXT_MUTED, wraplength=440, justify="center").pack(pady=(6, 0))

    def _show_welcome(self):
        self._clear_center()
        ticon = TRIBE_ICON.get(self.tribe, "")
        self._content_header(
            f"Welcome back, {self.account}",
            f"{self.server}  ·  {ticon} {self.tribe}  ·  {self.status.upper()}"
        )
        self._placeholder_card(
            "Select a view from the left panel",
            "Use the account-wide options for production stats, troop info, and more.\n"
            "Click a village on the right to manage it.\n\n"
            f"Account folder: {account_dir(self.server, self.account)}"
        )

    # ── Account-wide views ────────────────────────────────────────────────────

    def _show_production_info(self):
        self._clear_center()
        self._content_header("Production Info", "Resource output across all villages")
        self._placeholder_card("Production Info",
            f"Lumber, clay, iron, crop per hour per village.\n"
            f"Tribe bonuses for {self.tribe} will be factored in.")

    def _show_deployed_troops(self):
        self._clear_center()
        self._content_header("Deployed Troops", "Troops currently away from home")
        self._placeholder_card("Deployed Troops",
            f"All {self.tribe} troops on the move: raids, attacks, support, settlers.")

    def _show_troop_locations(self):
        self._clear_center()
        self._content_header("Troop Locations", "Where all your troops are")
        self._placeholder_card("Troop Locations",
            "Troop positions across the game world, shown with X/Y coordinates.")

    def _show_net_production(self):
        self._clear_center()
        self._content_header("Net Production", "Production minus troop upkeep")
        self._placeholder_card("Net Production",
            "Total net resources per hour after subtracting upkeep costs.")

    # ── Village views ─────────────────────────────────────────────────────────

    def _show_village_setup(self, village):
        self._clear_center()
        self._content_header(f"{village}  —  Setup", "Buildings and configuration")
        self._placeholder_card("Village Setup",
            "Building levels, rally point, and village notes.\n"
            f"Tribe-specific buildings for {self.tribe} will appear here.")

    def _show_trade_routes(self, village):
        self._clear_center()
        self._content_header(f"{village}  —  Trade Routes", "Active trade routes")
        self._placeholder_card("Trade Routes",
            "List of active resource routes to/from this village.")

    def _show_set_trade_route(self, village):
        self._clear_center()
        self._content_header(f"{village}  —  Set Trade Route", "Configure a trade route")
        self._placeholder_card("Set Trade Route",
            "Destination village by X/Y coordinates, resource type, amount, and interval.")

    def _show_troops_sent_out(self, village):
        self._clear_center()
        self._content_header(f"{village}  —  Troops Sent Out", "Outgoing troop movements")
        self._placeholder_card("Troops Sent Out",
            "Outgoing raids, attacks, reinforcements, and settlers from this village.")

    # ── Snapshot ──────────────────────────────────────────────────────────────

    def _take_snapshot(self):
        dst = take_snapshot(self.server, self.account)
        if dst:
            messagebox.showinfo("Snapshot Saved", f"Saved to:\n{dst}", parent=self)
        else:
            messagebox.showwarning("Snapshot Failed",
                "No village data found to snapshot.", parent=self)

    # ── Right panel: village list ─────────────────────────────────────────────

    def _build_right_panel(self, parent):
        right = tk.Frame(parent, bg=BG_PANEL, width=215)
        right.grid(row=0, column=2, sticky="nsew")
        right.pack_propagate(False)

        hdr = tk.Frame(right, bg=BG_MID)
        hdr.pack(fill="x")
        tk.Label(hdr, text="VILLAGES", font=("Consolas", 9, "bold"),
                 bg=BG_MID, fg=TEXT_MUTED).pack(side="left", padx=12, pady=8)
        if not self.is_archived:
            styled_button(hdr, "+", command=self._add_village_dialog,
                          small=True, accent=True).pack(side="right", padx=8, pady=6)

        make_separator(right).pack(fill="x")

        vlist_frame = tk.Frame(right, bg=BG_PANEL)
        vlist_frame.pack(fill="both", expand=True)
        scroll = tk.Scrollbar(vlist_frame, bg=BG_MID, troughcolor=BG_DARK,
                               relief="flat", bd=0, width=8)
        scroll.pack(side="right", fill="y")
        self.village_listbox = tk.Listbox(
            vlist_frame, bg=BG_PANEL, fg=TEXT_PRIMARY, font=FONT_BODY,
            selectbackground=VILLAGE_SEL, selectforeground=ACCENT,
            relief="flat", bd=0, highlightthickness=0,
            yscrollcommand=scroll.set, activestyle="none", cursor="hand2"
        )
        self.village_listbox.pack(fill="both", expand=True)
        scroll.config(command=self.village_listbox.yview)
        self.village_listbox.bind("<<ListboxSelect>>", self._on_village_select)

        self._refresh_village_list()

        make_separator(right).pack(fill="x")
        styled_button(right, "↺ Refresh", command=self._refresh_village_list,
                      small=True).pack(fill="x", padx=8, pady=6)

    def _refresh_village_list(self):
        self.villages = load_villages(self.server, self.account)
        self.village_listbox.delete(0, tk.END)
        if not self.villages:
            self.village_listbox.insert(tk.END, "  (no villages yet)")
            return
        for v in self.villages:
            x = v.get("coord_x", "?")
            y = v.get("coord_y", "?")
            self.village_listbox.insert(
                tk.END, f"  🏘 {v['village_name']}")
            # Coordinates as a dimmer sub-line feel
            self.village_listbox.insert(
                tk.END, f"      ({x} | {y})")

    def _on_village_select(self, _event):
        sel = self.village_listbox.curselection()
        if not sel or not self.villages:
            return
        # Each village occupies 2 rows in the listbox
        raw_idx = sel[0]
        village_idx = raw_idx // 2
        if village_idx >= len(self.villages):
            return
        village = self.villages[village_idx]
        name = village["village_name"]
        self.selected_village = name
        self._show_village_submenu(name)
        self._show_village_setup(name)

    def _add_village_dialog(self):
        dlg = AddVillageDialog(self)
        if dlg.result:
            d = dlg.result
            add_village(self.server, self.account,
                        d["village_name"], d["coord_x"], d["coord_y"], d["population"])
            self._refresh_village_list()


# ─── App Controller ───────────────────────────────────────────────────────────

class TravianApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Travian Manager")
        self.root.geometry("1160x730")
        self.root.minsize(960, 620)
        self.root.configure(bg=BG_DARK)
        try:
            self.root.tk.call("tk", "scaling", 1.2)
        except Exception:
            pass
        self.current_frame = None
        self._show_login()

    def _clear(self):
        if self.current_frame:
            self.current_frame.destroy()

    def _show_login(self):
        self._clear()
        self.root.title("Travian Manager — Select Account")
        self.current_frame = LoginScreen(self.root, on_login=self._on_login)

    def _on_login(self, server, account):
        self._clear()
        self.root.title(f"Travian Manager — [{server}] {account}")
        self.current_frame = MainApp(self.root, server, account,
                                     on_logout=self._show_login)

    def run(self):
        self.root.mainloop()


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = TravianApp()
    app.run()