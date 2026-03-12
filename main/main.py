"""
Travian Account Manager
Data stored in CSV files under travian_data/.

Folder structure:
  travian_data/
    accounts.csv
    EU2_Deonnar/
      villages.csv
      EU2_Deonnar_VillageName_layout.csv      ← planned building layout
      EU2_Deonnar_VillageName_buildings.csv   ← current building state
      snapshots/
"""

import tkinter as tk
from tkinter import messagebox, ttk
import csv, shutil
from datetime import datetime
from pathlib import Path

# ─── Constants ────────────────────────────────────────────────────────────────

DATA_DIR      = Path("travian_data")
ACCOUNTS_FILE = DATA_DIR / "accounts.csv"

TRIBES   = ["Romans", "Teutons", "Gauls", "Egyptians", "Huns", "Spartans", "Natars"]
STATUSES = ["active", "archived"]
SPEEDS   = ["1x", "2x", "3x", "5x", "10x"]

TRIBE_ICON = {
    "Romans": "🦅", "Teutons": "🪓", "Gauls": "🌿",
    "Egyptians": "𓂀", "Huns": "🏹", "Spartans": "🛡", "Natars": "💀",
}

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

# Building progress color thresholds
COL_RED         = "#c0392b"   # 0–25%
COL_ORANGE      = "#e67e22"   # 25–50%
COL_YELLOW      = "#f1c40f"   # 50–75%
COL_LIGHT_GREEN = "#58d68d"   # 75–99%
COL_FULL_GREEN  = "#27ae60"   # 100%
COL_MAXED       = "#1abc9c"   # above planned (extra credit)

FONT_TITLE   = ("Georgia", 18, "bold")
FONT_HEADING = ("Georgia", 11, "bold")
FONT_BODY    = ("Consolas", 10)
FONT_SMALL   = ("Consolas", 9)
FONT_TINY    = ("Consolas", 8)

# ─── Village building slots ────────────────────────────────────────────────────
# Travian villages have 18+2+1 outer (resource) slots and 18+2 inner slots.
# We track 22 inner village building slots (standard village center).
# Special slots with fixed building type: Wall (slot 40), Rally Point (slot 39).

# All buildable inner buildings (tribe=all + tribe-specific)
ALL_BUILDINGS = [
    "Main Building", "Warehouse", "Granary", "Marketplace", "Embassy",
    "Barracks", "Stable", "Workshop", "Academy", "Smithy", "Armoury",
    "Cranny", "Townhall", "Residence", "Palace", "Tournament Square",
    "Trade Office", "Hero's Mansion", "Sawmill", "Brickyard",
    "Iron Foundry", "Flour Mill", "Bakery", "Great Warehouse", "Great Granary",
    "Great Barracks", "Great Stable", "Stonemason", "Treasury",
    # Tribe-specific
    "Horse Drinking Trough",   # Romans
    "Brewery", "Trapper",       # Teutons
    "Menhir",                   # Gauls
]
ALL_BUILDINGS_SORTED = sorted(ALL_BUILDINGS)

TRIBE_BUILDINGS = {
    "Romans":    ALL_BUILDINGS_SORTED + [],
    "Teutons":   ALL_BUILDINGS_SORTED + [],
    "Gauls":     ALL_BUILDINGS_SORTED + [],
    "Egyptians": ALL_BUILDINGS_SORTED + [],
    "Huns":      ALL_BUILDINGS_SORTED + [],
    "Spartans":  ALL_BUILDINGS_SORTED + [],
    "Natars":    ALL_BUILDINGS_SORTED + [],
}

WALL_BY_TRIBE = {
    "Romans": "City Wall", "Teutons": "Earth Wall", "Gauls": "Palisade",
    "Egyptians": "Stone Wall", "Huns": "Makeshift Wall",
    "Spartans": "Spartan Wall", "Natars": "Natar Wall",
}

MAX_BUILDING_LEVEL = 20   # most buildings
SIEGE_MAX          = 10   # Workshop, Great Barracks, etc.

# 22 inner village building slots
# slot_id: (label, locked_building or None)
VILLAGE_SLOTS = {
    1:  ("Slot 1",  None),   2:  ("Slot 2",  None),   3:  ("Slot 3",  None),
    4:  ("Slot 4",  None),   5:  ("Slot 5",  None),   6:  ("Slot 6",  None),
    7:  ("Slot 7",  None),   8:  ("Slot 8",  None),   9:  ("Slot 9",  None),
    10: ("Slot 10", None),   11: ("Slot 11", None),   12: ("Slot 12", None),
    13: ("Slot 13", None),   14: ("Slot 14", None),   15: ("Slot 15", None),
    16: ("Slot 16", None),   17: ("Slot 17", None),   18: ("Slot 18", None),
    19: ("Rally Point", "Rally Point"),  # locked
    20: ("Wall",    "__WALL__"),          # tribe-specific wall, locked
}

BUILDING_LEVELS = [str(i) for i in range(0, 21)]   # 0 = empty / not built

BUILDING_LEVELS = [str(i) for i in range(0, 21)]   # 0 = empty / not built

# ─── Unique buildings (loaded from CSV) ───────────────────────────────────────
# Buildings marked is_unique=Yes may appear only once in a village layout.
# Non-unique (Cranny, Warehouse, Granary, Trapper, resource fields) can repeat.

NON_UNIQUE_BUILDINGS = {"Cranny", "Warehouse", "Granary", "Trapper"}

def load_unique_buildings() -> set:
    """Return set of building names that are unique per village (from CSV)."""
    csv_path = DATA_DIR / "general" / "1x" / "buildings.csv"
    unique = set()
    if not csv_path.exists():
        return set(ALL_BUILDINGS) - NON_UNIQUE_BUILDINGS
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("is_unique", "Yes").strip() == "Yes":
                unique.add(row["name"])
    return unique


# ─── Path helpers ─────────────────────────────────────────────────────────────

def account_key(server, account):    return f"{server.upper()}_{account}"
def account_dir(server, account):    return DATA_DIR / account_key(server, account)
def snapshots_dir(server, account):  return account_dir(server, account) / "snapshots"
def villages_file(server, account):  return account_dir(server, account) / "villages.csv"

def _vkey(server, account, village_name):
    safe = village_name.replace(" ", "_").replace("/", "-")
    return account_dir(server, account) / f"{account_key(server,account)}_{safe}"

def layout_file(server, account, village_name):
    return Path(str(_vkey(server, account, village_name)) + "_layout.csv")

def buildings_file(server, account, village_name):
    return Path(str(_vkey(server, account, village_name)) + "_buildings.csv")


# ─── Data layer ───────────────────────────────────────────────────────────────

ACCOUNT_FIELDS = ["server", "account", "tribe", "status", "speed"]
VILLAGE_FIELDS = ["village_name", "coord_x", "coord_y",
                  "res_wood", "res_clay", "res_iron", "res_crop"]
LAYOUT_FIELDS  = ["slot_id", "building", "level"]
BUILDING_FIELDS_CSV = ["slot_id", "building", "level"]

def ensure_data_dir():
    DATA_DIR.mkdir(exist_ok=True)
    if not ACCOUNTS_FILE.exists():
        with open(ACCOUNTS_FILE, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=ACCOUNT_FIELDS).writeheader()

def load_accounts():
    ensure_data_dir()
    with open(ACCOUNTS_FILE, newline="") as f:
        return list(csv.DictReader(f))

def _rewrite_accounts(accounts):
    with open(ACCOUNTS_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ACCOUNT_FIELDS)
        w.writeheader(); w.writerows(accounts)

def save_new_account(server, account, tribe, status="active", speed="1x"):
    ensure_data_dir()
    accounts = load_accounts()
    key = account_key(server, account)
    if any(account_key(a["server"], a["account"]) == key for a in accounts):
        return
    accounts.append({"server": server.upper(), "account": account,
                     "tribe": tribe, "status": status, "speed": speed})
    _rewrite_accounts(accounts)
    adir = account_dir(server, account)
    adir.mkdir(parents=True, exist_ok=True)
    snapshots_dir(server, account).mkdir(exist_ok=True)
    vfile = villages_file(server, account)
    if not vfile.exists():
        with open(vfile, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=VILLAGE_FIELDS).writeheader()

def update_account_status(server, account, new_status):
    accounts = load_accounts()
    key = account_key(server, account)
    for a in accounts:
        if account_key(a["server"], a["account"]) == key:
            a["status"] = new_status
    _rewrite_accounts(accounts)

def get_account(server, account):
    for a in load_accounts():
        if account_key(a["server"], a["account"]) == account_key(server, account):
            return a
    return None

def load_villages(server, account):
    vfile = villages_file(server, account)
    if not vfile.exists(): return []
    with open(vfile, newline="") as f:
        return list(csv.DictReader(f))

def _rewrite_villages(server, account, villages):
    with open(villages_file(server, account), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=VILLAGE_FIELDS)
        w.writeheader(); w.writerows(villages)

def add_village(server, account, name, coord_x="", coord_y="",
                res_wood=4, res_clay=4, res_iron=4, res_crop=6):
    villages = load_villages(server, account)
    villages.append({"village_name": name, "coord_x": coord_x, "coord_y": coord_y,
                     "res_wood": res_wood, "res_clay": res_clay,
                     "res_iron": res_iron, "res_crop": res_crop})
    _rewrite_villages(server, account, villages)

def update_village(server, account, name, updates: dict):
    villages = load_villages(server, account)
    for v in villages:
        if v["village_name"] == name:
            v.update(updates)
    _rewrite_villages(server, account, villages)

def take_snapshot(server, account):
    src = villages_file(server, account)
    if not src.exists(): return None
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dst = snapshots_dir(server, account) / f"{stamp}_villages.csv"
    shutil.copy2(src, dst)
    return dst

def load_layout(server, account, village_name):
    fpath = layout_file(server, account, village_name)
    if not fpath.exists(): return {}
    result = {}
    with open(fpath, newline="") as f:
        for row in csv.DictReader(f):
            result[int(row["slot_id"])] = {
                "building": row["building"], "level": int(row["level"])}
    return result

def save_layout(server, account, village_name, layout: dict):
    fpath = layout_file(server, account, village_name)
    with open(fpath, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LAYOUT_FIELDS)
        w.writeheader()
        for slot_id, data in sorted(layout.items()):
            w.writerow({"slot_id": slot_id, "building": data["building"], "level": data["level"]})

def load_current_buildings(server, account, village_name):
    fpath = buildings_file(server, account, village_name)
    if not fpath.exists(): return {}
    result = {}
    with open(fpath, newline="") as f:
        for row in csv.DictReader(f):
            result[int(row["slot_id"])] = {
                "building": row["building"], "level": int(row["level"])}
    return result

def save_current_buildings(server, account, village_name, buildings: dict):
    fpath = buildings_file(server, account, village_name)
    with open(fpath, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=BUILDING_FIELDS_CSV)
        w.writeheader()
        for slot_id, data in sorted(buildings.items()):
            w.writerow({"slot_id": slot_id, "building": data["building"], "level": data["level"]})

# Population lookup: building_name -> list of 20 incremental pop values per level
_BUILDING_STATS_CACHE = None   # (name, level) -> {"pop": int, "cp": int}

def _get_building_stats() -> dict:
    """Load population_gained and culture_points per (building, level) from buildings.csv."""
    global _BUILDING_STATS_CACHE
    if _BUILDING_STATS_CACHE is not None:
        return _BUILDING_STATS_CACHE
    csv_path = DATA_DIR / "general" / "1x" / "buildings.csv"
    table = {}
    if csv_path.exists():
        with open(csv_path, newline="") as f:
            for row in csv.DictReader(f):
                try:
                    table[(row["name"], int(row["level"]))] = {
                        "pop": int(row["population_gained"]),
                        "cp":  int(row["culture_points"]),
                    }
                except (ValueError, KeyError):
                    pass
    _BUILDING_STATS_CACHE = table
    return table

def _sum_village_stat(server, account, village_name, key: str) -> int:
    """Generic helper: sum a stat across all built levels in the village."""
    buildings = load_current_buildings(server, account, village_name)
    stats = _get_building_stats()
    total = 0
    for slot_data in buildings.values():
        name = slot_data.get("building", "")
        cur_level = int(slot_data.get("level", 0))
        for lv in range(1, cur_level + 1):
            total += stats.get((name, lv), {}).get(key, 0)
    return total

def calculate_population(server, account, village_name) -> int:
    """Sum incremental population gained by all currently built building levels."""
    return _sum_village_stat(server, account, village_name, "pop")

def calculate_culture_points(server, account, village_name) -> int:
    """Sum incremental culture points generated by all currently built building levels."""
    return _sum_village_stat(server, account, village_name, "cp")


# ─── Progress color helper ────────────────────────────────────────────────────

def progress_color(current_level, planned_level):
    if planned_level == 0:    return TEXT_MUTED
    if current_level >= planned_level: return COL_FULL_GREEN
    ratio = current_level / planned_level
    if ratio < 0.25:  return COL_RED
    if ratio < 0.50:  return COL_ORANGE
    if ratio < 0.75:  return COL_YELLOW
    return COL_LIGHT_GREEN


# ─── Progress bar canvas widget ──────────────────────────────────────────────

def make_progress_bar(parent, current_level, planned_level, row_bg,
                      bar_w=80, bar_h=12):
    """
    Returns a Canvas widget showing a filled progress bar.
    Width=bar_w, height=bar_h. Updates via .update_bar(cur, plan).
    """
    col = progress_color(current_level, planned_level)
    c = tk.Canvas(parent, width=bar_w, height=bar_h,
                  bg=row_bg, highlightthickness=0, bd=0)

    # Background track
    c.create_rectangle(0, 0, bar_w, bar_h, fill=BG_MID, outline=BORDER, width=1)

    if planned_level > 0:
        ratio = min(current_level / planned_level, 1.0)
        fill_w = max(int(ratio * (bar_w - 2)), 0)
        if fill_w > 0:
            c.create_rectangle(1, 1, 1 + fill_w, bar_h - 1, fill=col, outline="")

    # Percentage text inside bar
    if planned_level > 0:
        pct = int(min(current_level / planned_level, 1.0) * 100)
        text_col = BG_DARK if pct > 50 else TEXT_MUTED
        c.create_text(bar_w // 2, bar_h // 2, text=f"{pct}%",
                      font=("Consolas", 7, "bold"), fill=text_col)

    def update_bar(cur, plan):
        c.delete("all")
        nc = progress_color(cur, plan)
        c.create_rectangle(0, 0, bar_w, bar_h, fill=BG_MID, outline=BORDER, width=1)
        if plan > 0:
            r = min(cur / plan, 1.0)
            fw = max(int(r * (bar_w - 2)), 0)
            if fw > 0:
                c.create_rectangle(1, 1, 1 + fw, bar_h - 1, fill=nc, outline="")
            p = int(r * 100)
            tc = BG_DARK if p > 50 else TEXT_MUTED
            c.create_text(bar_w // 2, bar_h // 2, text=f"{p}%",
                          font=("Consolas", 7, "bold"), fill=tc)

    c.update_bar = update_bar
    return c


# ─── Styled widget helpers ─────────────────────────────────────────────────────

def styled_button(parent, text, command=None, accent=False, small=False, danger=False):
    if danger:   bg, fg = "#3a1010", "#e05555"
    elif accent: bg, fg = ACCENT, BG_DARK
    else:        bg, fg = BG_HOVER, TEXT_PRIMARY
    font = FONT_SMALL if small else FONT_BODY
    btn = tk.Button(parent, text=text, command=command, bg=bg, fg=fg, font=font,
                    relief="flat", cursor="hand2", padx=10, pady=4,
                    activebackground=ACCENT_DIM if accent else BORDER,
                    activeforeground=TEXT_PRIMARY, bd=0)
    return btn

def section_label(parent, text, bg=BG_PANEL):
    return tk.Label(parent, text=text.upper(), font=("Consolas", 8, "bold"),
                    bg=bg, fg=TEXT_MUTED, anchor="w")

def nav_button(parent, text, command=None):
    btn = tk.Button(parent, text=f"  {text}", command=command,
                    bg=BG_PANEL, fg=TEXT_SECONDARY, font=FONT_BODY,
                    relief="flat", anchor="w", cursor="hand2", padx=8, pady=6,
                    activebackground=BG_HOVER, activeforeground=ACCENT, bd=0)
    btn.bind("<Enter>", lambda e: btn.config(bg=BG_HOVER, fg=ACCENT))
    btn.bind("<Leave>", lambda e: btn.config(bg=BG_PANEL, fg=TEXT_SECONDARY))
    return btn

def make_separator(parent, bg=None):
    return tk.Frame(parent, bg=bg or BORDER, height=1)

def styled_entry(parent, var, width=None):
    kw = dict(textvariable=var, bg=BG_MID, fg=TEXT_PRIMARY, insertbackground=ACCENT,
              font=FONT_BODY, relief="flat", bd=0, highlightthickness=1,
              highlightbackground=BORDER, highlightcolor=ACCENT)
    if width: kw["width"] = width
    return tk.Entry(parent, **kw)

def styled_combo(parent, var, values, width=22, state="readonly"):
    style = ttk.Style()
    style.theme_use("default")
    style.configure("Dark.TCombobox",
                    fieldbackground=BG_MID, background=BG_MID,
                    foreground=TEXT_PRIMARY, selectbackground=BG_HOVER,
                    selectforeground=ACCENT, arrowcolor=ACCENT,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                    insertcolor=ACCENT)
    style.map("Dark.TCombobox",
              fieldbackground=[("readonly", BG_MID)],
              selectbackground=[("readonly", BG_MID)])
    cb = ttk.Combobox(parent, textvariable=var, values=values,
                      width=width, state=state, style="Dark.TCombobox",
                      font=FONT_SMALL)
    return cb

def scrollable_frame(parent, bg=BG_DARK):
    outer  = tk.Frame(parent, bg=bg)
    canvas = tk.Canvas(outer, bg=bg, highlightthickness=0, bd=0)
    sb     = tk.Scrollbar(outer, orient="vertical", command=canvas.yview,
                          bg=BG_MID, troughcolor=BG_DARK, relief="flat", bd=0, width=8)
    inner  = tk.Frame(canvas, bg=bg)
    inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    def _on_configure(e):
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfig(inner_id, width=canvas.winfo_width())

    inner.bind("<Configure>", _on_configure)
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(inner_id, width=e.width))

    def _on_mousewheel(e):
        canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    canvas.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    return outer, inner

def fade_label(widget, after_ms=3500):
    """Schedule a label to fade to invisible after after_ms milliseconds."""
    def _fade():
        widget.config(fg=BG_DARK)   # hide by matching bg
    widget.after(after_ms, _fade)


# ─── Column layout helpers ────────────────────────────────────────────────────
# Pixel widths for each column — shared between header and data rows so they
# always align exactly.

# Character-unit column widths (scale correctly with font/dpi)
# (header_text, label_width_chars, combo_width_chars)
PLANNER_COLS = [
    ("Slot",            5,   None),
    ("Fixed",           9,   None),
    ("Target Building", 26,  26),
    ("Target Level",    6,   6),
]

BUILDINGS_COLS = [
    ("Slot",             5,   None),
    ("Planned Building", 22,  None),
    ("Plan Lvl",         6,   None),
    ("Current Building", 22,  22),
    ("Cur Lvl",          6,   6),
    ("Progress",         None, None),   # canvas — no fixed char width
]


# ─── Add Account Dialog ────────────────────────────────────────────────────────

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

        for label, attr in [("Server name (e.g. EU2)", "server_var"),
                             ("Account / player name",  "account_var")]:
            var = tk.StringVar()
            setattr(self, attr, var)
            tk.Label(pad, text=label, font=FONT_SMALL, bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor="w")
            styled_entry(pad, var).pack(fill="x", pady=(2, 10), ipady=4)

        tk.Label(pad, text="Tribe", font=FONT_SMALL, bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor="w")
        self.tribe_var = tk.StringVar(value=TRIBES[0])
        tribe_frame = tk.Frame(pad, bg=BG_DARK); tribe_frame.pack(fill="x", pady=(2, 10))
        col_a = tk.Frame(tribe_frame, bg=BG_DARK); col_b = tk.Frame(tribe_frame, bg=BG_DARK)
        col_a.pack(side="left", padx=(0, 16)); col_b.pack(side="left")
        for i, t in enumerate(TRIBES):
            col = col_a if i < 4 else col_b
            tk.Radiobutton(col, text=f"{TRIBE_ICON.get(t,'')} {t}", variable=self.tribe_var, value=t,
                           bg=BG_DARK, fg=TEXT_SECONDARY, selectcolor=BG_MID,
                           activebackground=BG_DARK, activeforeground=ACCENT,
                           font=FONT_SMALL, cursor="hand2").pack(anchor="w")

        tk.Label(pad, text="Status", font=FONT_SMALL, bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor="w", pady=(6,0))
        self.status_var = tk.StringVar(value="active")
        sf = tk.Frame(pad, bg=BG_DARK); sf.pack(fill="x", pady=(2, 10))
        for s in STATUSES:
            tk.Radiobutton(sf, text=s.capitalize(), variable=self.status_var, value=s,
                           bg=BG_DARK, fg=TEXT_SECONDARY, selectcolor=BG_MID,
                           activebackground=BG_DARK, activeforeground=ACCENT,
                           font=FONT_SMALL, cursor="hand2").pack(side="left", padx=(0,16))

        tk.Label(pad, text="Server Speed", font=FONT_SMALL, bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor="w", pady=(6,0))
        self.speed_var = tk.StringVar(value="1x")
        spf = tk.Frame(pad, bg=BG_DARK); spf.pack(fill="x", pady=(2, 16))
        for sp in SPEEDS:
            tk.Radiobutton(spf, text=sp, variable=self.speed_var, value=sp,
                           bg=BG_DARK, fg=TEXT_SECONDARY, selectcolor=BG_MID,
                           activebackground=BG_DARK, activeforeground=ACCENT,
                           font=FONT_SMALL, cursor="hand2").pack(side="left", padx=(0,12))

        br = tk.Frame(pad, bg=BG_DARK); br.pack(fill="x")
        styled_button(br, "Create Account", command=self._submit, accent=True).pack(side="left")
        styled_button(br, "Cancel", command=self.destroy, small=True).pack(side="left", padx=8)

    def _submit(self):
        server = self.server_var.get().strip().upper()
        account = self.account_var.get().strip()
        if not server or not account:
            messagebox.showwarning("Missing info", "Please fill in both server and account name.", parent=self)
            return
        self.result = (server, account, self.tribe_var.get(), self.status_var.get(), self.speed_var.get())
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

        tk.Label(pad, text="Village name", font=FONT_SMALL,
                 bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor="w")
        styled_entry(pad, self.name_var).pack(fill="x", pady=(2, 10), ipady=4)

        coord_row = tk.Frame(pad, bg=BG_DARK)
        coord_row.pack(fill="x", pady=(0, 14))
        for label, var, side in [("Coord X", self.x_var, "left"),
                                  ("Coord Y", self.y_var, "right")]:
            col = tk.Frame(coord_row, bg=BG_DARK)
            col.pack(side=side, fill="x", expand=True, padx=(0 if side=="left" else 8, 0))
            tk.Label(col, text=label, font=FONT_SMALL, bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor="w")
            styled_entry(col, var, width=10).pack(fill="x", ipady=4)

        make_separator(pad).pack(fill="x", pady=(0, 12))
        tk.Label(pad, text="RESOURCE FIELDS", font=("Consolas", 8, "bold"),
                 bg=BG_DARK, fg=TEXT_MUTED).pack(anchor="w", pady=(0, 6))
        tk.Label(pad, text="Number of each resource field type in this village",
                 font=FONT_TINY, bg=BG_DARK, fg=TEXT_MUTED).pack(anchor="w", pady=(0, 8))

        self.res_vars = {}
        res_row = tk.Frame(pad, bg=BG_DARK)
        res_row.pack(fill="x", pady=(0, 14))

        for label, key, default in [("🌲 Wood", "res_wood", 4), ("🧱 Clay", "res_clay", 4),
                                     ("⚙ Iron",  "res_iron", 4), ("🌾 Crop", "res_crop", 6)]:
            col = tk.Frame(res_row, bg=BG_DARK)
            col.pack(side="left", fill="x", expand=True, padx=3)
            tk.Label(col, text=label, font=FONT_TINY, bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor="w")
            var = tk.StringVar(value=str(default))
            self.res_vars[key] = var
            styled_combo(col, var, [str(i) for i in range(1, 13)], width=4).pack(anchor="w", pady=(2, 0))

        br = tk.Frame(pad, bg=BG_DARK); br.pack(fill="x")
        styled_button(br, "Add Village", command=self._submit, accent=True).pack(side="left")
        styled_button(br, "Cancel", command=self.destroy, small=True).pack(side="left", padx=8)

    def _submit(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing info", "Village name is required.", parent=self)
            return
        self.result = {
            "village_name": name,
            "coord_x": self.x_var.get().strip(),
            "coord_y": self.y_var.get().strip(),
            "res_wood": self.res_vars["res_wood"].get(),
            "res_clay": self.res_vars["res_clay"].get(),
            "res_iron": self.res_vars["res_iron"].get(),
            "res_crop": self.res_vars["res_crop"].get(),
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
            yscrollcommand=scrollbar.set, activestyle="none")
        self.account_list.pack(fill="both", expand=True, padx=1, pady=1)
        scrollbar.config(command=self.account_list.yview)
        self.account_list.bind("<Double-Button-1>", self._on_double_click)
        self._refresh_accounts()

        btn_row = tk.Frame(inner, bg=BG_PANEL)
        btn_row.pack(fill="x", pady=(12, 0))
        styled_button(btn_row, "+ Add Account", command=self._add_account, accent=True).pack(side="left")
        styled_button(btn_row, "Open",          command=self._open_selected).pack(side="left", padx=8)
        styled_button(btn_row, "Archive / Restore", command=self._toggle_status, small=True).pack(side="left")
        styled_button(btn_row, "Remove", command=self._remove_account, small=True, danger=True).pack(side="right")

        tk.Label(self, text=f"Data folder: {DATA_DIR.resolve()}",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(pady=(0, 16))

    def _refresh_accounts(self):
        self.account_list.delete(0, tk.END)
        self._accounts = load_accounts()
        for a in self._accounts:
            icon  = "🟢" if a.get("status") == "active" else "🔵"
            ticon = TRIBE_ICON.get(a.get("tribe", ""), "")
            speed = a.get("speed", "1x")
            self.account_list.insert(tk.END,
                f"  {icon}  [{a['server']}]  {a['account']}   {ticon} {a.get('tribe','')}  ⚡{speed}")

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
            messagebox.showinfo("No Selection", "Select an account first."); return
        new = "archived" if a.get("status") == "active" else "active"
        update_account_status(a["server"], a["account"], new)
        self._refresh_accounts()

    def _remove_account(self):
        a = self._selected()
        if not a: return
        if not messagebox.askyesno("Remove Account",
                f"Remove [{a['server']}] {a['account']} from the list?\nData folder will NOT be deleted.",
                parent=self): return
        accounts = [x for x in load_accounts()
                    if account_key(x["server"], x["account"]) != account_key(a["server"], a["account"])]
        _rewrite_accounts(accounts)
        self._refresh_accounts()

    def _on_double_click(self, _e): self._open_selected()

    def _open_selected(self):
        a = self._selected()
        if not a:
            messagebox.showinfo("No Selection", "Please select an account first."); return
        self.on_login(a["server"], a["account"])


# ─── Village Layout Planner ────────────────────────────────────────────────────

class VillageLayoutPlanner(tk.Frame):
    """
    20 building slots, each with a building dropdown and level dropdown.
    Unique buildings can only be selected once across all free slots.
    Fixed slots (Rally Point, Wall) are locked.
    Save button shows a fading confirmation label instead of a popup.
    """
    def __init__(self, master, server, account, village_name, tribe, is_archived=False):
        super().__init__(master, bg=BG_DARK)
        self.server       = server
        self.account      = account
        self.village_name = village_name
        self.tribe        = tribe
        self.is_archived  = is_archived

        self._building_vars = {}
        self._level_vars    = {}
        self._combos        = {}   # slot_id -> Combobox widget (for rebuilding values)
        self._UNIQUE        = load_unique_buildings()

        self._load_and_build()

    # ── Unique enforcement ────────────────────────────────────────────────────

    def _used_unique(self, exclude_slot=None):
        """Return set of unique building names currently chosen in OTHER slots."""
        used = set()
        for sid, var in self._building_vars.items():
            if sid == exclude_slot:
                continue
            val = var.get()
            if val and val != "— Empty —" and val in self._UNIQUE:
                used.add(val)
        return used

    def _available_buildings(self, slot_id):
        used = self._used_unique(exclude_slot=slot_id)
        result = ["— Empty —"]
        for b in sorted(ALL_BUILDINGS):
            if b in self._UNIQUE and b in used:
                continue
            result.append(b)
        return result

    def _on_building_change(self, slot_id, *_):
        """Rebuild available options in all other free combos."""
        for sid, cb in self._combos.items():
            if sid == slot_id:
                continue
            cur_val = self._building_vars[sid].get()
            new_vals = self._available_buildings(sid)
            cb["values"] = new_vals
            if cur_val not in new_vals:
                self._building_vars[sid].set("— Empty —")

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _load_and_build(self):
        layout = load_layout(self.server, self.account, self.village_name)
        wall_building = WALL_BY_TRIBE.get(self.tribe, "Wall")

        # Header row with save button + fading status label
        hdr = tk.Frame(self, bg=BG_DARK)
        hdr.pack(fill="x", padx=24, pady=(24, 0))
        tk.Label(hdr, text=f"{self.village_name}  —  Village Layout Planner",
                 font=FONT_TITLE, bg=BG_DARK, fg=TEXT_PRIMARY).pack(side="left", anchor="w")

        if not self.is_archived:
            self._save_status = tk.Label(hdr, text="", font=FONT_SMALL,
                                         bg=BG_DARK, fg=COL_FULL_GREEN)
            self._save_status.pack(side="right", padx=(0, 12))
            styled_button(hdr, "💾  Save Layout", command=self._save,
                          accent=True).pack(side="right")

        make_separator(self).pack(fill="x", padx=24, pady=10)
        tk.Label(self,
                 text="Set the target building and level for each slot.  "
                      "🔒 Fixed slots cannot be changed.  "
                      "Unique buildings can only be placed once.",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(anchor="w", padx=24, pady=(0, 10))

        outer, inner = scrollable_frame(self)
        outer.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        # ── Column header ──
        hdr_row = tk.Frame(inner, bg=BG_PANEL)
        hdr_row.pack(fill="x", pady=(0, 2))
        for text, lw, _ in PLANNER_COLS:
            tk.Label(hdr_row, text=text, font=("Consolas", 8, "bold"),
                     bg=BG_PANEL, fg=TEXT_MUTED, width=lw, anchor="w").pack(side="left", padx=4)
        make_separator(inner, bg=BORDER).pack(fill="x", pady=(0, 4))

        # ── First pass: initialise StringVars so _available_buildings works ──
        for slot_id in range(1, 21):
            _, locked = VILLAGE_SLOTS[slot_id]
            if locked:
                ln = wall_building if locked == "__WALL__" else locked
                self._building_vars[slot_id] = tk.StringVar(value=ln)
            else:
                saved_b = layout.get(slot_id, {}).get("building", "— Empty —") or "— Empty —"
                self._building_vars[slot_id] = tk.StringVar(value=saved_b)
            saved_l = str(layout.get(slot_id, {}).get("level", 0))
            self._level_vars[slot_id] = tk.StringVar(value=saved_l)

        # ── Second pass: build rows ──
        for slot_id in range(1, 21):
            _, locked = VILLAGE_SLOTS[slot_id]
            is_locked = locked is not None
            locked_name = (wall_building if locked == "__WALL__" else locked) if locked else None
            row_bg = BG_MID if slot_id % 2 == 0 else BG_DARK
            row = tk.Frame(inner, bg=row_bg)
            row.pack(fill="x", pady=1)

            # Slot number
            tk.Label(row, text=f"  {slot_id:02d}", font=FONT_BODY,
                     width=PLANNER_COLS[0][1], bg=row_bg,
                     fg=ACCENT if is_locked else TEXT_SECONDARY,
                     anchor="w").pack(side="left", padx=4)

            # Fixed tag
            tag_text = "🔒 FIXED" if is_locked else ""
            tk.Label(row, text=tag_text, font=FONT_TINY,
                     width=PLANNER_COLS[1][1], bg=row_bg,
                     fg=TEXT_MUTED, anchor="w").pack(side="left", padx=4)

            # Building
            if is_locked:
                tk.Label(row, text=locked_name, font=FONT_BODY,
                         width=PLANNER_COLS[2][1], bg=row_bg,
                         fg=TEXT_SECONDARY, anchor="w").pack(side="left", padx=4)
            else:
                avail = self._available_buildings(slot_id)
                state = "disabled" if self.is_archived else "readonly"
                cb = styled_combo(row, self._building_vars[slot_id], avail,
                                  width=PLANNER_COLS[2][2], state=state)
                cb.pack(side="left", padx=4, pady=3)
                self._combos[slot_id] = cb
                self._building_vars[slot_id].trace_add(
                    "write", lambda *_, sid=slot_id: self._on_building_change(sid))

            # Level
            state = "disabled" if self.is_archived else "readonly"
            lv_cb = styled_combo(row, self._level_vars[slot_id],
                                 BUILDING_LEVELS, width=PLANNER_COLS[3][2], state=state)
            lv_cb.pack(side="left", padx=4, pady=3)

    def _save(self):
        layout = {}
        wall_building = WALL_BY_TRIBE.get(self.tribe, "Wall")
        for slot_id in range(1, 21):
            _, locked = VILLAGE_SLOTS[slot_id]
            if locked == "__WALL__": building = wall_building
            elif locked:             building = locked
            else:
                building = self._building_vars[slot_id].get()
                if building == "— Empty —": building = ""
            try:    level = int(self._level_vars[slot_id].get())
            except: level = 0
            if building or level:
                layout[slot_id] = {"building": building, "level": level}
        save_layout(self.server, self.account, self.village_name, layout)
        # Fading confirmation instead of popup
        self._save_status.config(text="✓ Layout saved", fg=COL_FULL_GREEN)
        fade_label(self._save_status, after_ms=3500)


# ─── Village Buildings Tracker ────────────────────────────────────────────────

class VillageBuildingsView(tk.Frame):
    """
    Side-by-side table: Planned layout (read-only) vs Current state (editable).
    Progress bar as the last column, colour-coded against planned level.
    Unique buildings enforced in the current-building dropdowns.
    Save uses fading status text instead of a popup.
    """
    def __init__(self, master, server, account, village_name, tribe, is_archived=False, on_save=None):
        super().__init__(master, bg=BG_DARK)
        self.server       = server
        self.account      = account
        self.village_name = village_name
        self.tribe        = tribe
        self.is_archived  = is_archived
        self._on_save     = on_save   # optional callback after saving

        self._cur_building_vars = {}
        self._cur_level_vars    = {}
        self._progress_bars     = {}
        self._cur_combos        = {}
        self._planned_levels    = {}
        self._UNIQUE            = load_unique_buildings()

        self._load_and_build()

    # ── Unique enforcement ────────────────────────────────────────────────────

    def _used_unique_cur(self, exclude_slot=None):
        used = set()
        for sid, var in self._cur_building_vars.items():
            if sid == exclude_slot: continue
            val = var.get()
            if val and val != "— Empty —" and val in self._UNIQUE:
                used.add(val)
        return used

    def _available_cur(self, slot_id, locked_name=None):
        if locked_name:
            return [locked_name]
        used = self._used_unique_cur(exclude_slot=slot_id)
        result = ["— Empty —"]
        for b in sorted(ALL_BUILDINGS):
            if b in self._UNIQUE and b in used:
                continue
            result.append(b)
        return result

    def _on_cur_building_change(self, slot_id, *_):
        for sid, cb in self._cur_combos.items():
            if sid == slot_id: continue
            cur_val = self._cur_building_vars[sid].get()
            new_vals = self._available_cur(sid)
            cb["values"] = new_vals
            if cur_val not in new_vals:
                self._cur_building_vars[sid].set("— Empty —")

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _load_and_build(self):
        self.layout  = load_layout(self.server, self.account, self.village_name)
        self.current = load_current_buildings(self.server, self.account, self.village_name)
        wall_building = WALL_BY_TRIBE.get(self.tribe, "Wall")

        # Header
        hdr = tk.Frame(self, bg=BG_DARK)
        hdr.pack(fill="x", padx=24, pady=(24, 0))
        tk.Label(hdr, text=f"{self.village_name}  —  Buildings",
                 font=FONT_TITLE, bg=BG_DARK, fg=TEXT_PRIMARY).pack(side="left", anchor="w")
        if not self.is_archived:
            # Status label pre-reserved with fixed width so buttons never shift
            self._save_status = tk.Label(hdr, text="", font=FONT_SMALL,
                                         bg=BG_DARK, fg=COL_FULL_GREEN,
                                         width=22, anchor="w")
            self._save_status.pack(side="left", padx=(16, 0))
            styled_button(hdr, "🔀  Sort to Plan", command=self._sort_to_plan,
                          small=True).pack(side="left", padx=(0, 6))
            styled_button(hdr, "💾  Save Current State", command=self._save,
                          accent=True).pack(side="left")

        make_separator(self).pack(fill="x", padx=24, pady=10)

        # Legend
        leg = tk.Frame(self, bg=BG_DARK)
        leg.pack(anchor="w", padx=24, pady=(0, 8))
        tk.Label(leg, text="Progress vs. planned:  ", font=FONT_TINY,
                 bg=BG_DARK, fg=TEXT_MUTED).pack(side="left")
        for col, label in [(COL_RED, "0–25%"), (COL_ORANGE, "25–50%"),
                           (COL_YELLOW, "50–75%"), (COL_LIGHT_GREEN, "75–99%"),
                           (COL_FULL_GREEN, "100% ✓")]:
            tk.Label(leg, text=f"  ■ {label}", font=FONT_TINY, bg=BG_DARK, fg=col).pack(side="left")

        make_separator(self).pack(fill="x", padx=24, pady=(0, 8))

        outer, inner = scrollable_frame(self)
        outer.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        # Column header
        hdr_row = tk.Frame(inner, bg=BG_PANEL)
        hdr_row.pack(fill="x", pady=(0, 2))
        for text, lw, _ in BUILDINGS_COLS:
            tk.Label(hdr_row, text=text, font=("Consolas", 8, "bold"),
                     bg=BG_PANEL, fg=TEXT_MUTED,
                     width=lw if lw else 10, anchor="w").pack(side="left", padx=4)
        make_separator(inner, bg=BORDER).pack(fill="x", pady=(0, 4))

        # First pass: initialise cur StringVars
        for slot_id in range(1, 21):
            _, locked = VILLAGE_SLOTS[slot_id]
            locked_name = (wall_building if locked == "__WALL__" else locked) if locked else None
            cur = self.current.get(slot_id, {})
            pl  = self.layout.get(slot_id, {})
            default_b = locked_name or cur.get("building", "") or ""
            self._cur_building_vars[slot_id] = tk.StringVar(
                value=default_b if default_b else "— Empty —")
            self._cur_level_vars[slot_id] = tk.StringVar(
                value=str(cur.get("level", 0)))
            self._planned_levels[slot_id] = int(pl.get("level", 0))

        # Second pass: build rows
        for slot_id in range(1, 21):
            _, locked = VILLAGE_SLOTS[slot_id]
            locked_name = (wall_building if locked == "__WALL__" else locked) if locked else None
            p_data     = self.layout.get(slot_id, {})
            p_building = p_data.get("building", "")
            p_level    = int(p_data.get("level", 0))
            c_level    = int(self.current.get(slot_id, {}).get("level", 0))

            row_bg = BG_MID if slot_id % 2 == 0 else BG_DARK
            row = tk.Frame(inner, bg=row_bg)
            row.pack(fill="x", pady=1)

            # Slot
            tk.Label(row, text=f"  {slot_id:02d}", font=FONT_BODY,
                     width=BUILDINGS_COLS[0][1], bg=row_bg,
                     fg=ACCENT if locked_name else TEXT_MUTED,
                     anchor="w").pack(side="left", padx=4)

            # Planned building
            p_disp = p_building or (locked_name or "—")
            tk.Label(row, text=p_disp, font=FONT_BODY,
                     width=BUILDINGS_COLS[1][1], bg=row_bg,
                     fg=TEXT_SECONDARY, anchor="w").pack(side="left", padx=4)

            # Planned level
            p_lv_text = str(p_level) if (p_building or locked_name) else "—"
            tk.Label(row, text=p_lv_text, font=FONT_BODY,
                     width=BUILDINGS_COLS[2][1], bg=row_bg,
                     fg=TEXT_SECONDARY, anchor="w").pack(side="left", padx=4)

            # Current building
            if locked_name:
                tk.Label(row, text=locked_name, font=FONT_BODY,
                         width=BUILDINGS_COLS[3][1], bg=row_bg,
                         fg=TEXT_PRIMARY, anchor="w").pack(side="left", padx=4)
            else:
                state = "disabled" if self.is_archived else "readonly"
                cb = styled_combo(row, self._cur_building_vars[slot_id],
                                  self._available_cur(slot_id),
                                  width=BUILDINGS_COLS[3][2], state=state)
                cb.pack(side="left", padx=4, pady=3)
                self._cur_combos[slot_id] = cb
                self._cur_building_vars[slot_id].trace_add(
                    "write", lambda *_, sid=slot_id: self._on_cur_building_change(sid))

            # Current level
            state = "disabled" if self.is_archived else "readonly"
            lv_cb = styled_combo(row, self._cur_level_vars[slot_id],
                                 BUILDING_LEVELS, width=BUILDINGS_COLS[4][2], state=state)
            lv_cb.pack(side="left", padx=4, pady=3)

            # Progress bar
            bar = make_progress_bar(row, c_level, p_level, row_bg, bar_w=90, bar_h=14)
            bar.pack(side="left", padx=8, pady=5)
            self._progress_bars[slot_id] = (bar, p_level)

            # Update bar when level changes
            def _make_bar_tracer(sid, pl):
                def _trace(*_):
                    b, _ = self._progress_bars[sid]
                    try:    cl = int(self._cur_level_vars[sid].get())
                    except: cl = 0
                    b.update_bar(cl, pl)
                return _trace
            self._cur_level_vars[slot_id].trace_add(
                "write", _make_bar_tracer(slot_id, p_level))

    def _sort_to_plan(self):
        """
        Reshuffle current building assignments in free slots so they align with
        the planned layout order.

        Logic:
        - Collect all (building, level) pairs from the current free slots.
        - Walk the planned layout in slot order; if a plan slot has a building,
          try to match it from the pool. Assign matched pair to that slot.
        - Any unmatched current entries fill remaining free slots in original order.
        - Locked slots (Rally Point, Wall) are never touched.
        """
        wall_building = WALL_BY_TRIBE.get(self.tribe, "Wall")

        # Gather current free-slot contents as a list of (building, level) pairs
        pool = []
        free_slots = []
        for slot_id in range(1, 21):
            _, locked = VILLAGE_SLOTS[slot_id]
            if locked:
                continue
            free_slots.append(slot_id)
            raw = self._cur_building_vars[slot_id].get()
            b = "" if raw == "— Empty —" else raw
            try:    lv = int(self._cur_level_vars[slot_id].get())
            except: lv = 0
            if b:
                pool.append([b, lv])

        # Build ordered assignment: match pool entries to plan slots in order
        assignment = []   # list of (building, level) to fill free_slots in order
        used = [False] * len(pool)

        for slot_id in free_slots:
            planned = self.layout.get(slot_id, {})
            p_b = planned.get("building", "")
            if not p_b:
                assignment.append(("", 0))
                continue
            # Find first unused pool entry with matching building name
            matched = False
            for i, (b, lv) in enumerate(pool):
                if not used[i] and b == p_b:
                    assignment.append((b, lv))
                    used[i] = True
                    matched = True
                    break
            if not matched:
                assignment.append(("", 0))

        # Append any unmatched pool entries (buildings not in plan)
        leftover = [(b, lv) for i, (b, lv) in enumerate(pool) if not used[i]]
        slot_idx = 0
        leftover_idx = 0
        for i, (b, lv) in enumerate(assignment):
            if b == "" and leftover_idx < len(leftover):
                assignment[i] = leftover[leftover_idx]
                leftover_idx += 1

        # Apply to UI vars
        for slot_id, (b, lv) in zip(free_slots, assignment):
            self._cur_building_vars[slot_id].set(b if b else "— Empty —")
            self._cur_level_vars[slot_id].set(str(lv))

        self._save_status.config(text="↕ Sorted to plan", fg=ACCENT)
        fade_label(self._save_status, after_ms=3000)

    def _save(self):
        buildings = {}
        wall_building = WALL_BY_TRIBE.get(self.tribe, "Wall")
        for slot_id in range(1, 21):
            _, locked = VILLAGE_SLOTS[slot_id]
            if locked == "__WALL__": building = wall_building
            elif locked:             building = locked
            else:
                raw = self._cur_building_vars[slot_id].get()
                building = "" if raw == "— Empty —" else raw
            try:    level = int(self._cur_level_vars[slot_id].get())
            except: level = 0
            if building or level:
                buildings[slot_id] = {"building": building, "level": level}
        save_current_buildings(self.server, self.account, self.village_name, buildings)
        self._save_status.config(text="✓ Current state saved", fg=COL_FULL_GREEN)
        fade_label(self._save_status, after_ms=3500)
        if self._on_save:
            self._on_save()

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
        self.speed  = self.account_data.get("speed", "1x")
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
            ("  ⚡", self.speed, ACCENT),
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
            tk.Label(banner, text="🔵  ARCHIVED  —  This server has ended. Data is read-only.",
                     font=FONT_SMALL, bg="#1e1010", fg="#c07070").pack(pady=5)
        make_separator(self).pack(fill="x")

    # ── Left panel ───────────────────────────────────────────────────────────

    def _build_left_panel(self, parent):
        self.left_panel = tk.Frame(parent, bg=BG_PANEL, width=220)
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

        snap_btn = styled_button(pad, "📸 Take Snapshot", command=self._take_snapshot,
                                 small=True, accent=not self.is_archived)
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
        vn = village_name
        for label, cmd in [
            ("🗺   Layout Planner",  lambda: self._show_village_layout(vn)),
            ("🏗   Buildings",       lambda: self._show_village_buildings(vn)),
            ("🔄  Trade Routes",     lambda: self._show_trade_routes(vn)),
            ("📋  Set Trade Route",  lambda: self._show_set_trade_route(vn)),
            ("🪖  Troops Sent Out",  lambda: self._show_troops_sent_out(vn)),
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
        tk.Label(inner, text=title, font=FONT_HEADING, bg=BG_PANEL, fg=TEXT_SECONDARY).pack()
        tk.Label(inner, text=description, font=FONT_SMALL, bg=BG_PANEL,
                 fg=TEXT_MUTED, wraplength=440, justify="center").pack(pady=(6, 0))

    def _show_welcome(self):
        self._clear_center()
        ticon = TRIBE_ICON.get(self.tribe, "")
        self._content_header(
            f"Welcome back, {self.account}",
            f"{self.server}  ·  {ticon} {self.tribe}  ·  {self.status.upper()}  ·  ⚡{self.speed}"
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
            f"Lumber, clay, iron, crop per hour per village. Tribe bonuses for {self.tribe} included.")

    def _show_deployed_troops(self):
        self._clear_center()
        self._content_header("Deployed Troops", "Troops currently away from home")
        self._placeholder_card("Deployed Troops", f"All {self.tribe} troops on the move.")

    def _show_troop_locations(self):
        self._clear_center()
        self._content_header("Troop Locations", "Where all your troops are")
        self._placeholder_card("Troop Locations", "Troop positions shown with X/Y coordinates.")

    def _show_net_production(self):
        self._clear_center()
        self._content_header("Net Production", "Production minus troop upkeep")
        self._placeholder_card("Net Production", "Total net resources per hour after upkeep.")

    # ── Village views ─────────────────────────────────────────────────────────

    def _show_village_layout(self, village):
        self._clear_center()
        planner = VillageLayoutPlanner(
            self.center, self.server, self.account, village,
            self.tribe, self.is_archived)
        planner.pack(fill="both", expand=True)

    def _show_village_buildings(self, village):
        self._clear_center()
        view = VillageBuildingsView(
            self.center, self.server, self.account, village,
            self.tribe, self.is_archived,
            on_save=self._refresh_village_list)
        view.pack(fill="both", expand=True)

    def _show_trade_routes(self, village):
        self._clear_center()
        self._content_header(f"{village}  —  Trade Routes", "Active trade routes")
        self._placeholder_card("Trade Routes", "List of active resource routes to/from this village.")

    def _show_set_trade_route(self, village):
        self._clear_center()
        self._content_header(f"{village}  —  Set Trade Route", "Configure a trade route")
        self._placeholder_card("Set Trade Route",
            "Destination village by X/Y coordinates, resource type, amount, and interval.")

    def _show_troops_sent_out(self, village):
        self._clear_center()
        self._content_header(f"{village}  —  Troops Sent Out", "Outgoing troop movements")
        self._placeholder_card("Troops Sent Out",
            "Outgoing raids, attacks, reinforcements, and settlers.")

    # ── Snapshot ──────────────────────────────────────────────────────────────

    def _take_snapshot(self):
        dst = take_snapshot(self.server, self.account)
        if dst:
            messagebox.showinfo("Snapshot Saved", f"Saved to:\n{dst}", parent=self)
        else:
            messagebox.showwarning("Snapshot Failed", "No village data found.", parent=self)

    # ── Right panel: village list ─────────────────────────────────────────────

    def _build_right_panel(self, parent):
        right = tk.Frame(parent, bg=BG_PANEL, width=220)
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
            yscrollcommand=scroll.set, activestyle="none", cursor="hand2")
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
            x = v.get("coord_x", "?"); y = v.get("coord_y", "?")
            w = v.get("res_wood", "?"); c = v.get("res_clay", "?")
            i = v.get("res_iron", "?"); cr = v.get("res_crop", "?")
            pop = calculate_population(self.server, self.account, v["village_name"])
            cp  = calculate_culture_points(self.server, self.account, v["village_name"])
            pop_str = str(pop) if pop > 0 else "—"
            cp_str  = str(cp)  if cp  > 0 else "—"
            self.village_listbox.insert(tk.END, f"  🏘 {v['village_name']}")
            self.village_listbox.insert(tk.END, f"      ({x} | {y})  👤{pop_str}  ★{cp_str}")
            self.village_listbox.insert(tk.END, f"      🌲{w} 🧱{c} ⚙{i} 🌾{cr}")

    def _on_village_select(self, _event):
        sel = self.village_listbox.curselection()
        if not sel or not self.villages: return
        village_idx = sel[0] // 3   # 3 lines per village
        if village_idx >= len(self.villages): return
        village = self.villages[village_idx]
        name = village["village_name"]
        self.selected_village = name
        self._show_village_submenu(name)
        self._show_village_layout(name)

    def _add_village_dialog(self):
        dlg = AddVillageDialog(self)
        if dlg.result:
            d = dlg.result
            add_village(self.server, self.account,
                        d["village_name"], d["coord_x"], d["coord_y"],
                        d.get("res_wood", 4), d.get("res_clay", 4),
                        d.get("res_iron", 4), d.get("res_crop", 6))
            self._refresh_village_list()


# ─── App Controller ───────────────────────────────────────────────────────────

class TravianApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Travian Manager")
        self.root.geometry("1260x780")
        self.root.minsize(1000, 650)
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
        self.current_frame = MainApp(self.root, server, account, on_logout=self._show_login)

    def run(self):
        self.root.mainloop()


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = TravianApp()
    app.run()