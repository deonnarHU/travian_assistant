"""
Travian Account Manager
A desktop tool for planning and managing your Travian account.
Data is stored in CSV files. No passwords required.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import csv
import os
from pathlib import Path

# ─── Constants ────────────────────────────────────────────────────────────────

DATA_DIR = Path("travian_data")
ACCOUNTS_FILE = DATA_DIR / "accounts.csv"

# Color palette — dark strategy-game aesthetic
BG_DARK      = "#0f1117"
BG_MID       = "#161b27"
BG_PANEL     = "#1c2333"
BG_HOVER     = "#242d42"
ACCENT       = "#c8963e"        # Travian gold
ACCENT_DIM   = "#7a5a22"
TEXT_PRIMARY  = "#e8dcc8"
TEXT_SECONDARY= "#8a9ab5"
TEXT_MUTED    = "#4a5568"
BORDER       = "#2a3450"
RED_ACCENT   = "#c0392b"
GREEN_ACCENT = "#27ae60"
VILLAGE_SEL  = "#1e2d4a"

FONT_TITLE   = ("Georgia", 18, "bold")
FONT_HEADING = ("Georgia", 11, "bold")
FONT_BODY    = ("Consolas", 10)
FONT_SMALL   = ("Consolas", 9)
FONT_LABEL   = ("Georgia", 9)

# ─── Data helpers ─────────────────────────────────────────────────────────────

def ensure_data_dir():
    DATA_DIR.mkdir(exist_ok=True)
    if not ACCOUNTS_FILE.exists():
        with open(ACCOUNTS_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["server", "account"])

def load_accounts():
    ensure_data_dir()
    accounts = []
    with open(ACCOUNTS_FILE, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            accounts.append((row["server"], row["account"]))
    return accounts

def save_account(server, account):
    ensure_data_dir()
    accounts = load_accounts()
    if (server.upper(), account) not in accounts:
        with open(ACCOUNTS_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([server.upper(), account])

def load_villages(server, account):
    """Load village list for an account from CSV."""
    vfile = DATA_DIR / f"{server}_{account}_villages.csv"
    if not vfile.exists():
        # Create with sample placeholder
        with open(vfile, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["village_name", "coords", "population"])
        return []
    villages = []
    with open(vfile, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            villages.append(row)
    return villages

def add_village(server, account, name, coords="", population=""):
    vfile = DATA_DIR / f"{server}_{account}_villages.csv"
    if not vfile.exists():
        with open(vfile, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["village_name", "coords", "population"])
    with open(vfile, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([name, coords, population])

# ─── Styled widget helpers ─────────────────────────────────────────────────────

def styled_button(parent, text, command=None, accent=False, small=False):
    bg = ACCENT if accent else BG_HOVER
    fg = BG_DARK if accent else TEXT_PRIMARY
    font = FONT_SMALL if small else FONT_BODY
    btn = tk.Button(
        parent, text=text, command=command,
        bg=bg, fg=fg, font=font,
        relief="flat", cursor="hand2",
        padx=10, pady=4,
        activebackground=ACCENT_DIM if accent else BORDER,
        activeforeground=TEXT_PRIMARY,
        bd=0
    )
    return btn

def section_label(parent, text):
    return tk.Label(
        parent, text=text.upper(), font=("Consolas", 8, "bold"),
        bg=BG_PANEL, fg=TEXT_MUTED, anchor="w"
    )

def nav_button(parent, text, command=None):
    """Left-panel navigation button."""
    btn = tk.Button(
        parent, text=f"  {text}", command=command,
        bg=BG_PANEL, fg=TEXT_SECONDARY, font=FONT_BODY,
        relief="flat", anchor="w", cursor="hand2",
        padx=8, pady=6,
        activebackground=BG_HOVER,
        activeforeground=ACCENT,
        bd=0
    )
    btn.bind("<Enter>", lambda e: btn.config(bg=BG_HOVER, fg=ACCENT))
    btn.bind("<Leave>", lambda e: btn.config(bg=BG_PANEL, fg=TEXT_SECONDARY))
    return btn

def separator(parent):
    return tk.Frame(parent, bg=BORDER, height=1)

# ─── Login Screen ─────────────────────────────────────────────────────────────

class LoginScreen(tk.Frame):
    def __init__(self, master, on_login):
        super().__init__(master, bg=BG_DARK)
        self.on_login = on_login
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        # Header
        header = tk.Frame(self, bg=BG_DARK)
        header.pack(pady=(60, 10))

        tk.Label(header, text="⚔", font=("Georgia", 36), bg=BG_DARK, fg=ACCENT).pack()
        tk.Label(header, text="TRAVIAN MANAGER", font=("Georgia", 22, "bold"),
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack()
        tk.Label(header, text="Account Planning & Management Tool",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_SECONDARY).pack(pady=(4, 0))

        # Account list panel
        panel = tk.Frame(self, bg=BG_PANEL, bd=0, relief="flat")
        panel.pack(padx=80, pady=20, fill="both", expand=True)

        # Inner padding
        inner = tk.Frame(panel, bg=BG_PANEL)
        inner.pack(fill="both", expand=True, padx=20, pady=20)

        tk.Label(inner, text="SELECT ACCOUNT", font=("Consolas", 9, "bold"),
                 bg=BG_PANEL, fg=TEXT_MUTED).pack(anchor="w")
        tk.Label(inner, text="Double-click an account to open it",
                 font=FONT_SMALL, bg=BG_PANEL, fg=TEXT_MUTED).pack(anchor="w", pady=(0, 10))

        # Listbox with scrollbar
        list_frame = tk.Frame(inner, bg=BORDER, bd=1, relief="flat")
        list_frame.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(list_frame, bg=BG_MID, troughcolor=BG_DARK,
                                 relief="flat", bd=0, width=10)
        scrollbar.pack(side="right", fill="y")

        self.account_list = tk.Listbox(
            list_frame,
            bg=BG_MID, fg=TEXT_PRIMARY, font=FONT_BODY,
            selectbackground=ACCENT_DIM, selectforeground=TEXT_PRIMARY,
            relief="flat", bd=0, highlightthickness=0,
            yscrollcommand=scrollbar.set,
            activestyle="none"
        )
        self.account_list.pack(fill="both", expand=True, padx=1, pady=1)
        scrollbar.config(command=self.account_list.yview)
        self.account_list.bind("<Double-Button-1>", self._on_double_click)

        self._refresh_accounts()

        # Buttons row
        btn_row = tk.Frame(inner, bg=BG_PANEL)
        btn_row.pack(fill="x", pady=(12, 0))

        styled_button(btn_row, "+ Add Account", command=self._add_account, accent=True).pack(side="left")
        styled_button(btn_row, "Open Selected", command=self._open_selected).pack(side="left", padx=8)
        styled_button(btn_row, "Remove", command=self._remove_account, small=True).pack(side="right")

        # Footer
        tk.Label(self, text="Data stored locally in /travian_data/",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(pady=(0, 20))

    def _refresh_accounts(self):
        self.account_list.delete(0, tk.END)
        for server, account in load_accounts():
            self.account_list.insert(tk.END, f"  [{server}]  {account}")

    def _add_account(self):
        server = simpledialog.askstring("Server", "Enter server name (e.g. EU2):",
                                        parent=self)
        if not server:
            return
        account = simpledialog.askstring("Account", "Enter account/player name:",
                                         parent=self)
        if not account:
            return
        save_account(server.strip(), account.strip())
        self._refresh_accounts()

    def _remove_account(self):
        sel = self.account_list.curselection()
        if not sel:
            return
        idx = sel[0]
        accounts = load_accounts()
        accounts.pop(idx)
        # Rewrite file
        with open(ACCOUNTS_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["server", "account"])
            for s, a in accounts:
                writer.writerow([s, a])
        self._refresh_accounts()

    def _on_double_click(self, event):
        self._open_selected()

    def _open_selected(self):
        sel = self.account_list.curselection()
        if not sel:
            messagebox.showinfo("No Selection", "Please select an account first.")
            return
        idx = sel[0]
        server, account = load_accounts()[idx]
        self.on_login(server, account)


# ─── Main Application Window ──────────────────────────────────────────────────

class MainApp(tk.Frame):
    def __init__(self, master, server, account, on_logout):
        super().__init__(master, bg=BG_DARK)
        self.server = server
        self.account = account
        self.on_logout = on_logout
        self.selected_village = None
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        self._build_topbar()

        # Main layout: left panel | center content | right panel
        body = tk.Frame(self, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=0, pady=0)

        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self._build_left_panel(body)
        self._build_center(body)
        self._build_right_panel(body)

    # ── Top bar ──

    def _build_topbar(self):
        bar = tk.Frame(self, bg=BG_MID, height=44)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        tk.Label(bar, text="⚔  TRAVIAN MANAGER", font=("Georgia", 12, "bold"),
                 bg=BG_MID, fg=ACCENT).pack(side="left", padx=16)

        # Account info
        info = tk.Frame(bar, bg=BG_MID)
        info.pack(side="left", padx=20)
        tk.Label(info, text=f"Server: ", font=FONT_SMALL, bg=BG_MID, fg=TEXT_MUTED).pack(side="left")
        tk.Label(info, text=self.server, font=("Consolas", 10, "bold"), bg=BG_MID, fg=ACCENT).pack(side="left")
        tk.Label(info, text="  Account: ", font=FONT_SMALL, bg=BG_MID, fg=TEXT_MUTED).pack(side="left")
        tk.Label(info, text=self.account, font=("Consolas", 10, "bold"), bg=BG_MID, fg=TEXT_PRIMARY).pack(side="left")

        styled_button(bar, "⇦ Logout", command=self.on_logout, small=True).pack(side="right", padx=12, pady=8)

        separator(self).pack(fill="x")

    # ── Left panel: account-wide navigation ──

    def _build_left_panel(self, parent):
        self.left_panel = tk.Frame(parent, bg=BG_PANEL, width=200)
        self.left_panel.grid(row=0, column=0, sticky="nsew")
        self.left_panel.pack_propagate(False)

        self._build_account_nav()

    def _build_account_nav(self):
        """Account-wide navigation items."""
        for widget in self.left_panel.winfo_children():
            widget.destroy()

        pad = tk.Frame(self.left_panel, bg=BG_PANEL)
        pad.pack(fill="both", expand=True, padx=0, pady=0)

        section_label(pad, "Account Overview").pack(fill="x", padx=12, pady=(14, 4))

        account_items = [
            ("📊  Production Info",    self._show_production_info),
            ("⚔   Deployed Troops",    self._show_deployed_troops),
            ("🗺   Troop Locations",    self._show_troop_locations),
            ("⚡  Net Production",      self._show_net_production),
        ]
        for label, cmd in account_items:
            nav_button(pad, label, command=cmd).pack(fill="x")

        separator(pad).pack(fill="x", padx=8, pady=10)

        # Village sub-menu (appears when a village is selected)
        self.village_nav_frame = tk.Frame(pad, bg=BG_PANEL)
        self.village_nav_frame.pack(fill="x")
        # Initially empty — populated when a village is selected

    def _show_village_submenu(self, village_name):
        """Show village-specific sub-navigation in left panel."""
        for widget in self.village_nav_frame.winfo_children():
            widget.destroy()

        # Village header
        vhdr = tk.Frame(self.village_nav_frame, bg=VILLAGE_SEL)
        vhdr.pack(fill="x")
        tk.Label(vhdr, text=f"🏘 {village_name}", font=("Georgia", 10, "bold"),
                 bg=VILLAGE_SEL, fg=ACCENT, anchor="w").pack(
                     fill="x", padx=12, pady=6)

        section_label(self.village_nav_frame, "Village Menu").pack(fill="x", padx=12, pady=(6, 4))

        village_items = [
            ("⚙   Setup",              lambda: self._show_village_setup(village_name)),
            ("🔄  Trade Routes",        lambda: self._show_trade_routes(village_name)),
            ("📋  Set Trade Route",     lambda: self._show_set_trade_route(village_name)),
            ("🪖  Troops Sent Out",     lambda: self._show_troops_sent_out(village_name)),
        ]
        for label, cmd in village_items:
            nav_button(self.village_nav_frame, label, command=cmd).pack(fill="x")

    # ── Center content area ──

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
            tk.Label(hdr, text=subtitle, font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(anchor="w", pady=(2, 0))
        separator(self.center).pack(fill="x", padx=24, pady=12)

    def _placeholder_card(self, title, description):
        """Render a placeholder content card."""
        card = tk.Frame(self.center, bg=BG_PANEL, bd=0)
        card.pack(fill="both", expand=True, padx=24, pady=(0, 24))

        inner = tk.Frame(card, bg=BG_PANEL)
        inner.pack(expand=True)

        tk.Label(inner, text="[ Placeholder ]", font=("Consolas", 11, "bold"),
                 bg=BG_PANEL, fg=TEXT_MUTED).pack(pady=(60, 8))
        tk.Label(inner, text=title, font=FONT_HEADING, bg=BG_PANEL, fg=TEXT_SECONDARY).pack()
        tk.Label(inner, text=description, font=FONT_SMALL, bg=BG_PANEL,
                 fg=TEXT_MUTED, wraplength=400, justify="center").pack(pady=(6, 0))

    # ── Welcome screen ──

    def _show_welcome(self):
        self._clear_center()
        self._content_header("Welcome back,", f"{self.account}  ·  {self.server}")
        self._placeholder_card(
            "Select a view from the left panel",
            "Use the account-wide options to view production stats, troop info, and more.\n"
            "Click a village in the right panel to manage it."
        )

    # ── Account-wide views ──

    def _show_production_info(self):
        self._clear_center()
        self._content_header("Production Info", "Resource output across all villages")
        self._placeholder_card("Production Info", "Will show lumber, clay, iron, crop production per hour for each village.")

    def _show_deployed_troops(self):
        self._clear_center()
        self._content_header("Deployed Troops", "All troops currently away from home")
        self._placeholder_card("Deployed Troops", "List of troops on the move: raids, attacks, support, and settlers.")

    def _show_troop_locations(self):
        self._clear_center()
        self._content_header("Troop Locations", "Where all your troops currently are")
        self._placeholder_card("Troop Locations", "Map-style overview of troop positions across the game world.")

    def _show_net_production(self):
        self._clear_center()
        self._content_header("Net Production", "Production minus consumption")
        self._placeholder_card("Net Production", "Total net resource production after subtracting troop upkeep.")

    # ── Village-specific views ──

    def _show_village_setup(self, village):
        self._clear_center()
        self._content_header(f"{village}  —  Setup", "Village configuration and buildings")
        self._placeholder_card("Village Setup", "Configure building levels, rally point settings, and village notes.")

    def _show_trade_routes(self, village):
        self._clear_center()
        self._content_header(f"{village}  —  Trade Routes", "Existing automated trade routes")
        self._placeholder_card("Trade Routes", "List of active resource trade routes to and from this village.")

    def _show_set_trade_route(self, village):
        self._clear_center()
        self._content_header(f"{village}  —  Set Trade Route", "Configure a new trade route")
        self._placeholder_card("Set Trade Route", "Form to create or modify a trade route: destination, resource type, amount, interval.")

    def _show_troops_sent_out(self, village):
        self._clear_center()
        self._content_header(f"{village}  —  Troops Sent Out", "Troops dispatched from this village")
        self._placeholder_card("Troops Sent Out", "Track outgoing raids, attacks, and reinforcements from this village.")

    # ── Right panel: village list ──

    def _build_right_panel(self, parent):
        right = tk.Frame(parent, bg=BG_PANEL, width=200)
        right.grid(row=0, column=2, sticky="nsew")
        right.pack_propagate(False)

        hdr = tk.Frame(right, bg=BG_MID)
        hdr.pack(fill="x")
        tk.Label(hdr, text="VILLAGES", font=("Consolas", 9, "bold"),
                 bg=BG_MID, fg=TEXT_MUTED).pack(side="left", padx=12, pady=8)

        styled_button(hdr, "+", command=self._add_village_dialog, small=True, accent=True).pack(
            side="right", padx=8, pady=6)

        separator(right).pack(fill="x")

        # Scrollable village list
        vlist_frame = tk.Frame(right, bg=BG_PANEL)
        vlist_frame.pack(fill="both", expand=True)

        scroll = tk.Scrollbar(vlist_frame, bg=BG_MID, troughcolor=BG_DARK,
                              relief="flat", bd=0, width=8)
        scroll.pack(side="right", fill="y")

        self.village_listbox = tk.Listbox(
            vlist_frame,
            bg=BG_PANEL, fg=TEXT_PRIMARY, font=FONT_BODY,
            selectbackground=VILLAGE_SEL, selectforeground=ACCENT,
            relief="flat", bd=0, highlightthickness=0,
            yscrollcommand=scroll.set, activestyle="none",
            cursor="hand2"
        )
        self.village_listbox.pack(fill="both", expand=True)
        scroll.config(command=self.village_listbox.yview)

        self.village_listbox.bind("<<ListboxSelect>>", self._on_village_select)

        self._refresh_village_list()

        separator(right).pack(fill="x")
        styled_button(right, "Refresh List", command=self._refresh_village_list, small=True).pack(
            fill="x", padx=8, pady=6)

    def _refresh_village_list(self):
        self.villages = load_villages(self.server, self.account)
        self.village_listbox.delete(0, tk.END)
        if not self.villages:
            self.village_listbox.insert(tk.END, "  (no villages yet)")
        for v in self.villages:
            self.village_listbox.insert(tk.END, f"  🏘 {v['village_name']}")

    def _on_village_select(self, event):
        sel = self.village_listbox.curselection()
        if not sel or not self.villages:
            return
        idx = sel[0]
        if idx >= len(self.villages):
            return
        village = self.villages[idx]
        name = village["village_name"]
        self.selected_village = name
        self._show_village_submenu(name)
        self._show_village_setup(name)

    def _add_village_dialog(self):
        name = simpledialog.askstring("Add Village", "Village name:", parent=self)
        if not name:
            return
        coords = simpledialog.askstring("Coordinates", "Coordinates (e.g. -45|32), optional:", parent=self) or ""
        add_village(self.server, self.account, name.strip(), coords.strip())
        self._refresh_village_list()


# ─── App Controller ───────────────────────────────────────────────────────────

class TravianApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Travian Manager")
        self.root.geometry("1100x700")
        self.root.minsize(900, 600)
        self.root.configure(bg=BG_DARK)

        # Try to set a nice icon/title bar color (platform-dependent)
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
        self.current_frame = MainApp(
            self.root, server, account,
            on_logout=self._show_login
        )

    def run(self):
        self.root.mainloop()


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = TravianApp()
    app.run()