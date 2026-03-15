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

# Universal buildings available to every tribe
_UNIVERSAL_BUILDINGS = [
    "Main Building", "Warehouse", "Granary", "Marketplace", "Embassy",
    "Barracks", "Stable", "Workshop", "Academy", "Smithy", "Armoury",
    "Cranny", "Townhall", "Residence", "Palace", "Tournament Square",
    "Trade Office", "Hero's Mansion", "Sawmill", "Brickyard",
    "Iron Foundry", "Flour Mill", "Bakery", "Great Warehouse", "Great Granary",
    "Great Barracks", "Great Stable", "Stonemason", "Treasury",
]

# Tribe-exclusive buildings (not available to any other tribe)
_TRIBE_EXCLUSIVE = {
    "Romans":    ["Horse Drinking Trough"],
    "Teutons":   ["Brewery", "Trapper"],
    "Gauls":     ["Menhir"],
    "Egyptians": [],
    "Huns":      [],
    "Spartans":  [],
    "Natars":    [],
}

def buildings_for_tribe(tribe: str) -> list:
    """Return sorted list of inner buildings available to the given tribe."""
    return sorted(_UNIVERSAL_BUILDINGS + _TRIBE_EXCLUSIVE.get(tribe, []))

# Keep ALL_BUILDINGS for legacy references (e.g. uniqueness checks)
ALL_BUILDINGS = _UNIVERSAL_BUILDINGS + [b for bs in _TRIBE_EXCLUSIVE.values() for b in bs]
ALL_BUILDINGS_SORTED = sorted(set(ALL_BUILDINGS))

WALL_BY_TRIBE = {
    "Romans": "City Wall", "Teutons": "Earth Wall", "Gauls": "Palisade",
    "Egyptians": "Stone Wall", "Huns": "Makeshift Wall",
    "Spartans": "Spartan Wall", "Natars": "Natar Wall",
}

MAX_BUILDING_LEVEL = 20   # default for most buildings

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

BUILDING_LEVELS = [str(i) for i in range(0, 21)]   # 0–20, default full range

# Max-level cache: building name -> highest level row present in buildings.csv
_MAX_LEVEL_CACHE: dict = {}

def building_max_level(name: str) -> int:
    """Return the maximum buildable level for a building (read from CSV, cached)."""
    global _MAX_LEVEL_CACHE
    if not _MAX_LEVEL_CACHE:
        csv_path = DATA_DIR / "general" / "1x" / "buildings.csv"
        if csv_path.exists():
            with open(csv_path, newline="") as f:
                for row in csv.DictReader(f):
                    try:
                        n, lv = row["name"], int(row["level"])
                        _MAX_LEVEL_CACHE[n] = max(_MAX_LEVEL_CACHE.get(n, 0), lv)
                    except (ValueError, KeyError):
                        pass
    return _MAX_LEVEL_CACHE.get(name, MAX_BUILDING_LEVEL)

def level_options(name: str) -> list:
    """Return the '0'..'N' string list for a building's level combobox."""
    return [str(i) for i in range(0, building_max_level(name) + 1)]

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

def troops_file(server, account, village_name):
    return Path(str(_vkey(server, account, village_name)) + "_troops.csv")

# Troop table row keys (stored as column headers in the CSV)
TROOP_ROWS = ["trained", "native_in", "native_out", "foreign_in"]

def load_troop_data(server, account, village_name, troop_names: list) -> dict:
    fpath = troops_file(server, account, village_name)
    data = {row: {t: 0 for t in troop_names} for row in TROOP_ROWS}
    if fpath.exists():
        for enc in ("utf-8", "utf-8-sig", "cp1250", "cp1252", "latin-1"):
            try:
                with open(fpath, newline="", encoding=enc) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        rk = row.get("row", "")
                        if rk in data:
                            for t in troop_names:
                                try:
                                    data[rk][t] = int(row.get(t, 0) or 0)
                                except ValueError:
                                    data[rk][t] = 0
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
    return data

def save_troop_data(server, account, village_name, troop_names: list, data: dict):
    fpath = troops_file(server, account, village_name)
    with open(fpath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["row"] + troop_names)
        w.writeheader()
        for rk in TROOP_ROWS:
            row_dict = {"row": rk}
            row_dict.update({t: data[rk].get(t, 0) for t in troop_names})
            w.writerow(row_dict)

def get_tribe_troops(tribe: str) -> list:
    """Return ordered list of troop names for the given tribe from troops.csv."""
    csv_path = DATA_DIR / "general" / "1x" / "troops.csv"
    troops = []
    if csv_path.exists():
        with open(csv_path, newline="") as f:
            for row in csv.DictReader(f):
                if row["tribe"].strip().lower() == tribe.strip().lower():
                    troops.append(row["name"].strip())
    return troops

# ─── Resource layout per-village ─────────────────────────────────────────────
# 18 resource field slots per village.  Each slot has a type and level.
RESOURCE_TYPES  = ["Woodcutter", "Clay Pit", "Iron Mine", "Cropland"]

# Travian production per hour at each field level (levels 0–10, index = level)
# Source: standard 1x speed values
FIELD_PRODUCTION = [0, 2, 5, 9, 15, 25, 40, 65, 105, 170, 280]
RESOURCE_FIELDS = ["slot", "type", "level"]

def resource_file(server, account, village_name) -> Path:
    return Path(str(_vkey(server, account, village_name)) + "_resources.csv")

def load_resource_layout(server, account, village_name) -> list:
    """Return list of 18 dicts {slot, type, level}. Defaults to empty Cropland lvl0."""
    fpath = resource_file(server, account, village_name)
    default = [{"slot": str(i), "type": "Cropland", "level": "0"} for i in range(1, 19)]
    if not fpath.exists():
        return default
    result = []
    with open(fpath, newline="") as f:
        for row in csv.DictReader(f):
            result.append({"slot": row["slot"], "type": row.get("type","Cropland"),
                           "level": row.get("level","0")})
    # Fill missing slots
    present = {r["slot"] for r in result}
    for i in range(1, 19):
        if str(i) not in present:
            result.append({"slot": str(i), "type": "Cropland", "level": "0"})
    result.sort(key=lambda r: int(r["slot"]))
    return result[:18]

def save_resource_layout(server, account, village_name, slots: list):
    fpath = resource_file(server, account, village_name)
    with open(fpath, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RESOURCE_FIELDS)
        w.writeheader()
        for slot in slots:
            w.writerow(slot)
    # Update the village-level counts (res_wood/clay/iron/crop)
    counts = {"Woodcutter": 0, "Clay Pit": 0, "Iron Mine": 0, "Cropland": 0}
    for s in slots:
        t = s.get("type", "Cropland")
        if t in counts:
            counts[t] += 1
    update_village(server, account, village_name, {
        "res_wood":  counts["Woodcutter"],
        "res_clay":  counts["Clay Pit"],
        "res_iron":  counts["Iron Mine"],
        "res_crop":  counts["Cropland"],
    })

def calculate_village_production(server, account, village_name,
                                  gold_bonus: bool = False) -> dict:
    """
    Return {wood, clay, iron, crop} production/hr for a village.
    Applies 5% per level bonuses from Sawmill/Brickyard/Iron Foundry/Flour Mill/Bakery.
    Optionally applies the 25% gold bonus on all resources.
    """
    slots = load_resource_layout(server, account, village_name)
    base  = {"wood": 0, "clay": 0, "iron": 0, "crop": 0}
    type_to_key = {"Woodcutter": "wood", "Clay Pit": "clay",
                   "Iron Mine": "iron", "Cropland": "crop"}
    for s in slots:
        key = type_to_key.get(s.get("type", "Cropland"), "crop")
        try:
            lvl = int(s.get("level", 0))
        except ValueError:
            lvl = 0
        lvl = max(0, min(lvl, len(FIELD_PRODUCTION) - 1))
        base[key] += FIELD_PRODUCTION[lvl]

    # Production building bonuses: 5% per level
    # Sawmill→wood, Brickyard→clay, Iron Foundry→iron, Flour Mill+Bakery→crop
    PROD_BUILDINGS = {
        "Sawmill":      "wood",
        "Brickyard":    "clay",
        "Iron Foundry": "iron",
        "Flour Mill":   "crop",
        "Bakery":       "crop",
    }
    buildings = load_current_buildings(server, account, village_name)
    bonuses   = {"wood": 1.0, "clay": 1.0, "iron": 1.0, "crop": 1.0}
    for slot_data in buildings.values():
        bname = slot_data.get("building", "")
        blvl  = slot_data.get("level", 0)
        if bname in PROD_BUILDINGS:
            key = PROD_BUILDINGS[bname]
            bonuses[key] += 0.05 * blvl

    prod = {k: round(base[k] * bonuses[k]) for k in base}

    if gold_bonus:
        prod = {k: round(v * 1.25) for k, v in prod.items()}

    return prod

# ─── Troop overview paste parser ──────────────────────────────────────────────
import re as _re
import unicodedata as _ud

def _clean(s: str) -> str:
    """Strip unicode directional marks, non-breaking spaces, and strip."""
    return _re.sub(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069\xad\xa0]', '', s).strip()

def parse_troop_overview(raw_text: str, tribe: str) -> dict:
    """
    Parse a raw paste from the Travian troop overview page.

    Returns:
        {
          "troop_columns": [str, ...],          # column names found in the table
          "village_troops": {
              "Village Name": {"Legionnaire": 123, ...},
              ...
          },
          "village_coords": {
              "Village Name": (x, y),           # from sidebar groups section
          },
          "village_groups": {
              "Village Name": "Group Name",      # from sidebar
          },
        }
    Returns None if no valid table could be found.
    """
    lines = [_clean(ln) for ln in raw_text.splitlines()]
    lines = [ln for ln in lines if ln]  # drop blanks

    tribe_troops = get_tribe_troops(tribe)
    # Also accept "Hero" as a valid column (it appears in the paste but isn't in troops.csv)
    valid_cols = set(tribe_troops) | {"Hero"}

    # ── Find the table header row ──────────────────────────────────────────
    # It starts with "Village" and is followed by troop names
    header_idx = None
    troop_columns = []
    for i, ln in enumerate(lines):
        parts = [_clean(p) for p in ln.split("\t")]
        if not parts:
            continue
        if _clean(parts[0]).lower() == "village" and len(parts) > 1:
            cols = [_clean(p) for p in parts[1:]]
            # Accept if at least one column matches a known troop
            if any(c in valid_cols for c in cols):
                header_idx = i
                troop_columns = [c for c in cols if c in valid_cols]
                break

    if header_idx is None:
        return None

    # ── Read data rows until "Sum" or end ─────────────────────────────────
    village_troops = {}
    for ln in lines[header_idx + 1:]:
        parts = [_clean(p) for p in ln.split("\t")]
        if not parts:
            continue
        name_raw = _clean(parts[0])
        if name_raw.lower() == "sum":
            break
        # Village names are like "19. Vigántpetend" — strip the prefix number
        vname = _re.sub(r'^\d+\.\s*', '', name_raw).strip()
        if not vname:
            continue
        counts = {}
        for j, col in enumerate(troop_columns):
            raw_val = parts[j + 1] if j + 1 < len(parts) else "0"
            # Remove thousand separators (commas or non-breaking thin spaces)
            raw_val = _re.sub(r'[,\u202f\u00a0]', '', raw_val)
            try:
                counts[col] = int(raw_val)
            except ValueError:
                counts[col] = 0
        village_troops[vname] = counts

    # ── Parse sidebar: group names and coordinates ─────────────────────────
    # Pattern in the sidebar:
    #   Group Name
    #   19. Vigántpetend
    #   ‭(‭89‬|‭53‬)‬        ← coords line
    village_coords = {}
    village_groups = {}

    coord_pat = _re.compile(r'\(?\s*(-?\d+)\s*\|\s*(-?\d+)\s*\)?$')
    i = 0
    current_group = ""
    # Known non-group lines to skip
    skip_prefixes = {"village", "sum", "deonnar", "task overview", "homepage",
                     "© ", "info box", "link list", "privacy", "switch",
                     "hero", "server time", "alliance"}

    while i < len(lines):
        ln = lines[i]
        # Coord line right after a village name line
        coord_m = coord_pat.search(ln)
        if coord_m and i > 0:
            # The village name should be the previous line (may have a number prefix)
            prev = _clean(lines[i - 1])
            vname_candidate = _re.sub(r'^\d+\.\s*', '', prev).strip()
            if vname_candidate in village_troops:
                village_coords[vname_candidate] = (coord_m.group(1), coord_m.group(2))
                if current_group:
                    village_groups[vname_candidate] = current_group
            i += 1
            continue

        # Check if this looks like a group header (no number prefix, no coords,
        # not a village name, doesn't match skip patterns)
        lln = ln.lower()
        is_skip = any(lln.startswith(s) for s in skip_prefixes)
        has_number_prefix = bool(_re.match(r'^\d+\.', ln))
        is_known_village = _re.sub(r'^\d+\.\s*', '', ln).strip() in village_troops

        if (not is_skip and not has_number_prefix and not is_known_village
                and len(ln) > 2 and len(ln) < 60
                and not coord_pat.search(ln)):
            # Candidate group header — accept if next non-blank is a village line
            for j in range(i + 1, min(i + 4, len(lines))):
                nxt = lines[j]
                if _re.match(r'^\d+\.', nxt) or _re.sub(r'^\d+\.\s*','',nxt).strip() in village_troops:
                    current_group = ln
                    break
        i += 1

    return {
        "troop_columns":   troop_columns,
        "village_troops":  village_troops,
        "village_coords":  village_coords,
        "village_groups":  village_groups,
    }

def templates_dir(server, account) -> Path:
    return account_dir(server, account) / "Village_Templates"

def template_file(server, account, template_name) -> Path:
    safe = template_name.replace(" ", "_").replace("/", "-")
    return templates_dir(server, account) / f"{safe}.csv"

def list_templates(server, account) -> list:
    """Return sorted list of template names (stem of each CSV in the templates dir)."""
    tdir = templates_dir(server, account)
    if not tdir.exists():
        return []
    return sorted(p.stem.replace("_", " ") for p in tdir.glob("*.csv"))

def load_template(server, account, template_name) -> dict:
    """Load a template layout dict {slot_id(int): {building, level}}."""
    fpath = template_file(server, account, template_name)
    if not fpath.exists():
        return {}
    result = {}
    with open(fpath, newline="") as f:
        for row in csv.DictReader(f):
            result[int(row["slot_id"])] = {
                "building": row["building"], "level": int(row["level"])}
    return result

def save_template(server, account, template_name, layout: dict):
    """Save a layout dict as a named template CSV."""
    tdir = templates_dir(server, account)
    tdir.mkdir(parents=True, exist_ok=True)
    fpath = template_file(server, account, template_name)
    with open(fpath, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LAYOUT_FIELDS)
        w.writeheader()
        for slot_id, data in sorted(layout.items()):
            w.writerow({"slot_id": slot_id,
                        "building": data["building"],
                        "level": data["level"]})


# ─── Data layer ───────────────────────────────────────────────────────────────

ACCOUNT_FIELDS = ["server", "account", "tribe", "status", "speed"]
VILLAGE_FIELDS = ["village_name", "coord_x", "coord_y",
                  "res_wood", "res_clay", "res_iron", "res_crop",
                  "applied_template", "group"]
LAYOUT_FIELDS  = ["slot_id", "building", "level"]
BUILDING_FIELDS_CSV = ["slot_id", "building", "level"]

OPTIONS_FILE = DATA_DIR / "options.csv"

def load_option(key: str, default=None):
    """Read a single option value from travian_data/options.csv."""
    if not OPTIONS_FILE.exists():
        return default
    try:
        with open(OPTIONS_FILE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("key") == key:
                    return row.get("value", default)
    except Exception:
        pass
    return default

def save_option(key: str, value):
    """Persist a single option key/value in travian_data/options.csv."""
    DATA_DIR.mkdir(exist_ok=True)
    rows = {}
    if OPTIONS_FILE.exists():
        try:
            with open(OPTIONS_FILE, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    rows[row["key"]] = row["value"]
        except Exception:
            pass
    rows[key] = str(value)
    with open(OPTIONS_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["key", "value"])
        w.writeheader()
        for k, v in rows.items():
            w.writerow({"key": k, "value": v})

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
    for enc in ("utf-8", "utf-8-sig", "cp1250", "cp1252", "latin-1"):
        try:
            with open(vfile, newline="", encoding=enc) as f:
                return list(csv.DictReader(f))
        except (UnicodeDecodeError, UnicodeError):
            continue
    return []

def _rewrite_villages(server, account, villages):
    vfile = villages_file(server, account)
    vfile.parent.mkdir(parents=True, exist_ok=True)
    with open(vfile, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=VILLAGE_FIELDS, extrasaction="ignore")
        w.writeheader()
        for v in villages:
            row = {k: v.get(k, "") for k in VILLAGE_FIELDS}
            if not row["res_wood"]: row["res_wood"] = 4
            if not row["res_clay"]: row["res_clay"] = 4
            if not row["res_iron"]: row["res_iron"] = 4
            if not row["res_crop"]: row["res_crop"] = 6
            w.writerow(row)

def add_village(server, account, name, coord_x="", coord_y="",
                res_wood=4, res_clay=4, res_iron=4, res_crop=6, group=""):
    villages = load_villages(server, account)
    villages.append({"village_name": name, "coord_x": coord_x, "coord_y": coord_y,
                     "res_wood": res_wood, "res_clay": res_clay,
                     "res_iron": res_iron, "res_crop": res_crop,
                     "applied_template": "", "group": group})
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

def calculate_layout_progress(server, account, village_name) -> float:
    """
    Return overall build progress (0.0–1.0) of the village towards its planned layout.
    Compares sum of current levels vs sum of planned levels across all slots.
    Returns None if no layout is planned yet.
    """
    layout  = load_layout(server, account, village_name)
    current = load_current_buildings(server, account, village_name)
    planned_total = sum(d["level"] for d in layout.values())
    if planned_total == 0:
        return None
    current_total = 0
    for slot_id, plan in layout.items():
        cur = current.get(slot_id, {})
        cur_lv = int(cur.get("level", 0))
        current_total += min(cur_lv, plan["level"])
    return current_total / planned_total


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

    def _bind_wheel(e=None):
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        canvas.bind_all("<Button-4>",   lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>",   lambda e: canvas.yview_scroll(1, "units"))
    def _unbind_wheel(e=None):
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")

    canvas.bind("<Enter>", _bind_wheel)
    canvas.bind("<Leave>", _unbind_wheel)
    inner.bind("<Enter>",  _bind_wheel)
    inner.bind("<Leave>",  _unbind_wheel)

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

class _NameDialog(tk.Toplevel):
    """Generic single-text-field dialog. Returns result or None."""
    def __init__(self, master, title: str, prompt: str, default: str = ""):
        super().__init__(master)
        self.result = None
        self.title(title)
        self.configure(bg=BG_DARK)
        self.resizable(False, False)
        self.grab_set()
        pad = tk.Frame(self, bg=BG_DARK)
        pad.pack(padx=24, pady=20)
        tk.Label(pad, text=prompt, font=FONT_SMALL,
                 bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor="w")
        self._var = tk.StringVar(value=default)
        styled_entry(pad, self._var, width=28).pack(fill="x", pady=(4, 14), ipady=4)
        br = tk.Frame(pad, bg=BG_DARK); br.pack(fill="x")
        styled_button(br, "OK", command=self._submit, accent=True).pack(side="left")
        styled_button(br, "Cancel", command=self.destroy, small=True).pack(side="left", padx=8)
        self.bind("<Return>", lambda _: self._submit())
        self.wait_window()

    def _submit(self):
        v = self._var.get().strip()
        if v:
            self.result = v
        self.destroy()


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


# ─── Template Dialogs ─────────────────────────────────────────────────────────

class SaveTemplateDialog(tk.Toplevel):
    """Prompt for a template name and confirm saving."""
    def __init__(self, master, server, account):
        super().__init__(master)
        self.server  = server
        self.account = account
        self.result  = None
        self.title("Save as Template")
        self.configure(bg=BG_DARK)
        self.resizable(False, False)
        self.grab_set()
        self._build()
        self.wait_window()

    def _build(self):
        pad = tk.Frame(self, bg=BG_DARK)
        pad.pack(padx=28, pady=24)

        tk.Label(pad, text="Save Layout as Template", font=FONT_HEADING,
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, 14))

        existing = list_templates(self.server, self.account)
        if existing:
            tk.Label(pad, text="Existing templates:", font=FONT_SMALL,
                     bg=BG_DARK, fg=TEXT_MUTED).pack(anchor="w")
            for t in existing:
                tk.Label(pad, text=f"  • {t}", font=FONT_SMALL,
                         bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor="w")
            tk.Frame(pad, bg=BORDER, height=1).pack(fill="x", pady=10)

        tk.Label(pad, text="Template name", font=FONT_SMALL,
                 bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor="w")
        self.name_var = tk.StringVar()
        styled_entry(pad, self.name_var, width=32).pack(fill="x", pady=(2, 14), ipady=4)

        br = tk.Frame(pad, bg=BG_DARK); br.pack(fill="x")
        styled_button(br, "Save Template", command=self._submit, accent=True).pack(side="left")
        styled_button(br, "Cancel", command=self.destroy, small=True).pack(side="left", padx=8)

    def _submit(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing name", "Please enter a template name.", parent=self)
            return
        self.result = name
        self.destroy()


class LoadTemplateDialog(tk.Toplevel):
    """List existing templates and let the user pick one."""
    def __init__(self, master, server, account):
        super().__init__(master)
        self.server  = server
        self.account = account
        self.result  = None   # selected template name
        self.title("Load Template")
        self.configure(bg=BG_DARK)
        self.resizable(False, False)
        self.grab_set()
        self._build()
        self.wait_window()

    def _build(self):
        pad = tk.Frame(self, bg=BG_DARK)
        pad.pack(padx=28, pady=24)

        tk.Label(pad, text="Load Template", font=FONT_HEADING,
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, 10))

        templates = list_templates(self.server, self.account)
        if not templates:
            tk.Label(pad, text="No templates saved yet.", font=FONT_SMALL,
                     bg=BG_DARK, fg=TEXT_MUTED).pack(pady=(0, 14))
            styled_button(pad, "Close", command=self.destroy, small=True).pack(anchor="w")
            return

        tk.Label(pad, text="Select a template to load:", font=FONT_SMALL,
                 bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor="w", pady=(0, 8))

        self.selected = tk.StringVar(value=templates[0])
        list_frame = tk.Frame(pad, bg=BG_MID)
        list_frame.pack(fill="x", pady=(0, 14))
        for t in templates:
            tk.Radiobutton(
                list_frame, text=f"  {t}", variable=self.selected, value=t,
                bg=BG_MID, fg=TEXT_PRIMARY, selectcolor=BG_HOVER,
                activebackground=BG_MID, activeforeground=ACCENT,
                font=FONT_BODY, cursor="hand2", anchor="w"
            ).pack(fill="x", padx=8, pady=2)

        br = tk.Frame(pad, bg=BG_DARK); br.pack(fill="x")
        styled_button(br, "Load", command=self._submit, accent=True).pack(side="left")
        styled_button(br, "Cancel", command=self.destroy, small=True).pack(side="left", padx=8)

    def _submit(self):
        self.result = self.selected.get()
        self.destroy()


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
        self._combos        = {}   # slot_id -> building Combobox (for rebuilding values)
        self._level_combos  = {}   # slot_id -> level Combobox (for updating range)
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
        for b in buildings_for_tribe(self.tribe):
            if b in self._UNIQUE and b in used:
                continue
            result.append(b)
        return result

    def _on_building_change(self, slot_id, *_):
        """Rebuild available options in all other free combos, and update own level range."""
        # 1. Update unique-enforcement options in all other building combos
        for sid, cb in self._combos.items():
            if sid == slot_id:
                continue
            cur_val = self._building_vars[sid].get()
            new_vals = self._available_buildings(sid)
            cb["values"] = new_vals
            if cur_val not in new_vals:
                self._building_vars[sid].set("— Empty —")

        # 2. Update the level combo range for the slot whose building just changed
        lv_cb = self._level_combos.get(slot_id)
        if lv_cb is None:
            return
        new_building = self._building_vars[slot_id].get()
        if new_building and new_building != "— Empty —":
            opts = level_options(new_building)
        else:
            opts = BUILDING_LEVELS
        lv_cb["values"] = opts
        # Clamp current selection if it exceeds new max
        try:
            cur_lv = int(self._level_vars[slot_id].get())
        except ValueError:
            cur_lv = 0
        max_lv = int(opts[-1])
        if cur_lv > max_lv:
            self._level_vars[slot_id].set(str(max_lv))

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
                                         bg=BG_DARK, fg=COL_FULL_GREEN,
                                         width=22, anchor="w")
            self._save_status.pack(side="left", padx=(16, 0))
            styled_button(hdr, "📂  Load Template",
                          command=self._load_template, small=True).pack(side="left", padx=(0, 6))
            styled_button(hdr, "📋  Create Template",
                          command=self._create_template, small=True).pack(side="left", padx=(0, 6))
            styled_button(hdr, "💾  Save Layout",
                          command=self._save, accent=True).pack(side="left")

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
            cur_building = self._building_vars[slot_id].get() if not is_locked else locked_name
            opts = level_options(cur_building) if cur_building and cur_building != "— Empty —" else BUILDING_LEVELS
            lv_cb = styled_combo(row, self._level_vars[slot_id],
                                 opts, width=PLANNER_COLS[3][2], state=state)
            lv_cb.pack(side="left", padx=4, pady=3)
            if not is_locked:
                self._level_combos[slot_id] = lv_cb

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
        self._save_status.config(text="✓ Layout saved", fg=COL_FULL_GREEN)
        fade_label(self._save_status, after_ms=3500)

    def _collect_layout(self) -> dict:
        """Read current UI state into a layout dict (same as _save but without writing)."""
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
        return layout

    def _create_template(self):
        dlg = SaveTemplateDialog(self, self.server, self.account)
        if not dlg.result:
            return
        layout = self._collect_layout()
        save_template(self.server, self.account, dlg.result, layout)
        self._save_status.config(text=f"✓ Template '{dlg.result}' saved", fg=ACCENT)
        fade_label(self._save_status, after_ms=3500)

    def _load_template(self):
        dlg = LoadTemplateDialog(self, self.server, self.account)
        if not dlg.result:
            return
        layout = load_template(self.server, self.account, dlg.result)
        if not layout:
            return
        wall_building = WALL_BY_TRIBE.get(self.tribe, "Wall")
        for slot_id in range(1, 21):
            _, locked = VILLAGE_SLOTS[slot_id]
            if locked:
                continue   # never overwrite fixed slots
            data = layout.get(slot_id, {})
            b = data.get("building", "") or "— Empty —"
            lv = str(data.get("level", 0))
            self._building_vars[slot_id].set(b)
            self._level_vars[slot_id].set(lv)
        # Persist the applied template name in the village record
        update_village(self.server, self.account, self.village_name,
                       {"applied_template": dlg.result})
        self._save_status.config(text=f"✓ Loaded '{dlg.result}'", fg=ACCENT)
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
        self._cur_level_combos  = {}   # slot_id -> level Combobox
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
        for b in buildings_for_tribe(self.tribe):
            if b in self._UNIQUE and b in used:
                continue
            result.append(b)
        return result

    def _on_cur_building_change(self, slot_id, *_):
        # 1. Update unique-enforcement options in all other building combos
        for sid, cb in self._cur_combos.items():
            if sid == slot_id: continue
            cur_val = self._cur_building_vars[sid].get()
            new_vals = self._available_cur(sid)
            cb["values"] = new_vals
            if cur_val not in new_vals:
                self._cur_building_vars[sid].set("— Empty —")

        # 2. Update level combo range for the changed slot
        lv_cb = self._cur_level_combos.get(slot_id)
        if lv_cb is None:
            return
        new_building = self._cur_building_vars[slot_id].get()
        if new_building and new_building != "— Empty —":
            opts = level_options(new_building)
        else:
            opts = BUILDING_LEVELS
        lv_cb["values"] = opts
        try:
            cur_lv = int(self._cur_level_vars[slot_id].get())
        except ValueError:
            cur_lv = 0
        max_lv = int(opts[-1])
        if cur_lv > max_lv:
            self._cur_level_vars[slot_id].set(str(max_lv))

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
            cur_bname = self._cur_building_vars[slot_id].get() if not locked_name else locked_name
            opts = level_options(cur_bname) if cur_bname and cur_bname != "— Empty —" else BUILDING_LEVELS
            lv_cb = styled_combo(row, self._cur_level_vars[slot_id],
                                 opts, width=BUILDINGS_COLS[4][2], state=state)
            lv_cb.pack(side="left", padx=4, pady=3)
            if not locked_name:
                self._cur_level_combos[slot_id] = lv_cb

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
                    self._update_summary()
                return _trace
            self._cur_level_vars[slot_id].trace_add(
                "write", _make_bar_tracer(slot_id, p_level))

        # ── Summary row ──────────────────────────────────────────────────────
        make_separator(inner, bg=BORDER).pack(fill="x", pady=(6, 2))
        self._summary_row = tk.Frame(inner, bg=BG_PANEL)
        self._summary_row.pack(fill="x", pady=(2, 6))
        tk.Label(self._summary_row, text="Overall progress:", font=("Consolas", 9, "bold"),
                 bg=BG_PANEL, fg=TEXT_SECONDARY).pack(side="left", padx=12)
        self._summary_label = tk.Label(self._summary_row, text="", font=("Consolas", 10, "bold"),
                                       bg=BG_PANEL, fg=TEXT_MUTED)
        self._summary_label.pack(side="left", padx=4)
        self._update_summary()

    def _update_summary(self):
        """Recalculate overall progress from current UI state and update label."""
        planned_total = 0
        current_total = 0
        for slot_id in range(1, 21):
            p_level = self._planned_levels.get(slot_id, 0)
            planned_total += p_level
            if p_level > 0:
                try:    c = int(self._cur_level_vars[slot_id].get())
                except: c = 0
                current_total += min(c, p_level)
        if planned_total == 0:
            self._summary_label.config(text="No layout planned", fg=TEXT_MUTED)
            return
        ratio = current_total / planned_total
        pct   = int(ratio * 100)
        col   = progress_color(current_total, planned_total)
        self._summary_label.config(text=f"{pct}%  ({current_total} / {planned_total} levels)",
                                   fg=col)

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

# ─── Village Troops View ──────────────────────────────────────────────────────

# Row metadata: key, label, bg colour, text colour
_TROOP_ROW_META = [
    ("trained",    "Trained here",        BG_PANEL, TEXT_PRIMARY),
    ("native_in",  "Native in village",   BG_PANEL, TEXT_PRIMARY),
    ("native_out", "Native sent out",     BG_PANEL, TEXT_MUTED),      # calculated
    ("foreign_in", "Foreign in village",  BG_PANEL, TEXT_PRIMARY),
]
_NET_ROW_BG  = "#1a2540"   # distinct highlight for net row
_NET_ROW_FG  = ACCENT

class VillageTroopsView(tk.Frame):
    """
    Horizontal troop table for a village.

    Columns  : one per tribe troop (name header + editable count cells)
    Rows     : Trained here / Native in village / Native sent out (calculated) /
               Foreign in village / [NET] Net troops in village
    Constraint: native_in + native_out = trained  →  native_out = trained - native_in
    Net row  : native_in + foreign_in  (troops physically present), highlighted.
    All editable cells persist to *_troops.csv.
    """

    def __init__(self, master, server, account, village_name, tribe, is_archived=False):
        super().__init__(master, bg=BG_DARK)
        self.server       = server
        self.account      = account
        self.village_name = village_name
        self.tribe        = tribe
        self.is_archived  = is_archived

        self._troop_names     = get_tribe_troops(tribe)
        self._vars            = {}   # (row_key, troop_name) -> StringVar
        self._net_labels      = {}   # troop_name -> Label (net row)
        self._native_out_lbls = {}   # troop_name -> Label (calculated native_out)

        self._load_and_build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _load_and_build(self):
        data = load_troop_data(self.server, self.account,
                               self.village_name, self._troop_names)

        # Header
        hdr = tk.Frame(self, bg=BG_DARK)
        hdr.pack(fill="x", padx=24, pady=(24, 0))
        tk.Label(hdr, text=f"{self.village_name}  —  Troops",
                 font=FONT_TITLE, bg=BG_DARK, fg=TEXT_PRIMARY).pack(side="left")
        if not self.is_archived:
            self._status_lbl = tk.Label(hdr, text="", font=FONT_SMALL,
                                        bg=BG_DARK, fg=COL_FULL_GREEN, width=22, anchor="w")
            self._status_lbl.pack(side="left", padx=(16, 0))
            styled_button(hdr, "💾  Save", command=self._save,
                          accent=True).pack(side="left")

        make_separator(self).pack(fill="x", padx=24, pady=10)

        if not self._troop_names:
            tk.Label(self, text=f"No troop data found for tribe '{self.tribe}'.",
                     font=FONT_BODY, bg=BG_DARK, fg=TEXT_MUTED).pack(padx=24, anchor="w")
            return

        # Scrollable table — single grid frame so columns align perfectly
        outer, inner = scrollable_frame(self)
        outer.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        n_troops = len(self._troop_names)
        tbl = tk.Frame(inner, bg=BG_DARK)
        tbl.pack(fill="x")
        tbl.columnconfigure(0, minsize=160)
        for c in range(1, n_troops + 1):
            tbl.columnconfigure(c, minsize=90, uniform="troop")

        def cell_bg(row_idx):
            return BG_MID if row_idx % 2 == 0 else BG_PANEL

        # ── Column header row (troop names) ──
        tk.Label(tbl, text="", bg=BG_MID, padx=6, pady=3).grid(
            row=0, column=0, sticky="nsew", padx=(0,1), pady=(0,1))
        for ci, tname in enumerate(self._troop_names):
            disp = tname if len(tname) <= 12 else tname[:11] + "…"
            lbl = tk.Label(tbl, text=disp, font=("Consolas", 9, "bold"),
                           bg=BG_MID, fg=ACCENT, anchor="center", padx=4, pady=3)
            lbl.grid(row=0, column=ci + 1, sticky="nsew", padx=(0,1), pady=(0,1))
            lbl.bind("<Enter>", lambda e, w=lbl, full=tname: w.config(text=full))
            lbl.bind("<Leave>", lambda e, w=lbl, d=disp: w.config(text=d))

        # 1px separator
        tk.Frame(tbl, bg=BORDER, height=1).grid(
            row=1, column=0, columnspan=n_troops + 1, sticky="ew", pady=(0,1))

        # ── Data rows ──
        state = "disabled" if self.is_archived else "normal"
        for row_idx, (rk, rlabel, _, _) in enumerate(_TROOP_ROW_META):
            gr  = row_idx + 2
            bg  = cell_bg(row_idx)
            tk.Label(tbl, text=rlabel, font=FONT_SMALL, bg=bg, fg=TEXT_SECONDARY,
                     anchor="w", padx=8, pady=2).grid(
                row=gr, column=0, sticky="nsew", padx=(0,1), pady=(0,1))

            for ci, tname in enumerate(self._troop_names):
                if rk == "native_out":
                    lbl = tk.Label(tbl, text="0", font=FONT_SMALL,
                                   bg=bg, fg=TEXT_MUTED, anchor="center", pady=2)
                    lbl.grid(row=gr, column=ci + 1, sticky="nsew", padx=(0,1), pady=(0,1))
                    self._native_out_lbls[tname] = lbl
                else:
                    var = tk.StringVar(value=str(data[rk].get(tname, 0)))
                    self._vars[(rk, tname)] = var
                    sb = tk.Spinbox(
                        tbl, textvariable=var,
                        from_=0, to=999999, increment=1,
                        bg=BG_MID, fg=TEXT_PRIMARY, buttonbackground=BG_HOVER,
                        insertbackground=ACCENT, relief="flat", bd=0,
                        highlightthickness=0, disabledbackground=bg,
                        disabledforeground=TEXT_MUTED, state=state,
                        font=FONT_SMALL, justify="center")
                    sb.grid(row=gr, column=ci + 1, sticky="nsew", padx=(0,1), pady=(0,1))
                    var.trace_add("write", lambda *_, t=tname: self._update_derived(t))

        # 1px separator before net row
        net_gr = len(_TROOP_ROW_META) + 2
        tk.Frame(tbl, bg=ACCENT_DIM, height=1).grid(
            row=net_gr, column=0, columnspan=n_troops + 1, sticky="ew", pady=(2,1))

        # ── Net row ──
        net_gr += 1
        tk.Label(tbl, text="Net troops in village", font=("Consolas", 9, "bold"),
                 bg=_NET_ROW_BG, fg=_NET_ROW_FG, anchor="w", padx=8, pady=4).grid(
            row=net_gr, column=0, sticky="nsew", padx=(0,1), pady=(0,1))
        for ci, tname in enumerate(self._troop_names):
            net_lbl = tk.Label(tbl, text="0", font=("Consolas", 9, "bold"),
                               bg=_NET_ROW_BG, fg=_NET_ROW_FG, anchor="center", pady=4)
            net_lbl.grid(row=net_gr, column=ci + 1, sticky="nsew", padx=(0,1), pady=(0,1))
            self._net_labels[tname] = net_lbl

        # Initial calculation pass
        for tname in self._troop_names:
            self._update_derived(tname)

    # ── Derived calculations ──────────────────────────────────────────────────

    def _get_int(self, rk, tname) -> int:
        try:
            return max(0, int(self._vars[(rk, tname)].get() or 0))
        except (ValueError, KeyError):
            return 0

    def _update_derived(self, tname: str):
        """
        native_out = trained - native_in   (clamped to 0)
        net        = native_in + foreign_in
        """
        trained    = self._get_int("trained",   tname)
        native_in  = self._get_int("native_in", tname)
        foreign_in = self._get_int("foreign_in", tname)

        native_out = max(0, trained - native_in)
        net        = native_in + foreign_in

        out_lbl = self._native_out_lbls.get(tname)
        if out_lbl:
            out_lbl.config(text=str(native_out))

        net_lbl = self._net_labels.get(tname)
        if net_lbl:
            net_lbl.config(
                text=str(net),
                fg=COL_FULL_GREEN if net > 0 else _NET_ROW_FG)

    # ── Save ─────────────────────────────────────────────────────────────────

    def _save(self):
        data = {rk: {} for rk in TROOP_ROWS}
        for (rk, tname), var in self._vars.items():
            try:
                data[rk][tname] = max(0, int(var.get() or 0))
            except ValueError:
                data[rk][tname] = 0
        # Derive native_out before saving so CSV stays consistent
        for tname in self._troop_names:
            trained   = data["trained"].get(tname, 0)
            native_in = data["native_in"].get(tname, 0)
            data["native_out"][tname] = max(0, trained - native_in)
        save_troop_data(self.server, self.account,
                        self.village_name, self._troop_names, data)
        self._status_lbl.config(text="✓ Troops saved", fg=COL_FULL_GREEN)
        fade_label(self._status_lbl, after_ms=3500)


# ─── Village Resource Layout View ─────────────────────────────────────────────

_RES_ICONS = {"Woodcutter": "🌲", "Clay Pit": "🧱", "Iron Mine": "⚙", "Cropland": "🌾"}
_RES_LEVEL_MAX = {"Woodcutter": 10, "Clay Pit": 10, "Iron Mine": 10, "Cropland": 10}

class VillageResourceLayoutView(tk.Frame):
    """18 resource field slots, each with a type and level selector."""

    def __init__(self, master, server, account, village_name, is_archived=False,
                 on_save=None):
        super().__init__(master, bg=BG_DARK)
        self.server       = server
        self.account      = account
        self.village_name = village_name
        self.is_archived  = is_archived
        self._on_save     = on_save
        self._type_vars   = {}   # slot_str -> StringVar
        self._level_vars  = {}   # slot_str -> StringVar
        self._load_and_build()

    def _load_and_build(self):
        slots = load_resource_layout(self.server, self.account, self.village_name)

        hdr = tk.Frame(self, bg=BG_DARK)
        hdr.pack(fill="x", padx=24, pady=(24, 0))
        tk.Label(hdr, text=f"{self.village_name}  —  Resource Layout",
                 font=FONT_TITLE, bg=BG_DARK, fg=TEXT_PRIMARY).pack(side="left")
        if not self.is_archived:
            self._status = tk.Label(hdr, text="", font=FONT_SMALL,
                                    bg=BG_DARK, fg=COL_FULL_GREEN, width=22, anchor="w")
            self._status.pack(side="left", padx=(16, 0))
            styled_button(hdr, "💾  Save", command=self._save,
                          accent=True).pack(side="left")

        make_separator(self).pack(fill="x", padx=24, pady=10)
        tk.Label(self, text="Set the type and level for each of the 18 resource fields.",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(anchor="w", padx=24, pady=(0, 10))

        outer, inner = scrollable_frame(self)
        outer.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        # Column headers
        col_hdr = tk.Frame(inner, bg=BG_PANEL)
        col_hdr.pack(fill="x", pady=(0, 2))
        for text, w in [("Slot", 5), ("Type", 16), ("Level", 8)]:
            tk.Label(col_hdr, text=text, font=("Consolas", 8, "bold"),
                     bg=BG_PANEL, fg=TEXT_MUTED, width=w, anchor="w").pack(side="left", padx=4)
        make_separator(inner, bg=BORDER).pack(fill="x", pady=(0, 4))

        state = "disabled" if self.is_archived else "readonly"
        level_opts = [str(i) for i in range(0, 11)]

        for i, slot in enumerate(slots):
            skey = slot["slot"]
            row_bg = BG_MID if i % 2 == 0 else BG_PANEL
            row = tk.Frame(inner, bg=row_bg)
            row.pack(fill="x", pady=1)

            tk.Label(row, text=skey, width=5, bg=row_bg,
                     fg=TEXT_MUTED, font=FONT_SMALL, anchor="w").pack(side="left", padx=4)

            t_var = tk.StringVar(value=slot.get("type", "Cropland"))
            self._type_vars[skey] = t_var
            styled_combo(row, t_var, RESOURCE_TYPES, width=16,
                         state=state).pack(side="left", padx=4, pady=2)

            l_var = tk.StringVar(value=str(slot.get("level", "0")))
            self._level_vars[skey] = l_var
            styled_combo(row, l_var, level_opts, width=8,
                         state=state).pack(side="left", padx=4, pady=2)

            # Icon preview that updates with type
            icon_lbl = tk.Label(row, text=_RES_ICONS.get(slot.get("type","Cropland"), ""),
                                font=FONT_BODY, bg=row_bg, fg=TEXT_PRIMARY)
            icon_lbl.pack(side="left", padx=4)
            t_var.trace_add("write", lambda *_, v=t_var, lbl=icon_lbl, bg=row_bg:
                            lbl.config(text=_RES_ICONS.get(v.get(), ""), bg=bg))

    def _save(self):
        slots = []
        for i in range(1, 19):
            skey = str(i)
            slots.append({
                "slot":  skey,
                "type":  self._type_vars[skey].get(),
                "level": self._level_vars[skey].get(),
            })
        save_resource_layout(self.server, self.account, self.village_name, slots)
        self._status.config(text="✓ Resource layout saved", fg=COL_FULL_GREEN)
        fade_label(self._status, after_ms=3500)
        if self._on_save:
            self._on_save()


# ─── Troop Overview Import Dialog ─────────────────────────────────────────────

class TroopOverviewImportDialog(tk.Toplevel):
    """
    Paste the raw text from the Travian 'Troops → Training' overview page.
    Parses the troop table + village sidebar, adds missing villages, and
    fills each village's 'trained here' troop counts.
    """
    def __init__(self, master, server, account, tribe, on_complete=None):
        super().__init__(master)
        self.server      = server
        self.account     = account
        self.tribe       = tribe
        self._on_complete = on_complete
        self.title("Import Troop Overview")
        self.configure(bg=BG_DARK)
        self.geometry("780x620")
        self.grab_set()
        self._parsed = None
        self._build()

    def _build(self):
        pad = tk.Frame(self, bg=BG_DARK)
        pad.pack(fill="both", expand=True, padx=20, pady=16)

        tk.Label(pad, text="Import Troop Overview", font=FONT_HEADING,
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, 4))
        tk.Label(pad,
                 text="Paste the full page text from Travian's Troops → Training overview.\n"
                      "Villages will be added automatically. Troop counts fill 'Trained here'.",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED,
                 justify="left").pack(anchor="w", pady=(0, 10))

        # Text area
        txt_frame = tk.Frame(pad, bg=BORDER)
        txt_frame.pack(fill="both", expand=True)
        self._txt = tk.Text(txt_frame, bg=BG_MID, fg=TEXT_PRIMARY,
                            insertbackground=ACCENT, font=("Consolas", 9),
                            relief="flat", bd=6, wrap="none",
                            selectbackground=BG_HOVER)
        sb_y = tk.Scrollbar(txt_frame, command=self._txt.yview,
                             bg=BG_MID, troughcolor=BG_DARK, relief="flat", bd=0, width=8)
        sb_x = tk.Scrollbar(txt_frame, orient="horizontal",
                             command=self._txt.xview,
                             bg=BG_MID, troughcolor=BG_DARK, relief="flat", bd=0, width=8)
        self._txt.config(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        sb_y.pack(side="right", fill="y")
        sb_x.pack(side="bottom", fill="x")
        self._txt.pack(fill="both", expand=True)

        # Preview area (shown after parse)
        self._preview_frame = tk.Frame(pad, bg=BG_DARK)
        self._preview_frame.pack(fill="x", pady=(8, 0))

        # Buttons
        btn_row = tk.Frame(pad, bg=BG_DARK)
        btn_row.pack(fill="x", pady=(10, 0))
        styled_button(btn_row, "🔍  Parse", command=self._parse,
                      accent=True).pack(side="left")
        styled_button(btn_row, "✅  Import", command=self._import,
                      small=True).pack(side="left", padx=8)
        self._status_lbl = tk.Label(btn_row, text="", font=FONT_SMALL,
                                    bg=BG_DARK, fg=COL_FULL_GREEN)
        self._status_lbl.pack(side="left", padx=8)
        styled_button(btn_row, "Close", command=self.destroy,
                      small=True).pack(side="right")

    def _parse(self):
        raw = self._txt.get("1.0", "end")
        result = parse_troop_overview(raw, self.tribe)

        for w in self._preview_frame.winfo_children():
            w.destroy()

        if result is None:
            tk.Label(self._preview_frame,
                     text="❌  Could not find a valid troop table. Make sure you pasted the full page.",
                     font=FONT_SMALL, bg=BG_DARK, fg=COL_RED).pack(anchor="w")
            self._parsed = None
            return

        self._parsed = result
        vt = result["village_troops"]
        coords = result["village_coords"]
        groups = result["village_groups"]

        existing = {v["village_name"] for v in load_villages(self.server, self.account)}
        new_villages = [vn for vn in vt if vn not in existing]

        # Summary
        tk.Label(self._preview_frame,
                 text=f"✔  Found {len(vt)} villages · {len(result['troop_columns'])} troop types · "
                      f"{len(new_villages)} new villages to add · "
                      f"{len(coords)} coordinates found",
                 font=FONT_SMALL, bg=BG_DARK, fg=COL_FULL_GREEN).pack(anchor="w")

        if new_villages:
            tk.Label(self._preview_frame,
                     text="New villages: " + ", ".join(new_villages),
                     font=FONT_SMALL, bg=BG_DARK, fg=ACCENT,
                     wraplength=700, justify="left").pack(anchor="w", pady=(2, 0))

        if groups:
            group_summary = ", ".join(f"{vn}→{g}" for vn, g in list(groups.items())[:6])
            if len(groups) > 6:
                group_summary += f" … (+{len(groups)-6} more)"
            tk.Label(self._preview_frame,
                     text="Groups: " + group_summary,
                     font=FONT_SMALL, bg=BG_DARK, fg=TEXT_SECONDARY,
                     wraplength=700, justify="left").pack(anchor="w", pady=(2, 0))

    def _import(self):
        if self._parsed is None:
            self._parse()
        if self._parsed is None:
            return

        vt     = self._parsed["village_troops"]
        coords = self._parsed["village_coords"]
        groups = self._parsed["village_groups"]
        cols   = self._parsed["troop_columns"]

        # Debug: show what we're about to import
        self._status_lbl.config(
            text=f"⏳ Importing {len(vt)} villages...", fg=TEXT_SECONDARY)
        self.update_idletasks()

        # Load once, work in memory, write once at the end
        # Ensure account directory exists before writing any files
        try:
            account_dir(self.server, self.account).mkdir(parents=True, exist_ok=True)
            snapshots_dir(self.server, self.account).mkdir(exist_ok=True)

            existing_villages = load_villages(self.server, self.account)
            existing_map      = {v["village_name"]: v for v in existing_villages}

            output_villages = []
            added = 0
            tribe_troops = get_tribe_troops(self.tribe)
            troop_errors = []

            for vname, troop_counts in vt.items():
                cx, cy = coords.get(vname, ("", ""))
                grp    = groups.get(vname, "")

                if vname in existing_map:
                    v = existing_map[vname]
                    if not v.get("coord_x") and cx:  v["coord_x"] = cx
                    if not v.get("coord_y") and cy:  v["coord_y"] = cy
                    if not v.get("group")   and grp: v["group"]   = grp
                    output_villages.append(v)
                else:
                    output_villages.append({
                        "village_name":     vname,
                        "coord_x":          cx,
                        "coord_y":          cy,
                        "res_wood":         4,
                        "res_clay":         4,
                        "res_iron":         4,
                        "res_crop":         6,
                        "applied_template": "",
                        "group":            grp,
                    })
                    added += 1

                try:
                    troop_data = load_troop_data(self.server, self.account, vname, tribe_troops)
                    for t in tribe_troops:
                        for col in cols:
                            if col.lower() == t.lower():
                                troop_data["trained"][t] = troop_counts.get(col, 0)
                                break
                    for t in tribe_troops:
                        troop_data["native_out"][t] = max(
                            0, troop_data["trained"].get(t, 0) - troop_data["native_in"].get(t, 0))
                    save_troop_data(self.server, self.account, vname, tribe_troops, troop_data)
                except Exception as e:
                    troop_errors.append(f"{vname}: {e}")

            _rewrite_villages(self.server, self.account, output_villages)

            if self._on_complete:
                self._on_complete()

            if troop_errors:
                log_path = account_dir(self.server, self.account) / "import_errors.txt"
                with open(log_path, "w", encoding="utf-8") as lf:
                    lf.write("\n".join(troop_errors))
                msg = (f"⚠  {len(output_villages)} villages written ({added} new), "
                       f"{len(troop_errors)} troop errors — see import_errors.txt")
                self._status_lbl.config(text=msg, fg=COL_ORANGE)
            else:
                msg = f"✅  Imported {len(output_villages)} villages ({added} new). Troop data updated."
                self._status_lbl.config(text=msg, fg=COL_FULL_GREEN)

        except Exception as fatal:
            self._status_lbl.config(
                text=f"❌ Fatal error: {fatal}", fg=COL_RED)

        if self._on_complete:
            self._on_complete()


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
            ("⚔   Troops Overview",  self._show_troops_overview),
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
        snap_btn.pack(fill="x", padx=8, pady=(0, 4))
        imp_btn = styled_button(pad, "📥 Import Overview", command=self._open_troops_import,
                                small=True, accent=not self.is_archived)
        imp_btn.pack(fill="x", padx=8, pady=(0, 8))
        if self.is_archived:
            snap_btn.config(state="disabled", fg=TEXT_MUTED, bg=BG_HOVER)
            imp_btn.config(state="disabled", fg=TEXT_MUTED, bg=BG_HOVER)

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
            ("🗺   Layout Planner",    lambda: self._show_village_layout(vn)),
            ("🏗   Buildings",         lambda: self._show_village_buildings(vn)),
            ("🌾  Resource Layout",    lambda: self._show_resource_layout(vn)),
            ("🔄  Trade Routes",       lambda: self._show_trade_routes(vn)),
            ("📋  Set Trade Route",    lambda: self._show_set_trade_route(vn)),
            ("🪖  Troops",             lambda: self._show_troops(vn)),
        ]:
            nav_button(self.village_nav_frame, label, command=cmd).pack(fill="x")

        make_separator(self.village_nav_frame).pack(fill="x", padx=8, pady=4)
        styled_button(self.village_nav_frame, "← Account overview",
                      command=self._rebuild_account_nav,
                      small=True).pack(fill="x", padx=8, pady=(0, 4))

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
        villages = load_villages(self.server, self.account)

        outer = tk.Frame(self.center, bg=BG_DARK)
        outer.pack(fill="both", expand=True)

        # ── Header ───────────────────────────────────────────────────────────
        hdr = tk.Frame(outer, bg=BG_DARK)
        hdr.pack(fill="x", padx=24, pady=(24, 0))
        tk.Label(hdr, text="Production Info",
                 font=FONT_TITLE, bg=BG_DARK, fg=TEXT_PRIMARY).pack(side="left")
        tk.Label(hdr, text="  —  hourly resource output per village",
                 font=FONT_BODY, bg=BG_DARK, fg=TEXT_MUTED).pack(side="left", pady=(6, 0))

        # Gold bonus toggle — persisted in options.csv
        gold_var = tk.BooleanVar(value=load_option("gold_bonus", "False") == "True")
        gold_frame = tk.Frame(hdr, bg=BG_MID, relief="flat", bd=0,
                              highlightthickness=1, highlightbackground=BORDER)
        gold_frame.pack(side="right", padx=(12, 0))

        def _refresh_table(*_):
            save_option("gold_bonus", gold_var.get())
            _build_table(gold_var.get())

        gold_cb = tk.Checkbutton(
            gold_frame, text="💰 +25% Gold Bonus",
            variable=gold_var, command=_refresh_table,
            bg=BG_MID, fg=TEXT_PRIMARY, selectcolor=BG_HOVER,
            activebackground=BG_MID, activeforeground=ACCENT,
            font=FONT_SMALL, relief="flat", bd=0,
            highlightthickness=0)
        gold_cb.pack(padx=8, pady=4)

        make_separator(outer).pack(fill="x", padx=24, pady=10)

        if not villages:
            tk.Label(outer, text="No villages found for this account.",
                     font=FONT_BODY, bg=BG_DARK, fg=TEXT_MUTED).pack(padx=24, anchor="w")
            return

        # ── Table container (rebuilt on toggle) ──────────────────────────────
        table_container = tk.Frame(outer, bg=BG_DARK)
        table_container.pack(fill="both", expand=True)

        COLS = [
            (1, "🌲 Wood",  "wood",  "#7daa6f"),
            (2, "🧱 Clay",  "clay",  "#b87c4c"),
            (3, "⚙ Iron",  "iron",  "#8aabcc"),
            (4, "🌾 Crop",  "crop",  "#c8b84a"),
        ]

        def _build_table(gold_bonus: bool):
            for w in table_container.winfo_children():
                w.destroy()

            rows   = []
            totals = {"wood": 0, "clay": 0, "iron": 0, "crop": 0}
            for v in villages:
                vname = v["village_name"]
                prod  = calculate_village_production(
                    self.server, self.account, vname, gold_bonus)
                rows.append((vname, prod))
                for k in totals:
                    totals[k] += prod[k]

            scroll_outer, inner = scrollable_frame(table_container)
            scroll_outer.pack(fill="both", expand=True, padx=24, pady=(0, 16))

            tbl = tk.Frame(inner, bg=BG_DARK)
            tbl.pack(fill="x")
            tbl.columnconfigure(0, minsize=180)
            for c in range(1, 5):
                tbl.columnconfigure(c, minsize=90, uniform="res")

            def gl(row, col, text, bg, fg, bold=False, anchor="center"):
                font = ("Consolas", 9, "bold") if bold else FONT_SMALL
                tk.Label(tbl, text=text, font=font, bg=bg, fg=fg,
                         anchor=anchor, padx=6, pady=3
                         ).grid(row=row, column=col, sticky="nsew",
                                padx=(0, 1), pady=(0, 1))

            # header
            gl(0, 0, "Village",   BG_MID, TEXT_MUTED, bold=True, anchor="w")
            for col, label, _, color in COLS:
                gl(0, col, label, BG_MID, color, bold=True)
            tk.Frame(tbl, bg=BORDER, height=1).grid(
                row=1, column=0, columnspan=5, sticky="ew", pady=(0, 1))

            for i, (vname, prod) in enumerate(rows):
                r  = i + 2
                bg = BG_MID if i % 2 == 0 else BG_PANEL
                gl(r, 0, vname, bg, TEXT_PRIMARY, anchor="w")
                for col, _, key, color in COLS:
                    val = prod[key]
                    fg  = color if val > 0 else TEXT_MUTED
                    gl(r, col, f"{val:,}" if val else "—", bg, fg)

            total_row = len(rows) + 2
            tk.Frame(tbl, bg=ACCENT_DIM, height=1).grid(
                row=total_row, column=0, columnspan=5, sticky="ew", pady=(2, 1))
            total_row += 1
            gl(total_row, 0, "Account Total", BG_HOVER, ACCENT, bold=True, anchor="w")
            for col, _, key, color in COLS:
                gl(total_row, col, f"{totals[key]:,}", BG_HOVER, COL_FULL_GREEN, bold=True)

            grand = sum(totals.values())
            bonus_note = "  (incl. 25% gold bonus)" if gold_bonus else ""
            tk.Label(inner,
                     text=f"Total production across all villages:  {grand:,} /hr{bonus_note}",
                     font=("Consolas", 9, "bold"), bg=BG_DARK, fg=ACCENT
                     ).pack(anchor="w", padx=4, pady=(8, 4))

        _build_table(gold_var.get())

    def _show_troops_overview(self):
        self._clear_center()
        troop_names = get_tribe_troops(self.tribe)
        villages    = load_villages(self.server, self.account)

        # ── outer frame ──────────────────────────────────────────────────────
        outer = tk.Frame(self.center, bg=BG_DARK)
        outer.pack(fill="both", expand=True)

        hdr = tk.Frame(outer, bg=BG_DARK)
        hdr.pack(fill="x", padx=24, pady=(24, 0))
        tk.Label(hdr, text="Troops Overview",
                 font=FONT_TITLE, bg=BG_DARK, fg=TEXT_PRIMARY).pack(side="left")
        tk.Label(hdr, text=f"  —  trained troops per village",
                 font=FONT_BODY, bg=BG_DARK, fg=TEXT_MUTED).pack(side="left", pady=(6, 0))
        make_separator(outer).pack(fill="x", padx=24, pady=10)

        if not villages:
            tk.Label(outer, text="No villages found for this account.",
                     font=FONT_BODY, bg=BG_DARK, fg=TEXT_MUTED).pack(padx=24, anchor="w")
            return

        if not troop_names:
            tk.Label(outer, text=f"No troop data found for tribe '{self.tribe}'.",
                     font=FONT_BODY, bg=BG_DARK, fg=TEXT_MUTED).pack(padx=24, anchor="w")
            return

        # ── load all village troop data ───────────────────────────────────────
        rows = []   # list of (village_name, {troop: count})
        totals = {t: 0 for t in troop_names}
        for v in villages:
            vname = v["village_name"]
            data  = load_troop_data(self.server, self.account, vname, troop_names)
            trained = data.get("trained", {})
            rows.append((vname, trained))
            for t in troop_names:
                totals[t] += trained.get(t, 0)

        # ── scrollable table ─────────────────────────────────────────────────
        scroll_outer, inner = scrollable_frame(outer)
        scroll_outer.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        # Single grid frame — all rows share the same column geometry
        tbl = tk.Frame(inner, bg=BG_DARK)
        tbl.pack(fill="x")

        n_troops = len(troop_names)
        # Column 0 = village name, columns 1..n = troops
        tbl.columnconfigure(0, minsize=180)
        for c in range(1, n_troops + 1):
            tbl.columnconfigure(c, minsize=90, uniform="troop")

        def grid_label(row, col, text, bg, fg, bold=False, anchor="center"):
            font = ("Consolas", 9, "bold") if bold else FONT_SMALL
            lbl = tk.Label(tbl, text=text, font=font, bg=bg, fg=fg,
                           anchor=anchor, padx=6, pady=3)
            lbl.grid(row=row, column=col, sticky="nsew", padx=(0, 1), pady=(0, 1))
            return lbl

        # ── header row ───────────────────────────────────────────────────────
        grid_label(0, 0, "Village", BG_MID, TEXT_MUTED, bold=True, anchor="w")
        for ci, t in enumerate(troop_names):
            disp = t if len(t) <= 12 else t[:11] + "…"
            lbl = grid_label(0, ci + 1, disp, BG_MID, ACCENT, bold=True)
            if len(t) > 12:
                lbl.bind("<Enter>", lambda e, w=lbl, full=t: w.config(text=full))
                lbl.bind("<Leave>", lambda e, w=lbl, d=disp: w.config(text=d))

        # 1px separator row
        sep = tk.Frame(tbl, bg=BORDER, height=1)
        sep.grid(row=1, column=0, columnspan=n_troops + 1, sticky="ew", pady=(0, 1))

        # ── village rows ─────────────────────────────────────────────────────
        for i, (vname, trained) in enumerate(rows):
            r   = i + 2
            bg  = BG_MID if i % 2 == 0 else BG_PANEL
            grid_label(r, 0, vname, bg, TEXT_PRIMARY, anchor="w")
            for ci, t in enumerate(troop_names):
                val = trained.get(t, 0)
                fg  = TEXT_PRIMARY if val > 0 else TEXT_MUTED
                grid_label(r, ci + 1, str(val) if val else "—", bg, fg)

        # 1px separator before sum
        sep2 = tk.Frame(tbl, bg=ACCENT_DIM, height=1)
        sep2.grid(row=len(rows) + 2, column=0, columnspan=n_troops + 1,
                  sticky="ew", pady=(2, 1))

        # ── sum row ──────────────────────────────────────────────────────────
        sum_r = len(rows) + 3
        grand_total = sum(totals.values())
        grid_label(sum_r, 0, "Account Total", BG_HOVER, ACCENT, bold=True, anchor="w")
        for ci, t in enumerate(troop_names):
            val = totals[t]
            fg  = COL_FULL_GREEN if val > 0 else TEXT_MUTED
            grid_label(sum_r, ci + 1, str(val) if val else "—", BG_HOVER, fg, bold=True)

        # grand total badge
        tk.Label(inner,
                 text=f"Total troops across all villages:  {grand_total:,}",
                 font=("Consolas", 9, "bold"), bg=BG_DARK,
                 fg=ACCENT).pack(anchor="w", padx=4, pady=(8, 4))

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

    def _show_troops(self, village):
        self._clear_center()
        view = VillageTroopsView(
            self.center, self.server, self.account,
            village, self.tribe, self.is_archived)
        view.pack(fill="both", expand=True)

    def _show_resource_layout(self, village):
        self._clear_center()
        view = VillageResourceLayoutView(
            self.center, self.server, self.account,
            village, self.is_archived,
            on_save=lambda: self._refresh_village_list())
        view.pack(fill="both", expand=True)

    def _open_troops_import(self):
        if self.is_archived:
            return
        TroopOverviewImportDialog(
            self, self.server, self.account, self.tribe,
            on_complete=self._refresh_village_list)

    # ── Snapshot ──────────────────────────────────────────────────────────────

    def _take_snapshot(self):
        dst = take_snapshot(self.server, self.account)
        if dst:
            messagebox.showinfo("Snapshot Saved", f"Saved to:\n{dst}", parent=self)
        else:
            messagebox.showwarning("Snapshot Failed", "No village data found.", parent=self)

    # ── Right panel: village list (drag-and-drop + groups) ───────────────────

    def _build_right_panel(self, parent):
        right = tk.Frame(parent, bg=BG_PANEL, width=220)
        right.grid(row=0, column=2, sticky="nsew")
        right.pack_propagate(False)

        # Header bar
        hdr = tk.Frame(right, bg=BG_MID)
        hdr.pack(fill="x")
        tk.Label(hdr, text="VILLAGES", font=("Consolas", 9, "bold"),
                 bg=BG_MID, fg=TEXT_MUTED).pack(side="left", padx=12, pady=8)
        if not self.is_archived:
            styled_button(hdr, "＋", command=self._add_village_dialog,
                          small=True, accent=True).pack(side="right", padx=4, pady=6)
            styled_button(hdr, "⊞", command=self._add_group_dialog,
                          small=True).pack(side="right", padx=0, pady=6)
        make_separator(right).pack(fill="x")

        # Scrollable canvas for village cards
        container = tk.Frame(right, bg=BG_PANEL)
        container.pack(fill="both", expand=True)
        self._vscroll = tk.Scrollbar(container, bg=BG_MID, troughcolor=BG_DARK,
                                     relief="flat", bd=0, width=8)
        self._vscroll.pack(side="right", fill="y")
        self._vcanvas = tk.Canvas(container, bg=BG_PANEL, bd=0,
                                  highlightthickness=0,
                                  yscrollcommand=self._vscroll.set)
        self._vcanvas.pack(side="left", fill="both", expand=True)
        self._vscroll.config(command=self._vcanvas.yview)

        self._vcanvas.bind("<Enter>", lambda e: self._vcanvas_bind_wheel())
        self._vcanvas.bind("<Leave>", lambda e: self._vcanvas_unbind_wheel())

        # Inner frame that holds all group+village frames
        self._vinner = tk.Frame(self._vcanvas, bg=BG_PANEL)
        self._vcanvas_window = self._vcanvas.create_window(
            (0, 0), window=self._vinner, anchor="nw")
        self._vinner.bind("<Configure>", self._on_vinner_configure)
        self._vcanvas.bind("<Configure>", self._on_vcanvas_configure)

        self._refresh_village_list()

        make_separator(right).pack(fill="x")
        styled_button(right, "↺ Refresh", command=self._refresh_village_list,
                      small=True).pack(fill="x", padx=8, pady=6)

    def _on_vinner_configure(self, _event):
        self._vcanvas.configure(scrollregion=self._vcanvas.bbox("all"))

    def _on_vcanvas_configure(self, event):
        self._vcanvas.itemconfig(self._vcanvas_window, width=event.width)

    # ── Groups data helpers ───────────────────────────────────────────────────

    def _all_groups(self) -> list:
        """Sorted list of unique group names present in villages ('' = ungrouped)."""
        groups = []
        for v in self.villages:
            g = v.get("group", "").strip()
            if g and g not in groups:
                groups.append(g)
        return groups

    def _villages_in_group(self, group_name: str) -> list:
        """Villages belonging to a group, sorted alphabetically."""
        members = [v for v in self.villages
                   if v.get("group", "").strip() == group_name]
        members.sort(key=lambda v: v["village_name"].lower())
        return members

    def _save_groups(self):
        """Persist group assignments back to CSV."""
        _rewrite_villages(self.server, self.account, self.villages)

    # ── Build the scrollable village list ─────────────────────────────────────

    def _refresh_village_list(self):
        self.villages = load_villages(self.server, self.account)

        # Destroy old card frames
        for w in self._vinner.winfo_children():
            w.destroy()
        self._village_cards = {}   # village_name -> card Frame

        if not self.villages:
            tk.Label(self._vinner, text="  (no villages yet)",
                     bg=BG_PANEL, fg=TEXT_MUTED, font=FONT_SMALL).pack(
                         anchor="w", padx=8, pady=8)
            return

        groups = self._all_groups()
        ungrouped = self._villages_in_group("")

        # Render ungrouped villages first (no header)
        for v in ungrouped:
            self._build_village_card(self._vinner, v)

        # Render each named group with a collapsible header
        for g in groups:
            self._build_group_section(self._vinner, g)

    def _build_group_section(self, parent, group_name: str):
        """Build a collapsible group block."""
        collapsed_key = f"_grp_collapsed_{group_name}"
        is_collapsed  = getattr(self, collapsed_key, False)

        # Group header row
        ghdr = tk.Frame(parent, bg=BG_MID, cursor="hand2")
        ghdr.pack(fill="x", pady=(6, 0))

        arrow = "▶" if is_collapsed else "▼"
        arrow_lbl = tk.Label(ghdr, text=arrow, font=FONT_SMALL,
                             bg=BG_MID, fg=ACCENT)
        arrow_lbl.pack(side="left", padx=(6, 2), pady=4)
        tk.Label(ghdr, text=group_name, font=("Consolas", 9, "bold"),
                 bg=BG_MID, fg=ACCENT).pack(side="left", pady=4)

        # Right-click: rename / delete group
        ctx_menu = tk.Menu(self, tearoff=0, bg=BG_PANEL, fg=TEXT_PRIMARY,
                           activebackground=BG_HOVER, activeforeground=ACCENT)
        ctx_menu.add_command(label="Rename group…",
                             command=lambda g=group_name: self._rename_group(g))
        ctx_menu.add_command(label="Delete group (ungroup villages)",
                             command=lambda g=group_name: self._delete_group(g))
        ghdr.bind("<Button-3>", lambda e, m=ctx_menu: m.tk_popup(e.x_root, e.y_root))
        arrow_lbl.bind("<Button-3>", lambda e, m=ctx_menu: m.tk_popup(e.x_root, e.y_root))

        # Toggle collapse on click
        def toggle(g=group_name, key=collapsed_key, ah=arrow_lbl):
            setattr(self, key, not getattr(self, key, False))
            self._refresh_village_list()
        ghdr.bind("<Button-1>", lambda e: toggle())
        arrow_lbl.bind("<Button-1>", lambda e: toggle())

        if is_collapsed:
            return

        # Village cards
        members = self._villages_in_group(group_name)
        for v in members:
            self._build_village_card(parent, v, group_name)

    def _build_village_card(self, parent, v: dict, group: str = ""):
        """Build one village card frame with drag handles."""
        vname = v["village_name"]
        is_selected = (self.selected_village == vname)
        bg = VILLAGE_SEL if is_selected else BG_PANEL

        card = tk.Frame(parent, bg=bg, cursor="hand2")
        card.pack(fill="x", pady=1)
        self._village_cards[vname] = card

        # Gather display data
        x = v.get("coord_x", "?"); y = v.get("coord_y", "?")
        w = v.get("res_wood", "?"); c_clay = v.get("res_clay", "?")
        iron = v.get("res_iron", "?"); cr = v.get("res_crop", "?")
        pop  = calculate_population(self.server, self.account, vname)
        cp   = calculate_culture_points(self.server, self.account, vname)
        prog = calculate_layout_progress(self.server, self.account, vname)
        pop_str = str(pop) if pop > 0 else "—"
        cp_str  = str(cp)  if cp  > 0 else "—"
        if prog is None:
            prog_str = "no layout"; prog_col = TEXT_MUTED
        else:
            prog_str = f"{int(prog*100)}%"
            prog_col = progress_color(int(prog * 100), 100)
        tmpl = v.get("applied_template", "").strip()

        # Text content
        content = tk.Frame(card, bg=bg)
        content.pack(side="left", fill="x", expand=True, padx=8)

        name_lbl = tk.Label(content, text=f"🏘 {vname}", font=FONT_BODY,
                            bg=bg, fg=ACCENT if is_selected else TEXT_PRIMARY,
                            anchor="w")
        name_lbl.pack(fill="x")

        coord_lbl = tk.Label(content,
                             text=f"  ({x}|{y})  👤{pop_str}  ★{cp_str}",
                             font=FONT_SMALL, bg=bg, fg=TEXT_SECONDARY, anchor="w")
        coord_lbl.pack(fill="x")

        res_lbl = tk.Label(content,
                           text=f"  🌲{w} 🧱{c_clay} ⚙{iron} 🌾{cr}  ▶{prog_str}",
                           font=FONT_SMALL, bg=bg, fg=prog_col, anchor="w")
        res_lbl.pack(fill="x")

        if tmpl:
            tk.Label(content, text=f"  📋 {tmpl}", font=FONT_SMALL,
                     bg=bg, fg=TEXT_MUTED, anchor="w").pack(fill="x")

        # Thin border separator
        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", side="bottom")

        # Right-click context menu: move to group
        ctx = tk.Menu(self, tearoff=0, bg=BG_PANEL, fg=TEXT_PRIMARY,
                      activebackground=BG_HOVER, activeforeground=ACCENT)
        ctx.add_command(label="Move to (ungrouped)",
                        command=lambda vn=vname: self._move_to_group(vn, ""))
        for g in self._all_groups():
            if g != group:
                ctx.add_command(label=f"Move to  {g}",
                                command=lambda vn=vname, gg=g: self._move_to_group(vn, gg))

        def show_ctx(e, m=ctx):
            m.tk_popup(e.x_root, e.y_root)

        for widget in (card, content, name_lbl, coord_lbl, res_lbl):
            widget.bind("<Button-1>", lambda e, vn=vname: self._on_card_click(vn))
            widget.bind("<Button-3>", show_ctx)

        self._bind_mousewheel(card)

    def _vcanvas_bind_wheel(self):
        self._vcanvas.bind_all("<MouseWheel>",
            lambda e: self._vcanvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        self._vcanvas.bind_all("<Button-4>",
            lambda e: self._vcanvas.yview_scroll(-1, "units"))
        self._vcanvas.bind_all("<Button-5>",
            lambda e: self._vcanvas.yview_scroll(1, "units"))

    def _vcanvas_unbind_wheel(self):
        self._vcanvas.unbind_all("<MouseWheel>")
        self._vcanvas.unbind_all("<Button-4>")
        self._vcanvas.unbind_all("<Button-5>")

    def _bind_mousewheel(self, widget):
        """Bind enter/leave on a card widget to activate right-panel scrolling."""
        widget.bind("<Enter>", lambda e: self._vcanvas_bind_wheel())
        widget.bind("<Leave>", lambda e: self._vcanvas_unbind_wheel())

    # ── Interaction handlers ──────────────────────────────────────────────────

    def _on_card_click(self, vname: str):
        self.selected_village = vname
        for v in self.villages:
            if v["village_name"] == vname:
                self._show_village_submenu(vname)
                self._show_village_layout(vname)
                break
        # Redraw to update selection highlight without full reload
        self._refresh_village_list()

    # ── Group management ─────────────────────────────────────────────────────

    def _move_to_group(self, vname: str, group_name: str):
        for v in self.villages:
            if v["village_name"] == vname:
                v["group"] = group_name
        self._save_groups()
        self._refresh_village_list()

    def _add_group_dialog(self):
        dlg = _NameDialog(self, "New Group", "Group name:")
        if dlg.result:
            # Just add a placeholder village if needed? No — groups appear
            # as soon as a village is assigned to them. For now, show a
            # confirmation and let user right-click a village to assign.
            messagebox.showinfo(
                "Group created",
                f'Group "{dlg.result}" is ready.\n\n'
                "Right-click any village card to move it into this group.",
                parent=self)
            # Pre-create the group by setting it on no villages yet — it will
            # appear once a village is moved into it. We store the name for
            # the Move-to menus by keeping a pending list.
            if not hasattr(self, "_pending_groups"):
                self._pending_groups = []
            if dlg.result not in self._pending_groups:
                self._pending_groups.append(dlg.result)

    def _all_groups(self) -> list:
        """All named groups from villages + any pending (not yet populated) groups."""
        seen = []
        for v in self.villages:
            g = v.get("group", "").strip()
            if g and g not in seen:
                seen.append(g)
        for g in getattr(self, "_pending_groups", []):
            if g not in seen:
                seen.append(g)
        return seen

    def _rename_group(self, old_name: str):
        dlg = _NameDialog(self, "Rename Group", "New name:", default=old_name)
        if not dlg.result or dlg.result == old_name:
            return
        for v in self.villages:
            if v.get("group", "").strip() == old_name:
                v["group"] = dlg.result
        # Update pending list
        if hasattr(self, "_pending_groups") and old_name in self._pending_groups:
            self._pending_groups[self._pending_groups.index(old_name)] = dlg.result
        self._save_groups()
        self._refresh_village_list()

    def _delete_group(self, group_name: str):
        if not messagebox.askyesno(
                "Delete group",
                f'Delete group "{group_name}"?\n\nVillages will become ungrouped.',
                parent=self):
            return
        for v in self.villages:
            if v.get("group", "").strip() == group_name:
                v["group"] = ""
        if hasattr(self, "_pending_groups") and group_name in self._pending_groups:
            self._pending_groups.remove(group_name)
        self._save_groups()
        self._refresh_village_list()

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