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

def troop_queues_file(server, account, village_name):
    return Path(str(_vkey(server, account, village_name)) + "_troop_queues.csv")

def load_troop_queues(server, account, village_name) -> dict:
    """Return {building_name: troop_name} for queued troops per building."""
    fpath = troop_queues_file(server, account, village_name)
    result = {}
    if not fpath.exists():
        return result
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            with open(fpath, newline="", encoding=enc) as f:
                for row in csv.DictReader(f):
                    b = row.get("building","").strip()
                    t = row.get("troop","").strip()
                    if b:
                        result[b] = t
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    return result

def save_troop_queues(server, account, village_name, queues: dict):
    fpath = troop_queues_file(server, account, village_name)
    fpath.parent.mkdir(parents=True, exist_ok=True)
    with open(fpath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["building", "troop"])
        w.writeheader()
        for b, t in queues.items():
            w.writerow({"building": b, "troop": t})

def sent_troops_file(server, account, village_name):
    return Path(str(_vkey(server, account, village_name)) + "_sent_troops.csv")

def load_sent_troops(server, account, village_name) -> list:
    """Return [{target_village, troop_name: count, ...}] — one row per destination."""
    fpath = sent_troops_file(server, account, village_name)
    if not fpath.exists():
        return []
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            with open(fpath, newline="", encoding=enc) as f:
                return list(csv.DictReader(f))
        except (UnicodeDecodeError, UnicodeError):
            continue
    return []

def save_sent_troops(server, account, village_name, rows: list, troop_names: list):
    """rows: [{target_village: str, troop_name: count}]"""
    fpath = sent_troops_file(server, account, village_name)
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["target_village"] + troop_names
    with open(fpath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)

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
        # If troops are trained but native_in was never set, assume all at home
        for t in troop_names:
            if data["trained"][t] > 0 and data["native_in"][t] == 0 and data["native_out"][t] == 0:
                data["native_in"][t] = data["trained"][t]
    else:
        # No file yet: default assumption is all troops are at home
        # native_in = trained (= 0 for new villages), native_out = 0
        for t in troop_names:
            data["native_in"][t] = data["trained"][t]
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

# Which buildings produce which troop categories (applies to all tribes)
# Troops are looked up per-tribe dynamically; this maps building -> troop index slice
PRODUCTION_BUILDINGS = ["Barracks", "Great Barracks", "Stable", "Great Stable", "Workshop"]

# Troop category by troop index within a tribe's list (0-based)
# Romans/Gauls/Teutons all follow: [0,1,2] = infantry, [3,4,5] = cavalry, [6,7] = siege
# This is consistent across all tribes
def troops_for_building(building: str, tribe: str) -> list:
    """Return the troop names producible in the given building for the given tribe."""
    all_troops = get_tribe_troops(tribe)
    # Exclude Settler (last), Senator/Chief/Chieftain (second-to-last)
    # Infantry = indices 0-2, Cavalry = 3-5, Siege = 6-7
    infantry = all_troops[0:3]
    cavalry  = all_troops[3:6]
    siege    = all_troops[6:8]
    mapping  = {
        "Barracks":       infantry,
        "Great Barracks": infantry,
        "Stable":         cavalry,
        "Great Stable":   cavalry,
        "Workshop":       siege,
    }
    return mapping.get(building, [])

def _parse_training_time(time_str: str) -> float:
    """Parse H:MM:SS or M:SS training time string into seconds."""
    parts = time_str.strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        pass
    return 3600.0

def get_troop_stats(tribe: str) -> dict:
    """Return {troop_name: {cost_wood, cost_clay, cost_iron, cost_crop, training_sec}} for tribe."""
    csv_path = DATA_DIR / "general" / "1x" / "troops.csv"
    result = {}
    if csv_path.exists():
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["tribe"].strip().lower() == tribe.strip().lower():
                    name = row["name"].strip()
                    result[name] = {
                        "wood":  int(row.get("cost_wood",  0) or 0),
                        "clay":  int(row.get("cost_clay",  0) or 0),
                        "iron":  int(row.get("cost_iron",  0) or 0),
                        "crop":  int(row.get("cost_crop",  0) or 0),
                        "training_sec": _parse_training_time(row.get("training_time_1x", "1:00:00")),
                    }
    return result

def calc_queue_hourly_cost(building: str, building_level: int,
                            troop_name: str, troop_stats: dict,
                            speed_mult: float = 1.0) -> dict:
    """
    Return {wood, clay, iron, crop} per hour for one building queuing one troop type.

    Training time reduction: 2% per building level for Barracks/Stable (not Workshop).
    Great Barracks / Great Stable: 3× cost, same training time reduction.
    Speed servers: training_time / speed_mult.
    """
    if troop_name not in troop_stats:
        return {"wood": 0, "clay": 0, "iron": 0, "crop": 0}

    stats = troop_stats[troop_name]
    base_sec = stats["training_sec"] / speed_mult

    # Training time reduction: 2% per level for Barracks/Stable/Great variants
    if building in ("Barracks", "Great Barracks", "Stable", "Great Stable"):
        reduced_sec = base_sec * (0.98 ** building_level)
    else:
        reduced_sec = base_sec   # Workshop: no reduction

    if reduced_sec <= 0:
        return {"wood": 0, "clay": 0, "iron": 0, "crop": 0}

    troops_per_hour = 3600.0 / reduced_sec
    cost_mult = 3.0 if building in ("Great Barracks", "Great Stable") else 1.0

    return {
        "wood": round(stats["wood"] * troops_per_hour * cost_mult),
        "clay": round(stats["clay"] * troops_per_hour * cost_mult),
        "iron": round(stats["iron"] * troops_per_hour * cost_mult),
        "crop": round(stats["crop"] * troops_per_hour * cost_mult),
    }


# ─── Resource layout per-village ─────────────────────────────────────────────
# 18 resource field slots per village.  Each slot has a type and level.
RESOURCE_TYPES  = ["Woodcutter", "Clay Pit", "Iron Mine", "Cropland"]

# Travian production per hour at each field level (levels 0–10, index = level)
# Source: standard 1x speed values
# Travian production per hour at each field level (levels 0–20, index = level)
# Levels 0–10 apply to all villages; levels 11–20 only in the capital.
FIELD_PRODUCTION = [0, 2, 5, 9, 15, 25, 40, 65, 105, 170, 280,
                    455, 740, 1200, 1950, 3170, 5145, 8350, 13555, 22010, 35745]
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

# ─── Parsed production data layer ────────────────────────────────────────────

PARSED_PROD_FIELDS = ["village_name", "wood", "clay", "iron", "crop"]

def parsed_production_file(server, account) -> Path:
    return account_dir(server, account) / "production.csv"

def load_parsed_production(server, account) -> dict:
    """Return {village_name: {wood, clay, iron, crop}} from production.csv."""
    fpath = parsed_production_file(server, account)
    result = {}
    if not fpath.exists():
        return result
    for enc in ("utf-8", "utf-8-sig", "cp1250", "latin-1"):
        try:
            with open(fpath, newline="", encoding=enc) as f:
                for row in csv.DictReader(f):
                    vname = row.get("village_name", "").strip()
                    if vname:
                        result[vname] = {
                            "wood": int(row.get("wood", 0) or 0),
                            "clay": int(row.get("clay", 0) or 0),
                            "iron": int(row.get("iron", 0) or 0),
                            "crop": int(row.get("crop", 0) or 0),
                        }
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    return result

def save_parsed_production(server, account, data: dict):
    """Write {village_name: {wood,clay,iron,crop}} to production.csv."""
    fpath = parsed_production_file(server, account)
    fpath.parent.mkdir(parents=True, exist_ok=True)
    with open(fpath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=PARSED_PROD_FIELDS)
        w.writeheader()
        for vname, prod in data.items():
            w.writerow({"village_name": vname,
                        "wood": prod.get("wood", 0),
                        "clay": prod.get("clay", 0),
                        "iron": prod.get("iron", 0),
                        "crop": prod.get("crop", 0)})

def parse_production_overview(raw_text: str) -> dict:
    """
    Parse raw paste from Travian Village Overview → Resources → Production.
    Format: tab-separated table.  Header row starts with "Village".
    Each data row: village_name TAB wood TAB clay TAB iron TAB crop
    Stops at a row whose first cell starts with "Sum".
    Returns {village_name: {wood, clay, iron, crop}}.
    """
    import re as _re2

    def _cl(s: str) -> str:
        """Strip unicode directional marks, separators, commas, and whitespace."""
        return _re2.sub(
            r'[\u200e\u200f\u202a-\u202e\u2066-\u2069\xad\xa0,]', '', s
        ).strip()

    lines = raw_text.splitlines()

    # Find the "Village" header row — it starts with "Village" and has tabs
    header_idx = None
    for i, ln in enumerate(lines):
        first = _cl(ln.split('\t')[0]) if '\t' in ln else _cl(ln)
        if first.lower() == 'village':
            header_idx = i
            break

    if header_idx is None:
        return {}

    result = {}
    for ln in lines[header_idx + 1:]:
        parts = [_cl(p) for p in ln.split('\t')]
        if not parts or not parts[0]:
            continue
        name = parts[0]
        if name.lower().startswith('sum'):
            break
        # Need at least 4 numeric columns after the name
        nums = []
        for p in parts[1:]:
            if p:
                try:
                    nums.append(int(p))
                except ValueError:
                    pass
        if len(nums) >= 4:
            result[name] = {
                "wood": nums[0], "clay": nums[1],
                "iron": nums[2], "crop": nums[3],
            }

    return result


# ─── Trade route data layer ───────────────────────────────────────────────────

TRADE_ROUTE_FIELDS = [
    "route_id", "target", "wood", "clay", "iron", "crop",
    "merchants", "frequency_min", "departure_time",
    "travel_minutes", "active",
]

def trade_routes_file(server, account, village_name) -> Path:
    return Path(str(_vkey(server, account, village_name)) + "_traderoutes.csv")

def load_trade_routes(server, account, village_name) -> list:
    fpath = trade_routes_file(server, account, village_name)
    if not fpath.exists():
        return []
    for enc in ("utf-8", "utf-8-sig", "cp1250", "latin-1"):
        try:
            with open(fpath, newline="", encoding=enc) as f:
                return list(csv.DictReader(f))
        except (UnicodeDecodeError, UnicodeError):
            continue
    return []

def save_trade_routes(server, account, village_name, routes: list):
    fpath = trade_routes_file(server, account, village_name)
    fpath.parent.mkdir(parents=True, exist_ok=True)
    with open(fpath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TRADE_ROUTE_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in routes:
            row = {k: r.get(k, "") for k in TRADE_ROUTE_FIELDS}
            w.writerow(row)

def _next_route_id(routes: list) -> str:
    if not routes:
        return "1"
    try:
        return str(max(int(r.get("route_id", 0)) for r in routes) + 1)
    except ValueError:
        return str(len(routes) + 1)

def get_merchant_stats(tribe: str, speed_mult: str = "1x",
                       commerce_level: int = 0) -> dict:
    """Return {speed, carry} for tribe's merchant.
    Speed adjusted for server speed; carry boosted by Commerce alliance bonus."""
    csv_path = DATA_DIR / "general" / "1x" / "merchants.csv"
    try:
        mult = float(speed_mult.replace("x", ""))
    except ValueError:
        mult = 1.0
    base_carry = 500
    base_speed = 16.0
    if csv_path.exists():
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["tribe"].strip().lower() == tribe.strip().lower():
                    base_speed = float(row["speed"])
                    base_carry = int(row["carry_capacity"])
                    break
    # Commerce bonus: +10% per level (levels 0-5)
    commerce_pct = max(0, min(5, commerce_level)) * 10
    carry = round(base_carry * (1 + commerce_pct / 100))
    return {
        "speed": base_speed * mult,
        "carry": carry,
    }

def travel_minutes_for_distance(dist: float, tribe: str, speed_mult: str = "1x") -> float:
    """Minutes for merchant to travel given distance in Travian field units."""
    stats = get_merchant_stats(tribe, speed_mult)
    if stats["speed"] <= 0:
        return 0.0
    # Travian: 1 field/hr at speed 1. travel_time_hr = dist / speed_fields_per_hr
    # speed is in fields/hr
    return (dist / stats["speed"]) * 60.0

def parse_trade_routes(raw_text: str) -> list:
    """
    Parse raw paste from Travian's Trade Routes page.
    Returns list of dicts matching TRADE_ROUTE_FIELDS (without route_id).
    Extracts data between "Create new trade route" and "Add route to village".
    """
    import re as _re2

    def _cl(s):
        return _re2.sub(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069\xad\xa0,]', '', s).strip()

    lines = [_cl(ln) for ln in raw_text.splitlines()]
    lines = [ln for ln in lines if ln]

    # Find bounds
    start = end = None
    for i, ln in enumerate(lines):
        if ln.lower().startswith("create new trade route"):
            start = i + 1
        if ln.lower().startswith("add route to village") and start is not None:
            end = i
            break
    if start is None or end is None:
        return []

    block = lines[start:end]

    routes = []
    i = 0
    while i < len(block):
        ln = block[i]

        # "To: X" starts a route
        m = _re2.match(r'^To:\s*(.+)$', ln, _re2.IGNORECASE)
        if m:
            target = m.group(1).strip()
            route  = {"target": target, "wood": "0", "clay": "0",
                      "iron": "0", "crop": "0", "merchants": "1",
                      "frequency_min": "60", "departure_time": "",
                      "travel_minutes": "0", "active": "1"}

            # Travel time on next line: "Travel time: H:MM:SSh"
            if i + 1 < len(block):
                tm = _re2.match(r'Travel time:\s*(\d+):(\d+):(\d+)', block[i + 1], _re2.IGNORECASE)
                if tm:
                    mins = int(tm.group(1)) * 60 + int(tm.group(2)) + round(int(tm.group(3)) / 60)
                    route["travel_minutes"] = str(mins)
                    i += 1

            # Scan following lines for resources, time, merchant count
            j = i + 1
            res_found = []
            while j < len(block) and j < i + 10:
                candidate = block[j]
                # pure integer → resource value
                if _re2.fullmatch(r'\d+', candidate):
                    res_found.append(candidate)
                # HH:MM → departure time
                elif _re2.fullmatch(r'\d{1,2}:\d{2}', candidate):
                    route["departure_time"] = candidate
                j += 1

            # First 4 integers are wood, clay, iron, crop
            res_keys = ["wood", "clay", "iron", "crop"]
            for ki, val in enumerate(res_found[:4]):
                route[res_keys[ki]] = val
            # 5th integer (if present) is merchant count
            if len(res_found) >= 5:
                route["merchants"] = res_found[4]

            routes.append(route)
            i = j
        else:
            i += 1

    return routes


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
            # Build a case-insensitive lookup: lower_name -> canonical_name
            ci_lookup = {t.lower(): t for t in valid_cols}
            if any(c.lower() in ci_lookup for c in cols):
                header_idx = i
                # troop_columns: list of (col_index_in_parts, canonical_name)
                # We keep every column that case-insensitively matches a known troop,
                # excluding "Hero" which is not a trainable troop unit.
                troop_columns = [
                    (ci + 1, ci_lookup[c.lower()])   # ci+1 because parts[0] is village name
                    for ci, c in enumerate(cols)
                    if c.lower() in ci_lookup and ci_lookup[c.lower()] != "Hero"
                ]
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
        # Village names include the number prefix, e.g. "19. Vigántpetend"
        vname = name_raw
        if not vname:
            continue
        counts = {}
        for part_idx, canonical in troop_columns:
            raw_val = parts[part_idx] if part_idx < len(parts) else "0"
            # Remove thousand separators (commas or non-breaking thin spaces)
            raw_val = _re.sub(r'[,\u202f\u00a0]', '', raw_val)
            try:
                counts[canonical] = int(raw_val)
            except ValueError:
                counts[canonical] = 0
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
            prev = _clean(lines[i - 1])
            # Village names now include the number prefix (e.g. "19. Vigántpetend")
            if prev in village_troops:
                village_coords[prev] = (coord_m.group(1), coord_m.group(2))
                if current_group:
                    village_groups[prev] = current_group
            i += 1
            continue

        # Check if this looks like a group header
        lln = ln.lower()
        is_skip = any(lln.startswith(s) for s in skip_prefixes)
        has_number_prefix = bool(_re.match(r'^\d+\.', ln))
        is_known_village = ln in village_troops

        if (not is_skip and not has_number_prefix and not is_known_village
                and len(ln) > 2 and len(ln) < 60
                and not coord_pat.search(ln)):
            # Candidate group header — accept if next non-blank is a village line
            for j in range(i + 1, min(i + 4, len(lines))):
                nxt = lines[j]
                if _re.match(r'^\d+\.', nxt) or nxt in village_troops:
                    current_group = ln
                    break
        i += 1

    return {
        "troop_columns":   [canonical for _, canonical in troop_columns],
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
                  "applied_template", "group", "is_capital"]
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

# ─── Alliance data layer ───────────────────────────────────────────────────────

ALLIANCE_BONUS_TYPES = ["Recruitment", "Philosophy", "Metallurgy", "Commerce"]

# ─── Village roles / boolean flags ───────────────────────────────────────────

def village_roles_file(server, account) -> Path:
    return account_dir(server, account) / "village_roles.csv"

def load_village_roles(server, account) -> dict:
    """Return {village_name: {flag: "1"/"0"}} from village_roles.csv."""
    fpath = village_roles_file(server, account)
    if not fpath.exists():
        return {}
    for enc in ("utf-8", "utf-8-sig", "cp1250", "latin-1"):
        try:
            with open(fpath, newline="", encoding=enc) as f:
                result = {}
                for row in csv.DictReader(f):
                    vname = row.pop("village_name", "")
                    if vname:
                        result[vname] = dict(row)
                return result
        except (UnicodeDecodeError, UnicodeError):
            continue
    return {}

def save_village_roles(server, account, roles: dict):
    """Write {village_name: {flag: "1"/"0"}} to village_roles.csv.
    Derives fieldnames from all flags seen across all villages."""
    if not roles:
        return
    all_flags = []
    seen = set()
    for flags in roles.values():
        for k in flags:
            if k not in seen:
                all_flags.append(k)
                seen.add(k)
    fpath = village_roles_file(server, account)
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["village_name"] + all_flags
    with open(fpath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for vname, flags in roles.items():
            row = {"village_name": vname}
            row.update({k: flags.get(k, "0") for k in all_flags})
            w.writerow(row)


def alliance_file(server, account) -> Path:
    return account_dir(server, account) / "alliance.csv"

def known_villages_dir(server, account) -> Path:
    return account_dir(server, account) / "Known_Villages"

def known_villages_file(server, account) -> Path:
    return known_villages_dir(server, account) / "known_villages.csv"

def known_village_types_file(server, account) -> Path:
    return known_villages_dir(server, account) / "types.csv"

ALLIANCE_FIELDS       = ["key", "value"]
KNOWN_VILLAGE_FIELDS  = ["village_id", "name", "coord_x", "coord_y", "vtype"]
KNOWN_TYPE_FIELDS     = ["vtype"]

def load_alliance_info(server, account) -> dict:
    """Return dict with alliance_name and bonus levels (Recruitment→int, etc.)."""
    fpath = alliance_file(server, account)
    result = {"alliance_name": ""}
    for bt in ALLIANCE_BONUS_TYPES:
        result[bt] = 0
    if not fpath.exists():
        return result
    try:
        with open(fpath, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                k, v = row.get("key", ""), row.get("value", "")
                if k == "alliance_name":
                    result["alliance_name"] = v
                elif k in ALLIANCE_BONUS_TYPES:
                    try:
                        result[k] = int(v)
                    except ValueError:
                        result[k] = 0
    except Exception:
        pass
    return result

def save_alliance_info(server, account, info: dict):
    fpath = alliance_file(server, account)
    fpath.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"key": "alliance_name", "value": info.get("alliance_name", "")}]
    for bt in ALLIANCE_BONUS_TYPES:
        rows.append({"key": bt, "value": str(info.get(bt, 0))})
    with open(fpath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ALLIANCE_FIELDS)
        w.writeheader()
        w.writerows(rows)

def load_alliance_bonus_table() -> dict:
    """Return {bonus_type: {level(int): {value, description}}} from general CSV."""
    csv_path = DATA_DIR / "general" / "1x" / "alliance_bonuses.csv"
    result = {bt: {} for bt in ALLIANCE_BONUS_TYPES}
    if not csv_path.exists():
        return result
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            bt  = row["bonus_type"].strip()
            lvl = int(row["level"])
            if bt in result:
                result[bt][lvl] = {
                    "value":       row["value"],
                    "description": row["description"],
                }
    return result

def load_known_village_types(server, account) -> list:
    fpath = known_village_types_file(server, account)
    if not fpath.exists():
        return []
    try:
        with open(fpath, newline="", encoding="utf-8") as f:
            return [row["vtype"] for row in csv.DictReader(f) if row.get("vtype")]
    except Exception:
        return []

def save_known_village_types(server, account, types: list):
    fpath = known_village_types_file(server, account)
    fpath.parent.mkdir(parents=True, exist_ok=True)
    with open(fpath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=KNOWN_TYPE_FIELDS)
        w.writeheader()
        for t in types:
            w.writerow({"vtype": t})

def load_known_villages(server, account) -> list:
    fpath = known_villages_file(server, account)
    if not fpath.exists():
        return []
    try:
        with open(fpath, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []

def save_known_villages(server, account, villages: list):
    fpath = known_villages_file(server, account)
    fpath.parent.mkdir(parents=True, exist_ok=True)
    with open(fpath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=KNOWN_VILLAGE_FIELDS, extrasaction="ignore")
        w.writeheader()
        for v in villages:
            row = {k: v.get(k, "") for k in KNOWN_VILLAGE_FIELDS}
            w.writerow(row)

def _next_village_id(villages: list) -> str:
    if not villages:
        return "1"
    try:
        return str(max(int(v.get("village_id", 0)) for v in villages) + 1)
    except ValueError:
        return str(len(villages) + 1)

def ensure_data_dir():
    DATA_DIR.mkdir(exist_ok=True)
    if not ACCOUNTS_FILE.exists():
        with open(ACCOUNTS_FILE, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=ACCOUNT_FIELDS).writeheader()

def load_accounts():
    ensure_data_dir()
    for enc in ("utf-8", "utf-8-sig", "cp1250", "latin-1"):
        try:
            with open(ACCOUNTS_FILE, newline="", encoding=enc) as f:
                return list(csv.DictReader(f))
        except (UnicodeDecodeError, UnicodeError):
            continue
    return []

def _rewrite_accounts(accounts):
    with open(ACCOUNTS_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ACCOUNT_FIELDS, extrasaction="ignore")
        w.writeheader()
        for a in accounts:
            # Ensure all required fields exist with defaults
            row = {
                "server":  a.get("server", ""),
                "account": a.get("account", ""),
                "tribe":   a.get("tribe", ""),
                "status":  a.get("status", "active"),
                "speed":   a.get("speed", "1x"),
            }
            w.writerow(row)

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
    matched = False
    for a in accounts:
        if account_key(a.get("server", ""), a.get("account", "")) == key:
            a["status"] = new_status
            matched = True
    if matched:
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

def set_capital(server, account, village_name: str):
    """Mark village_name as capital; clear is_capital on all others."""
    villages = load_villages(server, account)
    for v in villages:
        v["is_capital"] = "1" if v["village_name"] == village_name else ""
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
        current = (a.get("status") or "active").strip().lower()
        new = "archived" if current == "active" else "active"
        update_account_status(a["server"], a["account"], new)
        # Re-select same account after refresh
        key = account_key(a["server"], a["account"])
        self._refresh_accounts()
        for i, acc in enumerate(self._accounts):
            if account_key(acc.get("server",""), acc.get("account","")) == key:
                self.account_list.selection_set(i)
                self.account_list.see(i)
                break

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
    ("native_out", "Native sent out",     BG_PANEL, TEXT_PRIMARY),
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
        self._vars            = {}
        self._net_labels      = {}
        self._native_out_lbls = {}

        self._load_and_build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _load_and_build(self):
        for w in self.winfo_children():
            w.destroy()
        self._vars.clear()
        self._net_labels.clear()
        self._native_out_lbls.clear()

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
            styled_button(hdr, "📥  Import Sent Troops",
                          command=self._open_import, small=True
                          ).pack(side="left", padx=(8, 0))
            styled_button(hdr, "📥  Import Support Troops",
                          command=self._open_support_import, small=True
                          ).pack(side="left", padx=(4, 0))

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
                var = tk.StringVar(value=str(data[rk].get(tname, 0)))
                self._vars[(rk, tname)] = var
                ent = styled_entry(tbl, var, width=7)
                ent.config(state=state, justify="center",
                           disabledbackground=bg, disabledforeground=TEXT_MUTED)
                ent.grid(row=gr, column=ci + 1, sticky="nsew", padx=(0,1), pady=(0,1))
                var.trace_add("write", lambda *_, t=tname, k=rk: self._update_derived(t, k))

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
            self._update_derived(tname, None)

        # ── Sent troops destination table (always shown) ──────────────────────
        sent = load_sent_troops(self.server, self.account, self.village_name)
        sent = [r for r in sent if any(
            int(r.get(t, 0) or 0) for t in self._troop_names)]

        def _troop_subtable(parent, title, first_col_label, rows, unknown_counts):
            """Render a troop breakdown sub-table with an Unknown row."""
            make_separator(parent).pack(fill="x", pady=(16, 6))
            tk.Label(parent, text=title, font=("Consolas", 10, "bold"),
                     bg=BG_DARK, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, 6))

            tbl2 = tk.Frame(parent, bg=BG_DARK)
            tbl2.pack(fill="x")
            tbl2.columnconfigure(0, minsize=180)
            for c in range(1, n_troops + 1):
                tbl2.columnconfigure(c, minsize=90, uniform=f"sub{title[:4]}")

            # Header
            tk.Label(tbl2, text=first_col_label, font=("Consolas", 9, "bold"),
                     bg=BG_MID, fg=TEXT_MUTED, anchor="w", padx=6, pady=3
                     ).grid(row=0, column=0, sticky="nsew", padx=(0,1), pady=(0,1))
            for ci, tname in enumerate(self._troop_names):
                disp = tname if len(tname) <= 12 else tname[:11] + "…"
                lbl = tk.Label(tbl2, text=disp, font=("Consolas", 9, "bold"),
                               bg=BG_MID, fg=ACCENT, anchor="center", padx=4, pady=3)
                lbl.grid(row=0, column=ci + 1, sticky="nsew", padx=(0,1), pady=(0,1))
                lbl.bind("<Enter>", lambda e, w=lbl, full=tname: w.config(text=full))
                lbl.bind("<Leave>", lambda e, w=lbl, d=disp: w.config(text=d))
            tk.Frame(tbl2, bg=BORDER, height=1).grid(
                row=1, column=0, columnspan=n_troops + 1, sticky="ew", pady=(0,1))

            for i, row in enumerate(rows):
                r  = i + 2
                bg = BG_MID if i % 2 == 0 else BG_PANEL
                vname = row.get("_label", row.get("target_village",
                         row.get("source_village", "—")))
                tk.Label(tbl2, text=vname,
                         font=FONT_SMALL, bg=bg, fg=TEXT_PRIMARY,
                         anchor="w", padx=8, pady=3
                         ).grid(row=r, column=0, sticky="nsew", padx=(0,1), pady=(0,1))
                for ci, tname in enumerate(self._troop_names):
                    val = int(row.get(tname, 0) or 0)
                    tk.Label(tbl2, text=str(val) if val else "—",
                             font=FONT_SMALL, bg=bg,
                             fg=TEXT_PRIMARY if val else TEXT_MUTED,
                             anchor="center", pady=3
                             ).grid(row=r, column=ci + 1, sticky="nsew",
                                    padx=(0,1), pady=(0,1))

            # Unknown row
            n     = len(rows)
            sep_r = n + 2
            unk_r = n + 3
            unk_bg = BG_MID if n % 2 == 0 else BG_PANEL
            tk.Frame(tbl2, bg=ACCENT_DIM, height=1).grid(
                row=sep_r, column=0, columnspan=n_troops + 1,
                sticky="ew", pady=(2, 1))
            tk.Label(tbl2, text="Unknown", font=("Consolas", 9, "bold"),
                     bg=unk_bg, fg=TEXT_MUTED, anchor="w", padx=8, pady=3
                     ).grid(row=unk_r, column=0, sticky="nsew", padx=(0,1), pady=(0,1))
            for ci, tname in enumerate(self._troop_names):
                unknown = unknown_counts.get(tname, 0)
                fg = COL_RED if unknown < 0 else TEXT_PRIMARY if unknown else TEXT_MUTED
                tk.Label(tbl2, text=f"{unknown:+d}" if unknown else "0",
                         font=FONT_SMALL, bg=unk_bg, fg=fg,
                         anchor="center", pady=3
                         ).grid(row=unk_r, column=ci + 1, sticky="nsew",
                                padx=(0,1), pady=(0,1))

        # Sent-out table — always shown
        sent_unknown = {
            t: self._get_int("native_out", t) -
               sum(int(r.get(t, 0) or 0) for r in sent)
            for t in self._troop_names
        }
        _troop_subtable(inner, "Troops sent to other villages",
                        "Target village", sent, sent_unknown)

        # ── Incoming troops table ──────────────────────────────────────────────
        # Collect per-source data from every other village's _sent_troops.csv
        # where target_village == this village
        incoming_rows = []
        for v in load_villages(self.server, self.account):
            src_name = v["village_name"]
            if src_name == self.village_name:
                continue
            for row in load_sent_troops(self.server, self.account, src_name):
                if row.get("target_village", "") != self.village_name:
                    continue
                if not any(int(row.get(t, 0) or 0) for t in self._troop_names):
                    continue
                entry = {"_label": src_name}
                for t in self._troop_names:
                    entry[t] = int(row.get(t, 0) or 0)
                incoming_rows.append(entry)

        # Unknown = foreign_in - sum of known incoming
        inc_unknown = {
            t: self._get_int("foreign_in", t) -
               sum(r.get(t, 0) for r in incoming_rows)
            for t in self._troop_names
        }
        _troop_subtable(inner, "Troops from other villages",
                        "Source village", incoming_rows, inc_unknown)

    # ── Derived calculations ──────────────────────────────────────────────────

    def _get_int(self, rk, tname) -> int:
        try:
            return max(0, int(self._vars[(rk, tname)].get() or 0))
        except (ValueError, KeyError):
            return 0

    def _update_derived(self, tname: str, changed_key: str = None):
        """
        Maintain native_in + native_out == trained.
        When native_in changes → adjust native_out.
        When native_out changes → adjust native_in.
        Also recompute net = native_in + foreign_in.
        """
        if getattr(self, "_updating", False):
            return
        self._updating = True
        try:
            trained    = self._get_int("trained",    tname)
            native_in  = self._get_int("native_in",  tname)
            native_out = self._get_int("native_out", tname)

            if changed_key == "native_in":
                # Clamp native_in to trained, then derive native_out
                native_in  = min(native_in, trained)
                native_out = max(0, trained - native_in)
                if str(native_in) != self._vars.get(("native_in", tname), tk.StringVar()).get():
                    self._vars[("native_in", tname)].set(str(native_in))
                if str(native_out) != self._vars.get(("native_out", tname), tk.StringVar()).get():
                    self._vars[("native_out", tname)].set(str(native_out))
            elif changed_key == "native_out":
                native_out = min(native_out, trained)
                native_in  = max(0, trained - native_out)
                if str(native_out) != self._vars.get(("native_out", tname), tk.StringVar()).get():
                    self._vars[("native_out", tname)].set(str(native_out))
                if str(native_in) != self._vars.get(("native_in", tname), tk.StringVar()).get():
                    self._vars[("native_in", tname)].set(str(native_in))
            elif changed_key == "trained":
                # trained changed: keep native_in, recompute native_out
                native_in  = min(native_in, trained)
                native_out = max(0, trained - native_in)
                if str(native_in) != self._vars.get(("native_in", tname), tk.StringVar()).get():
                    self._vars[("native_in", tname)].set(str(native_in))
                if str(native_out) != self._vars.get(("native_out", tname), tk.StringVar()).get():
                    self._vars[("native_out", tname)].set(str(native_out))

            foreign_in = self._get_int("foreign_in", tname)
            net = self._get_int("native_in", tname) + foreign_in
            net_lbl = self._net_labels.get(tname)
            if net_lbl:
                net_lbl.config(text=str(net),
                               fg=COL_FULL_GREEN if net > 0 else _NET_ROW_FG)
        finally:
            self._updating = False

    # ── Save ─────────────────────────────────────────────────────────────────

    def _save(self):
        data = {rk: {} for rk in TROOP_ROWS}
        for (rk, tname), var in self._vars.items():
            try:
                data[rk][tname] = max(0, int(var.get() or 0))
            except ValueError:
                data[rk][tname] = 0
        save_troop_data(self.server, self.account,
                        self.village_name, self._troop_names, data)
        self._status_lbl.config(text="✓ Troops saved", fg=COL_FULL_GREEN)
        fade_label(self._status_lbl, after_ms=3500)

    def _open_import(self):
        dlg = ReinforcementsImportDialog(
            self, self.server, self.account, self.tribe,
            village_name=self.village_name,
            on_complete=self._load_and_build)
        self.wait_window(dlg)

    def _open_support_import(self):
        dlg = SupportTroopsImportDialog(
            self, self.server, self.account, self.tribe,
            village_name=self.village_name,
            on_complete=self._load_and_build)
        self.wait_window(dlg)


# ─── Village Resource Layout View ─────────────────────────────────────────────

_RES_ICONS = {"Woodcutter": "🌲", "Clay Pit": "🧱", "Iron Mine": "⚙", "Cropland": "🌾"}
_RES_LEVEL_MAX = {"Woodcutter": 10, "Clay Pit": 10, "Iron Mine": 10, "Cropland": 10}

class VillageResourceLayoutView(tk.Frame):
    """18 resource field slots, each with a type and level selector."""

    def __init__(self, master, server, account, village_name, is_archived=False,
                 on_save=None, is_capital=False):
        super().__init__(master, bg=BG_DARK)
        self.server       = server
        self.account      = account
        self.village_name = village_name
        self.is_archived  = is_archived
        self.is_capital   = is_capital
        self._on_save     = on_save
        self._type_vars   = {}
        self._level_vars  = {}
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
        cap_note = "  👑 Capital — fields can reach level 20" if self.is_capital else \
                   "  Fields max level 10  (set as capital to unlock lvl 11–20)"
        tk.Label(self, text=cap_note,
                 font=FONT_SMALL, bg=BG_DARK,
                 fg=ACCENT if self.is_capital else TEXT_MUTED).pack(anchor="w", padx=24, pady=(0, 10))

        outer, inner = scrollable_frame(self)
        outer.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        # Column headers
        col_hdr = tk.Frame(inner, bg=BG_PANEL)
        col_hdr.pack(fill="x", pady=(0, 2))
        for text, w in [("Slot", 5), ("Type", 16), ("Level", 8)]:
            tk.Label(col_hdr, text=text, font=("Consolas", 8, "bold"),
                     bg=BG_PANEL, fg=TEXT_MUTED, width=w, anchor="w").pack(side="left", padx=4)
        make_separator(inner, bg=BORDER).pack(fill="x", pady=(0, 4))

        state      = "disabled" if self.is_archived else "readonly"
        max_level  = 20 if self.is_capital else 10
        level_opts = [str(i) for i in range(0, max_level + 1)]

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
                    # Default: all trained troops are at home
                    for t in tribe_troops:
                        troop_data["native_in"][t]  = troop_data["trained"].get(t, 0)
                        troop_data["native_out"][t] = 0
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


# ─── Trade Routes View ────────────────────────────────────────────────────────

class TradeRoutesView(tk.Frame):
    """Village-level trade routes table with add/import buttons."""

    def __init__(self, master, server, account, village_name,
                 tribe, speed, is_archived=False):
        super().__init__(master, bg=BG_DARK)
        self.server       = server
        self.account      = account
        self.village_name = village_name
        self.tribe        = tribe
        self.speed        = speed
        self.is_archived  = is_archived
        alliance          = load_alliance_info(server, account)
        self.commerce_lvl = int(alliance.get("Commerce", 0))
        self._build()

    def _build(self):
        for w in self.winfo_children():
            w.destroy()

        routes = load_trade_routes(self.server, self.account, self.village_name)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG_DARK)
        hdr.pack(fill="x", padx=24, pady=(24, 0))
        tk.Label(hdr, text=f"{self.village_name}  —  Trade Routes",
                 font=FONT_TITLE, bg=BG_DARK, fg=TEXT_PRIMARY).pack(side="left")
        if not self.is_archived:
            styled_button(hdr, "📥  Import Routes",
                          command=self._open_import, small=True
                          ).pack(side="right", padx=(4, 0))
            styled_button(hdr, "➕  Add Manually",
                          command=self._open_add, small=True, accent=True
                          ).pack(side="right", padx=(4, 0))
            styled_button(hdr, "🔁  Recalc Merchants",
                          command=self._recalc_merchants, small=True
                          ).pack(side="right", padx=(4, 0))
            # Remove Selected wired up after sel_vars is built — stored as instance ref
            self._rm_btn_cmd = None
            rm_hdr_btn = styled_button(hdr, "🗑  Remove Selected",
                                       command=lambda: self._rm_btn_cmd and self._rm_btn_cmd(),
                                       small=True)
            rm_hdr_btn.pack(side="right", padx=(4, 0))
            self._rm_hdr_btn = rm_hdr_btn

        make_separator(self).pack(fill="x", padx=24, pady=10)

        if not routes:
            tk.Label(self, text="No trade routes yet. Use 'Add Manually' or 'Import Routes'.",
                     font=FONT_BODY, bg=BG_DARK, fg=TEXT_MUTED).pack(padx=24, anchor="w")
            return

        # ── Grid table ────────────────────────────────────────────────────────
        scroll_outer, inner = scrollable_frame(self)
        scroll_outer.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        # Selection state: route_id -> BooleanVar
        sel_vars = {}

        def _remove_selected():
            selected = {rid for rid, var in sel_vars.items() if var.get()}
            if not selected:
                return
            rts = load_trade_routes(self.server, self.account, self.village_name)
            rts = [rt for rt in rts if rt.get("route_id") not in selected]
            save_trade_routes(self.server, self.account, self.village_name, rts)
            self._build()

        # Wire the header button's command now that _remove_selected is defined
        if not self.is_archived:
            self._rm_btn_cmd = _remove_selected

        COLS = [
            (0,  "☐",           30, "center"),   # selection
            (1,  "Target",      180, "w"),
            (2,  "🌲 Wood",      70, "center"),
            (3,  "🧱 Clay",      70, "center"),
            (4,  "⚙ Iron",      70, "center"),
            (5,  "🌾 Crop",      70, "center"),
            (6,  "Merchants",    80, "center"),
            (7,  "Frequency",    80, "center"),
            (8,  "Departure",    80, "center"),
            (9,  "→ Arrive",     80, "center"),
            (10, "↩ Return",     80, "center"),
            (11, "Active",       60, "center"),
            (12, "",             40, "center"),   # edit button
        ]
        tbl = tk.Frame(inner, bg=BG_DARK)
        tbl.pack(fill="x")
        for ci, label, minw, anchor in COLS:
            tbl.columnconfigure(ci, minsize=minw)

        def gh(row, col, text, bg=BG_MID, fg=TEXT_MUTED, bold=True, anchor="center"):
            tk.Label(tbl, text=text, font=("Consolas", 9, "bold") if bold else FONT_SMALL,
                     bg=bg, fg=fg, anchor=anchor, padx=4, pady=3
                     ).grid(row=row, column=col, sticky="nsew", padx=(0,1), pady=(0,1))

        # Header row
        for ci, label, _, anchor in COLS:
            gh(0, ci, label, anchor=anchor)
        tk.Frame(tbl, bg=BORDER, height=1).grid(
            row=1, column=0, columnspan=len(COLS), sticky="ew", pady=(0,1))

        RES_COLS = {"🌲 Wood": ("#7daa6f","wood"), "🧱 Clay": ("#b87c4c","clay"),
                    "⚙ Iron": ("#8aabcc","iron"), "🌾 Crop": ("#c8b84a","crop")}

        def _fmt_time(minutes_str):
            try:
                m = int(float(minutes_str))
                return f"{m//60}h {m%60:02d}m" if m >= 60 else f"{m}m"
            except (ValueError, TypeError):
                return "—"

        def _fmt_freq(freq_str):
            try:
                m = int(float(freq_str))
                return f"{m//60}h" if m % 60 == 0 else f"{m}m"
            except (ValueError, TypeError):
                return "—"

        for i, route in enumerate(routes):
            r   = i + 2
            bg  = BG_MID if i % 2 == 0 else BG_PANEL
            rid = route.get("route_id", str(i))

            def gl(row, col, text, fg=TEXT_PRIMARY, bold=False, anchor="center"):
                tk.Label(tbl, text=text, font=("Consolas",9,"bold") if bold else FONT_SMALL,
                         bg=bg, fg=fg, anchor=anchor, padx=4, pady=3
                         ).grid(row=row, column=col, sticky="nsew", padx=(0,1), pady=(0,1))

            # Selection checkbox
            sel_var = tk.BooleanVar(value=False)
            sel_vars[rid] = sel_var
            sel_cb = tk.Checkbutton(tbl, variable=sel_var,
                                    bg=bg, activebackground=bg,
                                    selectcolor=BG_HOVER,
                                    fg=TEXT_MUTED, activeforeground=TEXT_MUTED,
                                    relief="flat", bd=0)
            if self.is_archived:
                sel_cb.config(state="disabled")
            sel_cb.grid(row=r, column=0, sticky="nsew", padx=(0,1), pady=(0,1))

            gl(r, 1,  route.get("target","—"), anchor="w")
            # Resources
            for ci, (label, (col, key)) in enumerate(RES_COLS.items(), start=2):
                val = route.get(key, "0")
                try:   ival = int(val)
                except: ival = 0
                gl(r, ci, f"{ival:,}" if ival else "—",
                   fg=col if ival else TEXT_MUTED)
            gl(r, 6, route.get("merchants","1"))
            gl(r, 7, _fmt_freq(route.get("frequency_min","60")))
            gl(r, 8, route.get("departure_time","—"))
            travel = route.get("travel_minutes","0")
            gl(r, 9,  _fmt_time(travel))
            try:    ret_min = str(int(float(travel)) * 2)
            except: ret_min = "0"
            gl(r, 10, _fmt_time(ret_min))

            # Active toggle — bright green tick
            is_active = route.get("active","1") not in ("0","false","False","")
            act_var = tk.BooleanVar(value=is_active)
            def _toggle(var=act_var, route_id=rid):
                rts = load_trade_routes(self.server, self.account, self.village_name)
                for rt in rts:
                    if rt.get("route_id") == route_id:
                        rt["active"] = "1" if var.get() else "0"
                save_trade_routes(self.server, self.account, self.village_name, rts)
            act_cb = tk.Checkbutton(tbl, variable=act_var, command=_toggle,
                                    bg=bg, activebackground=bg,
                                    fg=COL_FULL_GREEN, activeforeground=COL_FULL_GREEN,
                                    selectcolor=bg,          # bg behind tick = row colour
                                    relief="flat", bd=0)
            if self.is_archived:
                act_cb.config(state="disabled")
            act_cb.grid(row=r, column=11, sticky="nsew", padx=(0,1), pady=(0,1))

            # Edit button
            def _edit(route=route):
                dlg = TradeRouteFormDialog(
                    self, self.server, self.account, self.village_name,
                    self.tribe, self.speed, existing_route=route,
                    commerce_level=self.commerce_lvl)
                self.wait_window(dlg)
                self._build()
            edit_btn = tk.Button(tbl, text="✏", font=FONT_TINY,
                                 bg=bg, fg=TEXT_SECONDARY,
                                 activeforeground=ACCENT, activebackground=BG_HOVER,
                                 relief="flat", bd=0, cursor="hand2",
                                 command=_edit)
            if self.is_archived:
                edit_btn.config(state="disabled")
            edit_btn.grid(row=r, column=12, sticky="nsew", padx=(0,1), pady=(0,1))

    def _open_add(self):
        dlg = TradeRouteFormDialog(self, self.server, self.account,
                                   self.village_name, self.tribe, self.speed,
                                   commerce_level=self.commerce_lvl)
        self.wait_window(dlg)
        self._build()

    def _open_import(self):
        dlg = ImportTradeRoutesDialog(self, self.server, self.account, self.village_name)
        self.wait_window(dlg)
        self._build()

    def _recalc_merchants(self):
        """Recalculate merchant count for every route based on resources and carry capacity."""
        stats = get_merchant_stats(self.tribe, self.speed, self.commerce_lvl)
        carry = stats["carry"]
        routes = load_trade_routes(self.server, self.account, self.village_name)
        for rt in routes:
            total = 0
            for key in ("wood", "clay", "iron", "crop"):
                try:
                    total += max(0, int(rt.get(key, 0) or 0))
                except ValueError:
                    pass
            rt["merchants"] = str(max(1, -(-total // carry)))
        save_trade_routes(self.server, self.account, self.village_name, routes)
        self._build()


# ─── Trade Route Form Dialog (Add + Edit) ─────────────────────────────────────

_SEP = "────────────────────"   # visual separator in dropdown

class TradeRouteFormDialog(tk.Toplevel):
    """
    Shared dialog for adding and editing trade routes.
    Pass existing_route=dict to edit; omit (or None) to add new.
    """
    def __init__(self, master, server, account, village_name,
                 tribe, speed, existing_route=None, commerce_level=0):
        super().__init__(master)
        self.server         = server
        self.account        = account
        self.village_name   = village_name
        self.tribe          = tribe
        self.speed          = speed
        self.existing_route = existing_route
        self.commerce_level = commerce_level
        self.title("Edit Trade Route" if existing_route else "Add Trade Route")
        self.configure(bg=BG_DARK)
        self.geometry("460x500")
        self.grab_set()
        self._build()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _get_source_coords(self):
        """Return (x, y) ints for this village, or (None, None)."""
        for v in load_villages(self.server, self.account):
            if v["village_name"] == self.village_name:
                try:
                    return int(v["coord_x"]), int(v["coord_y"])
                except (ValueError, TypeError):
                    return None, None
        return None, None

    def _get_target_coords(self, target_name: str):
        """Return (x, y) ints for target from own or known villages."""
        for v in load_villages(self.server, self.account):
            if v["village_name"] == target_name:
                try:
                    return int(v["coord_x"]), int(v["coord_y"])
                except (ValueError, TypeError):
                    return None, None
        for v in load_known_villages(self.server, self.account):
            if v["name"] == target_name:
                try:
                    return int(v["coord_x"]), int(v["coord_y"])
                except (ValueError, TypeError):
                    return None, None
        return None, None

    @staticmethod
    def _travian_distance(x1, y1, x2, y2, map_size=401):
        """Travian wrapping distance (shortest path on torus)."""
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        dx = min(dx, map_size - dx)
        dy = min(dy, map_size - dy)
        return (dx**2 + dy**2) ** 0.5

    def _calc_travel(self, target_name: str) -> int:
        """Return travel minutes, or 0 if coords unavailable."""
        sx, sy = self._get_source_coords()
        tx, ty = self._get_target_coords(target_name)
        if None in (sx, sy, tx, ty):
            return 0
        dist = self._travian_distance(sx, sy, tx, ty)
        stats = get_merchant_stats(self.tribe, self.speed)
        if stats["speed"] <= 0:
            return 0
        return round((dist / stats["speed"]) * 60)

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self):
        ex  = self.existing_route or {}
        stats = get_merchant_stats(self.tribe, self.speed, self.commerce_level)
        carry = stats["carry"]

        pad = tk.Frame(self, bg=BG_DARK)
        pad.pack(fill="both", expand=True, padx=20, pady=16)

        tk.Label(pad,
                 text="Edit Trade Route" if self.existing_route else "Add Trade Route",
                 font=FONT_HEADING, bg=BG_DARK, fg=TEXT_PRIMARY
                 ).pack(anchor="w", pady=(0, 10))

        fields = {}

        def field_row(label, key, default="0", width=14):
            f = tk.Frame(pad, bg=BG_DARK)
            f.pack(fill="x", pady=3)
            tk.Label(f, text=label, width=18, font=FONT_SMALL,
                     bg=BG_DARK, fg=TEXT_SECONDARY, anchor="w").pack(side="left")
            var = tk.StringVar(value=str(ex.get(key, default)))
            styled_entry(f, var, width=width).pack(side="left")
            fields[key] = var
            return var

        # ── Target village dropdown ────────────────────────────────────────────
        own     = [v["village_name"] for v in load_villages(self.server, self.account)]
        known   = [v["name"] for v in load_known_villages(self.server, self.account)]
        options = own + ([_SEP] + known if known else [])

        cur_target = ex.get("target", "")
        tgt_var = tk.StringVar(value=cur_target if cur_target in options else
                               (own[0] if own else ""))

        tf = tk.Frame(pad, bg=BG_DARK)
        tf.pack(fill="x", pady=3)
        tk.Label(tf, text="Target village", width=18, font=FONT_SMALL,
                 bg=BG_DARK, fg=TEXT_SECONDARY, anchor="w").pack(side="left")
        tgt_cb = styled_combo(tf, tgt_var, options, width=22, state="readonly")
        tgt_cb.pack(side="left")

        # Travel time — auto-calculated, but still editable override
        travel_tf = tk.Frame(pad, bg=BG_DARK)
        travel_tf.pack(fill="x", pady=3)
        tk.Label(travel_tf, text="Travel time (min)", width=18, font=FONT_SMALL,
                 bg=BG_DARK, fg=TEXT_SECONDARY, anchor="w").pack(side="left")
        travel_var = tk.StringVar(value=ex.get("travel_minutes", "0"))
        travel_entry = styled_entry(travel_tf, travel_var, width=8)
        travel_entry.pack(side="left")
        travel_note = tk.Label(travel_tf, text="", font=FONT_SMALL,
                               bg=BG_DARK, fg=TEXT_MUTED)
        travel_note.pack(side="left", padx=(8, 0))

        def _on_target_change(*_):
            t = tgt_var.get()
            if t == _SEP:
                # Don't allow selecting the separator
                tgt_var.set(own[0] if own else "")
                return
            mins = self._calc_travel(t)
            travel_var.set(str(mins))
            if mins:
                travel_note.config(text=f"auto  ({mins}m)")
            else:
                travel_note.config(text="coords unknown")

        tgt_var.trace_add("write", _on_target_change)
        # Run once on open to populate travel time if adding new
        if not self.existing_route:
            _on_target_change()

        # Resources
        wood_var = field_row("🌲 Wood",  "wood",  default="0")
        clay_var = field_row("🧱 Clay",  "clay",  default="0")
        iron_var = field_row("⚙  Iron",  "iron",  default="0")
        crop_var = field_row("🌾 Crop",  "crop",  default="0")

        # Merchants — calculated
        mf = tk.Frame(pad, bg=BG_DARK)
        mf.pack(fill="x", pady=3)
        tk.Label(mf, text="Merchants", width=18, font=FONT_SMALL,
                 bg=BG_DARK, fg=TEXT_SECONDARY, anchor="w").pack(side="left")
        merch_lbl = tk.Label(mf, text="1", font=("Consolas", 9, "bold"),
                             bg=BG_DARK, fg=ACCENT)
        merch_lbl.pack(side="left")
        tk.Label(mf, text=f"  (carry {carry:,} each)",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(side="left")

        def _update_merchants(*_):
            total = sum(max(0, int(v.get() or 0))
                        for v in (wood_var, clay_var, iron_var, crop_var)
                        if v.get().lstrip("-").isdigit())
            merch_lbl.config(text=str(max(1, -(-total // carry))))

        for v in (wood_var, clay_var, iron_var, crop_var):
            v.trace_add("write", _update_merchants)
        _update_merchants()

        freq_var = field_row("Frequency (min)",   "frequency_min",  default="60")
        dep_var  = field_row("Departure (HH:MM)", "departure_time", default="00:00")

        # Active
        af = tk.Frame(pad, bg=BG_DARK)
        af.pack(fill="x", pady=3)
        tk.Label(af, text="Active", width=18, font=FONT_SMALL,
                 bg=BG_DARK, fg=TEXT_SECONDARY, anchor="w").pack(side="left")
        act_var = tk.BooleanVar(value=ex.get("active","1") not in ("0","false","False",""))
        tk.Checkbutton(af, variable=act_var, bg=BG_DARK, activebackground=BG_DARK,
                       selectcolor=BG_HOVER, fg=COL_FULL_GREEN,
                       activeforeground=COL_FULL_GREEN, relief="flat").pack(side="left")

        status = tk.Label(pad, text="", font=FONT_SMALL, bg=BG_DARK, fg=COL_RED)
        status.pack(anchor="w", pady=(4, 0))

        def _save():
            target = tgt_var.get().strip()
            if not target or target == _SEP:
                status.config(text="Please select a target village.")
                return
            total = sum(max(0, int(fields[k].get() or 0))
                        for k in ("wood","clay","iron","crop")
                        if fields[k].get().lstrip("-").isdigit())
            merchants = max(1, -(-total // carry))
            try:
                travel = int(travel_var.get() or 0)
            except ValueError:
                travel = 0

            new_rt = {
                "target":         target,
                "wood":           fields["wood"].get().strip(),
                "clay":           fields["clay"].get().strip(),
                "iron":           fields["iron"].get().strip(),
                "crop":           fields["crop"].get().strip(),
                "merchants":      str(merchants),
                "frequency_min":  fields["frequency_min"].get().strip(),
                "departure_time": fields["departure_time"].get().strip(),
                "travel_minutes": str(travel),
                "active":         "1" if act_var.get() else "0",
            }

            routes = load_trade_routes(self.server, self.account, self.village_name)
            if self.existing_route:
                rid = self.existing_route.get("route_id")
                for i, rt in enumerate(routes):
                    if rt.get("route_id") == rid:
                        new_rt["route_id"] = rid
                        routes[i] = new_rt
                        break
            else:
                new_rt["route_id"] = _next_route_id(routes)
                routes.append(new_rt)

            save_trade_routes(self.server, self.account, self.village_name, routes)
            self.destroy()

        br = tk.Frame(pad, bg=BG_DARK)
        br.pack(fill="x", pady=(10, 0))
        styled_button(br, "💾  Save", command=_save, accent=True).pack(side="left")
        styled_button(br, "Cancel", command=self.destroy, small=True).pack(side="left", padx=8)


# ─── Import Trade Routes Dialog ────────────────────────────────────────────────

class ImportTradeRoutesDialog(tk.Toplevel):
    def __init__(self, master, server, account, village_name):
        super().__init__(master)
        self.server       = server
        self.account      = account
        self.village_name = village_name
        self.title("Import Trade Routes")
        self.configure(bg=BG_DARK)
        self.geometry("700x520")
        self.grab_set()
        self._parsed = []
        self._build()

    def _build(self):
        pad = tk.Frame(self, bg=BG_DARK)
        pad.pack(fill="both", expand=True, padx=20, pady=16)

        tk.Label(pad, text="Import Trade Routes", font=FONT_HEADING,
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0,4))
        tk.Label(pad,
                 text="Paste the full Trade Routes page. Data between\n"
                      "'Create new trade route' and 'Add route to village' will be parsed.",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED,
                 justify="left").pack(anchor="w", pady=(0,8))

        txt_frame = tk.Frame(pad, bg=BORDER)
        txt_frame.pack(fill="both", expand=True)
        self._txt = tk.Text(txt_frame, bg=BG_MID, fg=TEXT_PRIMARY,
                            insertbackground=ACCENT, font=("Consolas", 9),
                            relief="flat", bd=6, wrap="none",
                            selectbackground=BG_HOVER)
        sb = tk.Scrollbar(txt_frame, command=self._txt.yview,
                          bg=BG_MID, troughcolor=BG_DARK, relief="flat", bd=0, width=8)
        self._txt.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._txt.pack(fill="both", expand=True)

        self._preview = tk.Label(pad, text="", font=FONT_SMALL,
                                 bg=BG_DARK, fg=COL_FULL_GREEN, justify="left")
        self._preview.pack(anchor="w", pady=(6,0))

        btn_row = tk.Frame(pad, bg=BG_DARK)
        btn_row.pack(fill="x", pady=(8,0))
        styled_button(btn_row, "🔍  Parse",  command=self._parse,  accent=True).pack(side="left")
        styled_button(btn_row, "✅  Import", command=self._import, small=True).pack(side="left", padx=6)
        self._status = tk.Label(btn_row, text="", font=FONT_SMALL,
                                bg=BG_DARK, fg=COL_FULL_GREEN)
        self._status.pack(side="left", padx=8)
        styled_button(btn_row, "Close", command=self.destroy, small=True).pack(side="right")

    def _parse(self):
        raw = self._txt.get("1.0", "end")
        self._parsed = parse_trade_routes(raw)
        if not self._parsed:
            self._preview.config(
                text="❌  No trade routes found. Make sure the paste includes\n"
                     "   'Create new trade route' and 'Add route to village'.",
                fg=COL_RED)
        else:
            lines = [f"✔  Found {len(self._parsed)} route(s):"]
            for rt in self._parsed:
                res = ", ".join(f"{k}:{rt[k]}" for k in ("wood","clay","iron","crop") if rt.get(k,"0") != "0")
                lines.append(f"  → {rt['target']}  travel:{rt['travel_minutes']}min  {res or 'no resources?'}  dep:{rt['departure_time']}")
            self._preview.config(text="\n".join(lines), fg=COL_FULL_GREEN)

    def _import(self):
        if not self._parsed:
            self._parse()
        if not self._parsed:
            return
        routes = load_trade_routes(self.server, self.account, self.village_name)
        for rt in self._parsed:
            rt["route_id"] = _next_route_id(routes)
            routes.append(rt)
        save_trade_routes(self.server, self.account, self.village_name, routes)
        self._status.config(text=f"✅  Imported {len(self._parsed)} route(s).", fg=COL_FULL_GREEN)
        self._parsed = []


# ─── Import Production Dialog ─────────────────────────────────────────────────

class ImportProductionDialog(tk.Toplevel):
    """Paste the Travian Village Overview → Resources → Production page."""

    def __init__(self, master, server, account, village_names: list):
        super().__init__(master)
        self.server        = server
        self.account       = account
        self.village_names = village_names
        self.title("Import Production Data")
        self.configure(bg=BG_DARK)
        self.geometry("700x520")
        self.grab_set()
        self._parsed = {}
        self._build()

    def _build(self):
        pad = tk.Frame(self, bg=BG_DARK)
        pad.pack(fill="both", expand=True, padx=20, pady=16)

        tk.Label(pad, text="Import Production Data", font=FONT_HEADING,
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, 4))
        tk.Label(pad,
                 text="Paste the full page from Village Overview → Resources → Production.\n"
                      "Village names in the paste must match your village names.",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED,
                 justify="left").pack(anchor="w", pady=(0, 8))

        txt_frame = tk.Frame(pad, bg=BORDER)
        txt_frame.pack(fill="both", expand=True)
        self._txt = tk.Text(txt_frame, bg=BG_MID, fg=TEXT_PRIMARY,
                            insertbackground=ACCENT, font=("Consolas", 9),
                            relief="flat", bd=6, wrap="none",
                            selectbackground=BG_HOVER)
        sb = tk.Scrollbar(txt_frame, command=self._txt.yview,
                          bg=BG_MID, troughcolor=BG_DARK, relief="flat", bd=0, width=8)
        self._txt.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._txt.pack(fill="both", expand=True)

        self._preview = tk.Label(pad, text="", font=FONT_SMALL,
                                 bg=BG_DARK, fg=COL_FULL_GREEN, justify="left",
                                 wraplength=640)
        self._preview.pack(anchor="w", pady=(6, 0))

        btn_row = tk.Frame(pad, bg=BG_DARK)
        btn_row.pack(fill="x", pady=(8, 0))
        styled_button(btn_row, "🔍  Parse",  command=self._parse,  accent=True).pack(side="left")
        styled_button(btn_row, "✅  Import", command=self._import, small=True).pack(side="left", padx=6)
        self._status = tk.Label(btn_row, text="", font=FONT_SMALL,
                                bg=BG_DARK, fg=COL_FULL_GREEN)
        self._status.pack(side="left", padx=8)
        styled_button(btn_row, "Close", command=self.destroy, small=True).pack(side="right")

    def _parse(self):
        raw = self._txt.get("1.0", "end")
        self._parsed = parse_production_overview(raw)
        if not self._parsed:
            self._preview.config(
                text="❌  No production data found. Make sure the paste includes the "
                     "production table with village names and numeric values.",
                fg=COL_RED)
            return

        lines = [f"✔  Found {len(self._parsed)} village(s):"]
        for vname, prod in self._parsed.items():
            lines.append(f"  {vname}:  🌲{prod['wood']:,}  🧱{prod['clay']:,}"
                         f"  ⚙{prod['iron']:,}  🌾{prod['crop']:,}")

        # Warn about unmatched names
        unmatched = [vn for vn in self._parsed if vn not in self.village_names]
        if unmatched:
            lines.append(f"⚠  {len(unmatched)} name(s) not in your village list: "
                         + ", ".join(unmatched))

        self._preview.config(text="\n".join(lines), fg=COL_FULL_GREEN)

    def _import(self):
        if not self._parsed:
            self._parse()
        if not self._parsed:
            return
        # Merge with existing (preserve villages not in this paste)
        existing = load_parsed_production(self.server, self.account)
        existing.update(self._parsed)
        save_parsed_production(self.server, self.account, existing)
        self._status.config(
            text=f"✅  Saved {len(self._parsed)} village(s) to production.csv",
            fg=COL_FULL_GREEN)


def parse_reinforcements(raw_text: str, tribe: str) -> list:
    """
    Parse Rally Point → Overview → Troops in other villages paste.

    The browser copies each table ROW as one line, cells separated by tabs.
    Structure per reinforcement block:
      ROW A: source_village TAB "Reinforcement for TARGET"
      ROW B: coords TAB troop_name TAB troop_name ...
      ROW C: "Troops" TAB count TAB count ...

    Returns list of {source_village, target_village, troops: {name: count}}.
    """
    import re as _re2

    def _cl(s):
        return _re2.sub(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069\xad\xa0,]', '', s).strip()

    tribe_troops = set(get_tribe_troops(tribe)) | {"Hero"}
    ci_lookup    = {t.lower(): t for t in tribe_troops}
    coord_pat    = _re2.compile(r'\(?\s*-?\d+\s*\|\s*[\u2212\-]?\d+\s*\)?')
    reinf_pat    = _re2.compile(r'^Reinforcement\s+for\s+(.+)$', _re2.IGNORECASE)

    # Do NOT filter empty lines — tab structure must be preserved per-row
    lines = raw_text.splitlines()

    results = []
    i = 0
    while i < len(lines):
        parts = [_cl(p) for p in lines[i].split('\t')]
        # Match row: source TAB "Reinforcement for TARGET"
        if len(parts) >= 2:
            m = reinf_pat.match(parts[1])
            if m:
                source = parts[0]
                target = m.group(1).strip()

                j = i + 1
                troop_names = []
                # Next row: coords TAB troop_name TAB ...
                if j < len(lines):
                    hdr = [_cl(p) for p in lines[j].split('\t')]
                    if coord_pat.search(hdr[0] if hdr else ""):
                        troop_names = [p for p in hdr[1:] if p and p.lower() != "hero"]
                        j += 1

                # Next row: "Troops" TAB count TAB ...
                counts = []
                if j < len(lines):
                    tr = [_cl(p) for p in lines[j].split('\t')]
                    if tr and tr[0].lower() == "troops":
                        for p in tr[1:]:
                            try:
                                counts.append(int(p))
                            except ValueError:
                                pass
                        j += 1

                troops = dict(zip(troop_names, counts))
                results.append({
                    "source_village": source,
                    "target_village": target,
                    "troops": troops,
                })
                i = j
                continue
        i += 1

    return results


# ─── Reinforcements Import Dialog ─────────────────────────────────────────────

class ReinforcementsImportDialog(tk.Toplevel):
    """
    Parse Rally Point → Overview → Troops in other villages.
    When village_name is given (opened from a village's Troops view):
      - only processes blocks where source == village_name
      - updates native_out on the source and foreign_in on targets
    """
    def __init__(self, master, server, account, tribe,
                 village_name=None, on_complete=None):
        super().__init__(master)
        self.server        = server
        self.account       = account
        self.tribe         = tribe
        self.village_name  = village_name   # if set, filter to this source only
        self._on_complete  = on_complete
        self.title("Import Sent Troops" if village_name else "Import Reinforcements")
        self.configure(bg=BG_DARK)
        self.geometry("720x580")
        self.grab_set()
        self._parsed = []
        self._build()

    def _build(self):
        pad = tk.Frame(self, bg=BG_DARK)
        pad.pack(fill="both", expand=True, padx=20, pady=16)

        title = "Import Sent Troops" if self.village_name else "Import Reinforcements"
        tk.Label(pad, text=title, font=FONT_HEADING,
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, 4))

        if self.village_name:
            desc = (f"Paste from Rally Point → Overview → Troops in other villages.\n"
                    f"Will import troops sent OUT from '{self.village_name}'.\n"
                    f"Updates 'Native sent out' here and 'Foreign in village' on targets.")
        else:
            desc = ("Paste from Rally Point → Overview → Troops in other villages.\n"
                    "Updates 'foreign troops in' on target villages and "
                    "'native troops out' on source villages.")
        tk.Label(pad, text=desc, font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED,
                 justify="left").pack(anchor="w", pady=(0, 8))

        txt_frame = tk.Frame(pad, bg=BORDER)
        txt_frame.pack(fill="both", expand=True)
        self._txt = tk.Text(txt_frame, bg=BG_MID, fg=TEXT_PRIMARY,
                            insertbackground=ACCENT, font=("Consolas", 9),
                            relief="flat", bd=6, wrap="none",
                            selectbackground=BG_HOVER)
        sb = tk.Scrollbar(txt_frame, command=self._txt.yview,
                          bg=BG_MID, troughcolor=BG_DARK, relief="flat", bd=0, width=8)
        self._txt.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._txt.pack(fill="both", expand=True)

        self._preview = tk.Label(pad, text="", font=("Consolas", 8),
                                 bg=BG_DARK, fg=COL_FULL_GREEN,
                                 justify="left", wraplength=660, anchor="w")
        self._preview.pack(fill="x", pady=(6, 0))

        btn_row = tk.Frame(pad, bg=BG_DARK)
        btn_row.pack(fill="x", pady=(8, 0))
        styled_button(btn_row, "🔍  Parse",  command=self._parse,  accent=True).pack(side="left")
        styled_button(btn_row, "✅  Import", command=self._import, small=True).pack(side="left", padx=6)
        self._status = tk.Label(btn_row, text="", font=FONT_SMALL,
                                bg=BG_DARK, fg=COL_FULL_GREEN)
        self._status.pack(side="left", padx=8)
        styled_button(btn_row, "Close", command=self.destroy, small=True).pack(side="right")

    def _parse(self):
        raw = self._txt.get("1.0", "end")
        all_parsed = parse_reinforcements(raw, self.tribe)

        # Filter to source village if specified
        if self.village_name:
            self._parsed = [r for r in all_parsed
                            if r["source_village"] == self.village_name]
            filtered_note = f" (filtered to source='{self.village_name}')" if self._parsed != all_parsed else ""
        else:
            self._parsed = all_parsed
            filtered_note = ""

        if not self._parsed:
            # Show debug info to help diagnose
            import re as _re
            def _cl(s):
                return _re.sub(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069\xad\xa0,]', '', s).strip()
            lines = [_cl(ln) for ln in raw.splitlines()]
            lines = [ln for ln in lines if ln]
            reinf_lines = [f"  [{i}] {repr(ln)}" for i, ln in enumerate(lines[:30])]
            debug = ("❌  No reinforcements found.\n\n"
                     f"Tribe: {self.tribe}  |  All parsed: {len(all_parsed)}"
                     + (f"  |  Source filter: '{self.village_name}'" if self.village_name else "") + "\n"
                     "First 30 cleaned lines seen:\n" + "\n".join(reinf_lines))
            self._preview.config(text=debug, fg=COL_RED)
            return

        lines_out = [f"✔  Found {len(self._parsed)} block(s){filtered_note}:"]
        for r in self._parsed:
            nonzero = {k: v for k, v in r["troops"].items() if v}
            lines_out.append(f"  {r['source_village']} → {r['target_village']}:  "
                             + ("  ".join(f"{k}: {v}" for k, v in nonzero.items()) or "all zero"))
        self._preview.config(text="\n".join(lines_out), fg=COL_FULL_GREEN)

    def _import(self):
        if not self._parsed:
            self._parse()
        if not self._parsed:
            return

        tribe_troops = get_tribe_troops(self.tribe)
        own_villages = {v["village_name"] for v in load_villages(self.server, self.account)}

        foreign_updates: dict = {}
        out_updates: dict = {}

        for r in self._parsed:
            src = r["source_village"]
            tgt = r["target_village"]

            if tgt not in foreign_updates:
                foreign_updates[tgt] = {t: 0 for t in tribe_troops}
            for t, cnt in r["troops"].items():
                if t in foreign_updates[tgt]:
                    foreign_updates[tgt][t] += cnt

            if src not in out_updates:
                out_updates[src] = {t: 0 for t in tribe_troops}
            for t, cnt in r["troops"].items():
                if t in out_updates[src]:
                    out_updates[src][t] += cnt

        updated = 0
        for vname, foreign_counts in foreign_updates.items():
            if vname not in own_villages:
                continue
            td = load_troop_data(self.server, self.account, vname, tribe_troops)
            for t in tribe_troops:
                td["foreign_in"][t] = foreign_counts.get(t, 0)
            save_troop_data(self.server, self.account, vname, tribe_troops, td)
            updated += 1

        for vname, out_counts in out_updates.items():
            if vname not in own_villages:
                continue
            td = load_troop_data(self.server, self.account, vname, tribe_troops)
            for t in tribe_troops:
                td["native_out"][t] = out_counts.get(t, 0)
                td["native_in"][t]  = max(0, td["trained"].get(t, 0) - td["native_out"][t])
            save_troop_data(self.server, self.account, vname, tribe_troops, td)
            # Save per-destination breakdown for this source village
            dest_rows = []
            for r in self._parsed:
                if r["source_village"] == vname:
                    row = {"target_village": r["target_village"]}
                    for t in tribe_troops:
                        row[t] = r["troops"].get(t, 0)
                    dest_rows.append(row)
            save_sent_troops(self.server, self.account, vname, dest_rows, tribe_troops)
            updated += 1

        self._status.config(text=f"✅  Updated {updated} village(s).", fg=COL_FULL_GREEN)
        self._parsed = []
        if self._on_complete:
            self._on_complete()


def parse_support_troops(raw_text: str, tribe: str) -> list:
    """
    Parse Rally Point → Overview → Troops in this village (and its oases).

    Row format (tab-separated):
      SOURCE TAB "Own troops"          → skip
      SOURCE TAB "PLAYER's troops"     → foreign reinforcement block
      coords TAB troop_name TAB ...
      "Troops" TAB count TAB ...

    Returns list of {source_village, troops: {name: count}}.
    'source_village' is the player name (from "PLAYER's troops").
    """
    import re as _re2

    def _cl(s):
        return _re2.sub(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069\xad\xa0,]', '', s).strip()

    tribe_troops = set(get_tribe_troops(tribe)) | {"Hero"}
    ci_lookup    = {t.lower(): t for t in tribe_troops}
    coord_pat    = _re2.compile(r'\(?\s*-?\d+\s*\|\s*[\u2212\-]?\d+\s*\)?')
    own_pat      = _re2.compile(r'^Own\s+troops$', _re2.IGNORECASE)
    # "Deadline's troops" or "Deadline's troops" (both apostrophe variants)
    foreign_pat  = _re2.compile(r"^(.+?)[\u2019']s\s+troops$", _re2.IGNORECASE)

    lines = raw_text.splitlines()
    results = []
    i = 0
    while i < len(lines):
        parts = [_cl(p) for p in lines[i].split('\t')]
        if len(parts) >= 2:
            # Skip own troops block
            if own_pat.match(parts[1]):
                i += 1
                continue
            m = foreign_pat.match(parts[1])
            if m:
                source = m.group(1).strip()
                j = i + 1
                troop_names = []
                if j < len(lines):
                    hdr = [_cl(p) for p in lines[j].split('\t')]
                    if coord_pat.search(hdr[0] if hdr else ""):
                        troop_names = [p for p in hdr[1:] if p and p.lower() != "hero"]
                        j += 1
                counts = []
                if j < len(lines):
                    tr = [_cl(p) for p in lines[j].split('\t')]
                    if tr and tr[0].lower() == "troops":
                        for p in tr[1:]:
                            try:
                                counts.append(int(p))
                            except ValueError:
                                pass
                        j += 1
                troops = dict(zip(troop_names, counts))
                results.append({"source_village": source, "troops": troops})
                i = j
                continue
        i += 1
    return results


# ─── Support Troops Import Dialog ─────────────────────────────────────────────

class SupportTroopsImportDialog(tk.Toplevel):
    """
    Parse Rally Point → Overview → Troops in this village.
    Imports foreign_in for this village, skipping own troops and
    avoiding duplication with troops already imported via sent troops.
    """
    def __init__(self, master, server, account, tribe,
                 village_name=None, on_complete=None):
        super().__init__(master)
        self.server       = server
        self.account      = account
        self.tribe        = tribe
        self.village_name = village_name
        self._on_complete = on_complete
        self.title("Import Support Troops")
        self.configure(bg=BG_DARK)
        self.geometry("720x560")
        self.grab_set()
        self._parsed = []
        self._build()

    def _build(self):
        pad = tk.Frame(self, bg=BG_DARK)
        pad.pack(fill="both", expand=True, padx=20, pady=16)

        tk.Label(pad, text="Import Support Troops", font=FONT_HEADING,
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, 4))
        tk.Label(pad,
                 text=f"Paste from Rally Point → Overview → Troops in this village"
                      + (f" (for '{self.village_name}')" if self.village_name else "") + ".\n"
                      "Own troops are ignored. Only foreign reinforcements are imported.\n"
                      "Troops already recorded via 'Import Sent Troops' are not duplicated.",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED,
                 justify="left").pack(anchor="w", pady=(0, 8))

        txt_frame = tk.Frame(pad, bg=BORDER)
        txt_frame.pack(fill="both", expand=True)
        self._txt = tk.Text(txt_frame, bg=BG_MID, fg=TEXT_PRIMARY,
                            insertbackground=ACCENT, font=("Consolas", 9),
                            relief="flat", bd=6, wrap="none",
                            selectbackground=BG_HOVER)
        sb = tk.Scrollbar(txt_frame, command=self._txt.yview,
                          bg=BG_MID, troughcolor=BG_DARK, relief="flat", bd=0, width=8)
        self._txt.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._txt.pack(fill="both", expand=True)

        self._preview = tk.Label(pad, text="", font=("Consolas", 8),
                                 bg=BG_DARK, fg=COL_FULL_GREEN,
                                 justify="left", wraplength=660, anchor="w")
        self._preview.pack(fill="x", pady=(6, 0))

        btn_row = tk.Frame(pad, bg=BG_DARK)
        btn_row.pack(fill="x", pady=(8, 0))
        styled_button(btn_row, "🔍  Parse",  command=self._parse,  accent=True).pack(side="left")
        styled_button(btn_row, "✅  Import", command=self._import, small=True).pack(side="left", padx=6)
        self._status = tk.Label(btn_row, text="", font=FONT_SMALL,
                                bg=BG_DARK, fg=COL_FULL_GREEN)
        self._status.pack(side="left", padx=8)
        styled_button(btn_row, "Close", command=self.destroy, small=True).pack(side="right")

    def _parse(self):
        raw = self._txt.get("1.0", "end")
        self._parsed = parse_support_troops(raw, self.tribe)
        if not self._parsed:
            import re as _re
            def _cl(s):
                return _re.sub(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069\xad\xa0,]', '', s).strip()
            lines = raw.splitlines()
            preview_lines = [f"  [{i}] {repr(_cl(ln))}" for i, ln in enumerate(lines[:25]) if _cl(ln)]
            self._preview.config(
                text="❌  No support troops found. Make sure you pasted from\n"
                     "Rally Point → Overview → Troops in this village.\n\n"
                     "First 25 lines:\n" + "\n".join(preview_lines),
                fg=COL_RED)
            return
        lines_out = [f"✔  Found {len(self._parsed)} reinforcement(s):"]
        for r in self._parsed:
            nonzero = {k: v for k, v in r["troops"].items() if v}
            lines_out.append(f"  from {r['source_village']}:  "
                             + ("  ".join(f"{k}: {v}" for k, v in nonzero.items()) or "all zero"))
        self._preview.config(text="\n".join(lines_out), fg=COL_FULL_GREEN)

    def _import(self):
        if not self._parsed:
            self._parse()
        if not self._parsed:
            return

        tribe_troops = get_tribe_troops(self.tribe)
        target = self.village_name

        # Build set of (source_village, troop_name, count) already recorded
        # via sent troops imports from any village → avoid double-counting
        already_sent: dict = {}   # source_village -> {troop: count}
        for v in load_villages(self.server, self.account):
            vname = v["village_name"]
            for row in load_sent_troops(self.server, self.account, vname):
                tgt = row.get("target_village", "")
                if tgt != target:
                    continue
                src = vname
                if src not in already_sent:
                    already_sent[src] = {t: 0 for t in tribe_troops}
                for t in tribe_troops:
                    try:
                        already_sent[src][t] += int(row.get(t, 0) or 0)
                    except ValueError:
                        pass

        # Accumulate foreign_in for this village, subtracting already-known sent troops
        foreign_totals = {t: 0 for t in tribe_troops}
        for r in self._parsed:
            src = r["source_village"]
            known = already_sent.get(src, {})
            for t in tribe_troops:
                incoming = r["troops"].get(t, 0)
                already  = known.get(t, 0)
                net = max(0, incoming - already)
                foreign_totals[t] += net

        if target:
            td = load_troop_data(self.server, self.account, target, tribe_troops)
            for t in tribe_troops:
                td["foreign_in"][t] = foreign_totals.get(t, 0)
            save_troop_data(self.server, self.account, target, tribe_troops, td)

        self._status.config(text="✅  Support troops imported.", fg=COL_FULL_GREEN)
        self._parsed = []
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
            ("🏠  Account Overview",  self._show_account_overview),
            ("🤝  Alliance Info",     self._show_alliance_info),
            ("🗺   Map",              self._show_map),
            ("🔄  Trade Route Summary", self._show_trade_route_summary),
            ("📊  Production Info",   self._show_production_info),
            ("⚔   Troops Overview",   self._show_troops_overview),
            ("⚔   Net Troops",        self._show_troop_locations),
            ("⚡  Net Production",    self._show_net_production),
        ]:
            nav_button(pad, label, command=cmd).pack(fill="x")

        make_separator(pad).pack(fill="x", padx=8, pady=10)
        section_label(pad, "Statistics").pack(fill="x", padx=12, pady=(0, 4))
        for label, cmd in [
            ("🌾  Farm Top Stats",    self._show_farm_top_stats),
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
            ("🪖  Troops",             lambda: self._show_troops(vn)),
            ("⚙   Troop Queues",       lambda: self._show_troop_queues(vn)),
            ("📊  Net Resources",      lambda: self._show_net_resources(vn)),
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

    def _show_account_overview(self):
        self._clear_center()
        villages  = load_villages(self.server, self.account)
        templates = list_templates(self.server, self.account)

        outer = tk.Frame(self.center, bg=BG_DARK)
        outer.pack(fill="both", expand=True)

        hdr = tk.Frame(outer, bg=BG_DARK)
        hdr.pack(fill="x", padx=24, pady=(24, 0))
        tk.Label(hdr, text="Account Overview",
                 font=FONT_TITLE, bg=BG_DARK, fg=TEXT_PRIMARY).pack(side="left")
        tk.Label(hdr, text=f"  —  {len(villages)} villages",
                 font=FONT_BODY, bg=BG_DARK, fg=TEXT_MUTED).pack(side="left", pady=(6, 0))
        status_lbl = tk.Label(hdr, text="", font=FONT_SMALL,
                              bg=BG_DARK, fg=COL_FULL_GREEN, width=28, anchor="w")
        status_lbl.pack(side="left", padx=(16, 0))
        if not self.is_archived:
            styled_button(hdr, "💾  Apply Templates",
                          command=lambda: _save_templates(),
                          accent=True).pack(side="left")
        make_separator(outer).pack(fill="x", padx=24, pady=10)

        if not villages:
            tk.Label(outer, text="No villages yet. Use Import Overview or add manually.",
                     font=FONT_BODY, bg=BG_DARK, fg=TEXT_MUTED).pack(padx=24, anchor="w")
            return

        # ── state tracking ────────────────────────────────────────────────────
        # Find current capital
        cap_var   = tk.StringVar(value=next(
            (v["village_name"] for v in villages if v.get("is_capital") == "1"), ""))
        t_var_map = {}   # vname -> StringVar for template dropdown

        def _save_templates():
            applied = 0
            skipped = 0
            for vname, tvar in t_var_map.items():
                chosen = tvar.get()
                if chosen and chosen != "— None —":
                    layout = load_template(self.server, self.account, chosen)
                    if layout:
                        save_layout(self.server, self.account, vname, layout)
                        update_village(self.server, self.account, vname,
                                       {"applied_template": chosen})
                        applied += 1
                    else:
                        skipped += 1
                else:
                    # Explicitly clear the template assignment
                    update_village(self.server, self.account, vname,
                                   {"applied_template": ""})
            msg = f"✓ Applied {applied} template(s)"
            if skipped:
                msg += f"  ({skipped} not found)"
            status_lbl.config(text=msg,
                              fg=COL_FULL_GREEN if not skipped else COL_ORANGE)
            fade_label(status_lbl, after_ms=4000)

        def _on_capital_click(vname: str):
            """Toggle capital: if already capital, deselect; else set as new capital."""
            current = cap_var.get()
            new_cap = "" if current == vname else vname
            cap_var.set(new_cap)
            if new_cap:
                set_capital(self.server, self.account, new_cap)
            else:
                # Clear all
                for v in load_villages(self.server, self.account):
                    v["is_capital"] = ""
                _rewrite_villages(self.server, self.account,
                                  load_villages(self.server, self.account))
                update_village(self.server, self.account, vname, {"is_capital": ""})
            _rebuild()

        # ── table container (rebuilt after capital toggle) ─────────────────────
        table_container = tk.Frame(outer, bg=BG_DARK)
        table_container.pack(fill="both", expand=True)

        troop_names = get_tribe_troops(self.tribe)   # tribe-specific unit list
        bool_flags  = ["Small", "Large"]

        # roles_map: {vname: {flag: "1"/"0"}}
        roles_map = load_village_roles(self.server, self.account)
        # bool vars: {vname: {flag: BooleanVar}}
        bool_vars: dict = {}

        def _save_roles():
            new_roles = {}
            for vname, fvars in bool_vars.items():
                new_roles[vname] = {flag: "1" if var.get() else "0"
                                    for flag, var in fvars.items()}
            save_village_roles(self.server, self.account, new_roles)
            status_lbl.config(text="✓ Saved", fg=COL_FULL_GREEN)
            fade_label(status_lbl, after_ms=3000)

        # Wire save button (already in header)
        # We attach the command after bool_vars is populated in _rebuild

        def _rebuild():
            for w in table_container.winfo_children():
                w.destroy()
            bool_vars.clear()

            cur_villages = load_villages(self.server, self.account)
            scroll_outer, inner = scrollable_frame(table_container)
            scroll_outer.pack(fill="both", expand=True, padx=24, pady=(0, 16))

            tbl = tk.Frame(inner, bg=BG_DARK)
            tbl.pack(fill="x")

            # Fixed columns
            tbl.columnconfigure(0, minsize=180)   # village name
            tbl.columnconfigure(1, minsize=60)    # capital
            tbl.columnconfigure(2, minsize=180)   # template
            # Boolean flag columns
            for ci, _ in enumerate(bool_flags, start=3):
                tbl.columnconfigure(ci, minsize=55, uniform="bool")

            n_cols = 3 + len(bool_flags)

            def gh(col, text, bg=BG_MID, fg=TEXT_MUTED, anchor="center"):
                tk.Label(tbl, text=text, font=("Consolas", 9, "bold"),
                         bg=bg, fg=fg, anchor=anchor, padx=4, pady=3
                         ).grid(row=0, column=col, sticky="nsew", padx=(0,1), pady=(0,1))

            gh(0, "Village",          anchor="w")
            gh(1, "👑")
            gh(2, "Layout Template",  anchor="w")
            for ci, flag in enumerate(bool_flags, start=3):
                # Abbreviate long troop names
                disp = flag if len(flag) <= 8 else flag[:7] + "…"
                lbl = tk.Label(tbl, text=disp, font=("Consolas", 8, "bold"),
                               bg=BG_MID, fg=TEXT_MUTED, anchor="center", padx=2, pady=3)
                lbl.grid(row=0, column=ci, sticky="nsew", padx=(0,1), pady=(0,1))
                if len(flag) > 8:
                    lbl.bind("<Enter>", lambda e, w=lbl, f=flag: w.config(text=f))
                    lbl.bind("<Leave>", lambda e, w=lbl, d=disp: w.config(text=d))

            tk.Frame(tbl, bg=BORDER, height=1).grid(
                row=1, column=0, columnspan=n_cols, sticky="ew", pady=(0,1))

            tmpl_opts = ["— None —"] + templates

            for i, v in enumerate(cur_villages):
                r      = i + 2
                bg     = BG_MID if i % 2 == 0 else BG_PANEL
                vname  = v["village_name"]
                is_cap = v.get("is_capital", "") == "1"

                # Village name
                tk.Label(tbl, text=("👑 " if is_cap else "   ") + vname,
                         font=FONT_SMALL, bg=bg,
                         fg=ACCENT if is_cap else TEXT_PRIMARY,
                         anchor="w", padx=6, pady=3
                         ).grid(row=r, column=0, sticky="nsew", padx=(0,1), pady=(0,1))

                # Capital toggle
                cap_btn = tk.Button(
                    tbl, text="★" if is_cap else "☆",
                    font=FONT_SMALL,
                    bg=ACCENT_DIM if is_cap else bg,
                    fg=ACCENT if is_cap else TEXT_MUTED,
                    activebackground=BG_HOVER, activeforeground=ACCENT,
                    relief="flat", bd=0, cursor="hand2",
                    command=lambda vn=vname: _on_capital_click(vn))
                if self.is_archived:
                    cap_btn.config(state="disabled")
                cap_btn.grid(row=r, column=1, sticky="nsew", padx=(0,1), pady=(0,1))

                # Template dropdown
                cur_tmpl = v.get("applied_template", "") or "— None —"
                t_var = tk.StringVar(value=cur_tmpl if cur_tmpl in tmpl_opts else "— None —")
                t_var_map[vname] = t_var
                state = "disabled" if self.is_archived else "readonly"
                cb = styled_combo(tbl, t_var, tmpl_opts, width=18, state=state)
                cb.grid(row=r, column=2, sticky="nsew", padx=(0,1), pady=(0,1))

                # Boolean flag checkboxes
                vflags = roles_map.get(vname, {})
                bool_vars[vname] = {}
                for ci, flag in enumerate(bool_flags, start=3):
                    bvar = tk.BooleanVar(value=vflags.get(flag, "0") == "1")
                    bool_vars[vname][flag] = bvar

                    # Small and Large are mutually exclusive
                    if flag == "Small":
                        cmd = lambda vn=vname, bv=bvar: (
                            bool_vars[vn]["Large"].set(False) if bv.get() else None)
                    elif flag == "Large":
                        cmd = lambda vn=vname, bv=bvar: (
                            bool_vars[vn]["Small"].set(False) if bv.get() else None)
                    else:
                        cmd = None

                    cb2 = tk.Checkbutton(tbl, variable=bvar, command=cmd,
                                         bg=bg, activebackground=bg,
                                         fg=COL_FULL_GREEN, activeforeground=COL_FULL_GREEN,
                                         selectcolor=bg, relief="flat", bd=0)
                    if self.is_archived:
                        cb2.config(state="disabled")
                    cb2.grid(row=r, column=ci, sticky="nsew", padx=(0,1), pady=(0,1))

        # Wire the save button's command now that _save_roles is defined
        if not self.is_archived:
            # Find and update the Apply Templates button to also save roles,
            # or add a dedicated Save Roles button
            save_roles_btn = styled_button(hdr, "💾  Save Roles",
                                           command=_save_roles, small=True)
            save_roles_btn.pack(side="left", padx=(8, 0))

        _rebuild()

    def _show_alliance_info(self):
        self._clear_center()

        outer = tk.Frame(self.center, bg=BG_DARK)
        outer.pack(fill="both", expand=True)

        # ── Scrollable container for the whole page ───────────────────────────
        scroll_outer, page = scrollable_frame(outer)
        scroll_outer.pack(fill="both", expand=True)

        info        = load_alliance_info(self.server, self.account)
        bonus_table = load_alliance_bonus_table()

        # ══ Header ════════════════════════════════════════════════════════════
        hdr = tk.Frame(page, bg=BG_DARK)
        hdr.pack(fill="x", padx=24, pady=(24, 0))
        tk.Label(hdr, text="Alliance Info",
                 font=FONT_TITLE, bg=BG_DARK, fg=TEXT_PRIMARY).pack(side="left")
        if not self.is_archived:
            styled_button(hdr, "💾  Save All", command=lambda: _save_all(),
                          accent=True).pack(side="left", padx=(16, 0))
        status_lbl = tk.Label(hdr, text="", font=FONT_SMALL,
                              bg=BG_DARK, fg=COL_FULL_GREEN)
        status_lbl.pack(side="left", padx=12)
        make_separator(page).pack(fill="x", padx=24, pady=10)

        # ══ Alliance name ═════════════════════════════════════════════════════
        name_frame = tk.Frame(page, bg=BG_DARK)
        name_frame.pack(fill="x", padx=24, pady=(0, 16))
        tk.Label(name_frame, text="Alliance name:", font=FONT_SMALL,
                 bg=BG_DARK, fg=TEXT_SECONDARY, width=16, anchor="w").pack(side="left")
        name_var = tk.StringVar(value=info.get("alliance_name", ""))
        state = "disabled" if self.is_archived else "normal"
        styled_entry(name_frame, name_var, width=30).pack(side="left")

        # ══ Alliance Bonuses table ════════════════════════════════════════════
        tk.Label(page, text="Alliance Bonuses", font=FONT_HEADING,
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack(anchor="w", padx=24, pady=(0, 6))

        bonus_frame = tk.Frame(page, bg=BG_DARK)
        bonus_frame.pack(fill="x", padx=24, pady=(0, 20))
        bonus_frame.columnconfigure(0, minsize=160)
        bonus_frame.columnconfigure(1, minsize=80)
        bonus_frame.columnconfigure(2, minsize=80)
        bonus_frame.columnconfigure(3, minsize=260)

        # Header
        for ci, text in enumerate(["Bonus Type", "Level", "Value", "Description"]):
            tk.Label(bonus_frame, text=text, font=("Consolas", 9, "bold"),
                     bg=BG_MID, fg=TEXT_MUTED, anchor="w", padx=6, pady=3
                     ).grid(row=0, column=ci, sticky="nsew", padx=(0,1), pady=(0,1))
        tk.Frame(bonus_frame, bg=BORDER, height=1).grid(
            row=1, column=0, columnspan=4, sticky="ew", pady=(0,1))

        bonus_level_vars = {}

        for bi, bt in enumerate(ALLIANCE_BONUS_TYPES):
            r  = bi + 2
            bg = BG_MID if bi % 2 == 0 else BG_PANEL
            tk.Label(bonus_frame, text=bt, font=FONT_SMALL,
                     bg=bg, fg=TEXT_PRIMARY, anchor="w", padx=6, pady=3
                     ).grid(row=r, column=0, sticky="nsew", padx=(0,1), pady=(0,1))

            lvl_var = tk.StringVar(value=str(info.get(bt, 0)))
            bonus_level_vars[bt] = lvl_var

            val_lbl  = tk.Label(bonus_frame, text="", font=("Consolas", 9, "bold"),
                                bg=bg, fg=ACCENT, anchor="w", padx=6, pady=3)
            val_lbl.grid(row=r, column=2, sticky="nsew", padx=(0,1), pady=(0,1))

            desc_lbl = tk.Label(bonus_frame, text="", font=FONT_SMALL,
                                bg=bg, fg=TEXT_SECONDARY, anchor="w", padx=6, pady=3)
            desc_lbl.grid(row=r, column=3, sticky="nsew", padx=(0,1), pady=(0,1))

            def _update_row(bt=bt, var=lvl_var, vl=val_lbl, dl=desc_lbl):
                try:
                    lvl = int(var.get())
                except ValueError:
                    lvl = 0
                entry = bonus_table.get(bt, {}).get(lvl, {})
                vl.config(text=entry.get("value", ""))
                dl.config(text=entry.get("description", ""))

            cb = styled_combo(bonus_frame, lvl_var,
                              [str(i) for i in range(6)], width=8,
                              state="disabled" if self.is_archived else "readonly")
            cb.grid(row=r, column=1, sticky="nsew", padx=(0,1), pady=(0,1))
            lvl_var.trace_add("write", lambda *_, bt=bt, v=lvl_var, vl=val_lbl, dl=desc_lbl:
                              _update_row(bt, v, vl, dl))
            _update_row(bt, lvl_var, val_lbl, desc_lbl)

        # ══ Known Villages section ════════════════════════════════════════════
        make_separator(page).pack(fill="x", padx=24, pady=(4, 12))

        kv_hdr = tk.Frame(page, bg=BG_DARK)
        kv_hdr.pack(fill="x", padx=24, pady=(0, 8))
        tk.Label(kv_hdr, text="Known Villages", font=FONT_HEADING,
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack(side="left")
        if not self.is_archived:
            styled_button(kv_hdr, "➕ Add Village",
                          command=lambda: _add_village_dialog(), small=True,
                          accent=True).pack(side="right", padx=(4,0))
            styled_button(kv_hdr, "🏷 Add Type",
                          command=lambda: _add_type_dialog(), small=True
                          ).pack(side="right", padx=(4,0))

        kv_container = tk.Frame(page, bg=BG_DARK)
        kv_container.pack(fill="x", padx=24, pady=(0, 24))

        def _rebuild_kv_table():
            for w in kv_container.winfo_children():
                w.destroy()

            known   = load_known_villages(self.server, self.account)
            types   = load_known_village_types(self.server, self.account)
            sel_vars_kv = {}

            if not self.is_archived:
                rm_row = tk.Frame(kv_container, bg=BG_DARK)
                rm_row.pack(anchor="e", pady=(0, 4))
                styled_button(rm_row, "🗑 Remove Selected",
                              command=lambda: _remove_kv(sel_vars_kv), small=True
                              ).pack(side="right")

            tbl = tk.Frame(kv_container, bg=BG_DARK)
            tbl.pack(fill="x")
            tbl.columnconfigure(0, minsize=30)   # select
            tbl.columnconfigure(1, minsize=200)  # name
            tbl.columnconfigure(2, minsize=70)   # x
            tbl.columnconfigure(3, minsize=70)   # y
            tbl.columnconfigure(4, minsize=180)  # type

            for ci, text in enumerate(["", "Name", "X", "Y", "Type"]):
                tk.Label(tbl, text=text, font=("Consolas",9,"bold"),
                         bg=BG_MID, fg=TEXT_MUTED, anchor="w" if ci > 0 else "center",
                         padx=4, pady=3
                         ).grid(row=0, column=ci, sticky="nsew", padx=(0,1), pady=(0,1))
            tk.Frame(tbl, bg=BORDER, height=1).grid(
                row=1, column=0, columnspan=5, sticky="ew", pady=(0,1))

            if not known:
                tk.Label(tbl, text="No known villages yet.",
                         font=FONT_SMALL, bg=BG_PANEL, fg=TEXT_MUTED,
                         anchor="w", padx=8, pady=6
                         ).grid(row=2, column=0, columnspan=5, sticky="ew")
                return

            type_opts = [""] + types
            for i, v in enumerate(known):
                r   = i + 2
                bg  = BG_MID if i % 2 == 0 else BG_PANEL
                vid = v.get("village_id", str(i))

                sel = tk.BooleanVar(value=False)
                sel_vars_kv[vid] = sel
                tk.Checkbutton(tbl, variable=sel, bg=bg, activebackground=bg,
                               selectcolor=BG_HOVER, relief="flat", bd=0
                               ).grid(row=r, column=0, sticky="nsew", padx=(0,1), pady=(0,1))

                for ci, (key, anchor) in enumerate([("name","w"),("coord_x","center"),("coord_y","center")], start=1):
                    tk.Label(tbl, text=v.get(key,"—"), font=FONT_SMALL,
                             bg=bg, fg=TEXT_PRIMARY, anchor=anchor, padx=4, pady=3
                             ).grid(row=r, column=ci, sticky="nsew", padx=(0,1), pady=(0,1))

                t_var = tk.StringVar(value=v.get("vtype",""))
                cb = styled_combo(tbl, t_var, type_opts, width=20,
                                  state="disabled" if self.is_archived else "readonly")
                cb.grid(row=r, column=4, sticky="nsew", padx=(0,1), pady=(0,1))
                def _on_type(vid=vid, tv=t_var):
                    kv = load_known_villages(self.server, self.account)
                    for entry in kv:
                        if entry.get("village_id") == vid:
                            entry["vtype"] = tv.get()
                    save_known_villages(self.server, self.account, kv)
                t_var.trace_add("write", lambda *_, vid=vid, tv=t_var: _on_type(vid, tv))

        def _remove_kv(sel_vars_kv):
            selected = {vid for vid, var in sel_vars_kv.items() if var.get()}
            if not selected:
                return
            kv = load_known_villages(self.server, self.account)
            kv = [v for v in kv if v.get("village_id") not in selected]
            save_known_villages(self.server, self.account, kv)
            _rebuild_kv_table()

        def _add_village_dialog():
            dlg = tk.Toplevel(self)
            dlg.title("Add Known Village")
            dlg.configure(bg=BG_DARK)
            dlg.geometry("360x240")
            dlg.grab_set()
            pad2 = tk.Frame(dlg, bg=BG_DARK)
            pad2.pack(fill="both", expand=True, padx=16, pady=14)
            tk.Label(pad2, text="Add Known Village", font=FONT_HEADING,
                     bg=BG_DARK, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0,10))
            fvars = {}
            for label, key, default in [("Village name","name",""),
                                         ("X coord","coord_x","0"),
                                         ("Y coord","coord_y","0")]:
                f = tk.Frame(pad2, bg=BG_DARK)
                f.pack(fill="x", pady=2)
                tk.Label(f, text=label, width=14, font=FONT_SMALL,
                         bg=BG_DARK, fg=TEXT_SECONDARY, anchor="w").pack(side="left")
                var = tk.StringVar(value=default)
                styled_entry(f, var, width=16).pack(side="left")
                fvars[key] = var

            types = load_known_village_types(self.server, self.account)
            tf = tk.Frame(pad2, bg=BG_DARK)
            tf.pack(fill="x", pady=2)
            tk.Label(tf, text="Type", width=14, font=FONT_SMALL,
                     bg=BG_DARK, fg=TEXT_SECONDARY, anchor="w").pack(side="left")
            t_var = tk.StringVar(value="")
            styled_combo(tf, t_var, [""] + types, width=16).pack(side="left")

            err = tk.Label(pad2, text="", font=FONT_SMALL, bg=BG_DARK, fg=COL_RED)
            err.pack(anchor="w", pady=(4,0))

            def _do_add():
                name = fvars["name"].get().strip()
                if not name:
                    err.config(text="Name is required.")
                    return
                kv = load_known_villages(self.server, self.account)
                kv.append({"village_id": _next_village_id(kv),
                           "name": name,
                           "coord_x": fvars["coord_x"].get().strip(),
                           "coord_y": fvars["coord_y"].get().strip(),
                           "vtype":   t_var.get().strip()})
                save_known_villages(self.server, self.account, kv)
                dlg.destroy()
                _rebuild_kv_table()

            br = tk.Frame(pad2, bg=BG_DARK)
            br.pack(fill="x", pady=(10,0))
            styled_button(br, "Add", command=_do_add, accent=True).pack(side="left")
            styled_button(br, "Cancel", command=dlg.destroy, small=True).pack(side="left", padx=8)

        def _add_type_dialog():
            dlg = tk.Toplevel(self)
            dlg.title("Add Village Type")
            dlg.configure(bg=BG_DARK)
            dlg.geometry("340x180")
            dlg.grab_set()
            pad2 = tk.Frame(dlg, bg=BG_DARK)
            pad2.pack(fill="both", expand=True, padx=16, pady=14)
            tk.Label(pad2, text="Add Village Type", font=FONT_HEADING,
                     bg=BG_DARK, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0,10))
            f = tk.Frame(pad2, bg=BG_DARK)
            f.pack(fill="x", pady=2)
            tk.Label(f, text="Type name", width=12, font=FONT_SMALL,
                     bg=BG_DARK, fg=TEXT_SECONDARY, anchor="w").pack(side="left")
            t_var = tk.StringVar()
            styled_entry(f, t_var, width=20).pack(side="left")

            # Show existing types
            existing = load_known_village_types(self.server, self.account)
            if existing:
                tk.Label(pad2, text="Existing: " + ", ".join(existing),
                         font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED,
                         wraplength=280, justify="left").pack(anchor="w", pady=(4,0))

            err = tk.Label(pad2, text="", font=FONT_SMALL, bg=BG_DARK, fg=COL_RED)
            err.pack(anchor="w", pady=(4,0))

            def _do_add():
                name = t_var.get().strip()
                if not name:
                    err.config(text="Type name is required.")
                    return
                types = load_known_village_types(self.server, self.account)
                if name in types:
                    err.config(text="Type already exists.")
                    return
                types.append(name)
                save_known_village_types(self.server, self.account, types)
                dlg.destroy()
                _rebuild_kv_table()

            br = tk.Frame(pad2, bg=BG_DARK)
            br.pack(fill="x", pady=(10,0))
            styled_button(br, "Add", command=_do_add, accent=True).pack(side="left")
            styled_button(br, "Cancel", command=dlg.destroy, small=True).pack(side="left", padx=8)

        def _save_all():
            info_new = {
                "alliance_name": name_var.get().strip(),
            }
            for bt in ALLIANCE_BONUS_TYPES:
                try:
                    info_new[bt] = int(bonus_level_vars[bt].get())
                except ValueError:
                    info_new[bt] = 0
            save_alliance_info(self.server, self.account, info_new)
            status_lbl.config(text="✓ Saved", fg=COL_FULL_GREEN)
            fade_label(status_lbl, after_ms=3000)

        _rebuild_kv_table()

    def _show_trade_route_summary(self):
        self._clear_center()
        villages = load_villages(self.server, self.account)

        outer = tk.Frame(self.center, bg=BG_DARK)
        outer.pack(fill="both", expand=True)

        hdr = tk.Frame(outer, bg=BG_DARK)
        hdr.pack(fill="x", padx=24, pady=(24, 0))
        tk.Label(hdr, text="Trade Route Summary",
                 font=FONT_TITLE, bg=BG_DARK, fg=TEXT_PRIMARY).pack(side="left")
        tk.Label(hdr, text="  —  outgoing and incoming routes per village",
                 font=FONT_BODY, bg=BG_DARK, fg=TEXT_MUTED).pack(side="left", pady=(6, 0))
        make_separator(outer).pack(fill="x", padx=24, pady=10)

        if not villages:
            tk.Label(outer, text="No villages found.",
                     font=FONT_BODY, bg=BG_DARK, fg=TEXT_MUTED).pack(padx=24, anchor="w")
            return

        # ── Count outgoing per village ────────────────────────────────────────
        outgoing = {}   # village_name -> count
        incoming = {}   # village_name -> count
        for v in villages:
            outgoing[v["village_name"]] = 0
            incoming[v["village_name"]] = 0

        for v in villages:
            vname = v["village_name"]
            routes = load_trade_routes(self.server, self.account, vname)
            outgoing[vname] = len(routes)
            for rt in routes:
                target = rt.get("target", "")
                if target in incoming:
                    incoming[target] += 1

        total_out = sum(outgoing.values())
        total_in  = sum(incoming.values())

        # ── Grid table ────────────────────────────────────────────────────────
        scroll_outer, inner = scrollable_frame(outer)
        scroll_outer.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        tbl = tk.Frame(inner, bg=BG_DARK)
        tbl.pack(fill="x")
        tbl.columnconfigure(0, minsize=200)
        tbl.columnconfigure(1, minsize=120, uniform="counts")
        tbl.columnconfigure(2, minsize=120, uniform="counts")

        def gl(row, col, text, bg, fg, bold=False, anchor="center"):
            tk.Label(tbl, text=text,
                     font=("Consolas", 9, "bold") if bold else FONT_SMALL,
                     bg=bg, fg=fg, anchor=anchor, padx=8, pady=4
                     ).grid(row=row, column=col, sticky="nsew",
                            padx=(0, 1), pady=(0, 1))

        # Header
        gl(0, 0, "Village",   BG_MID, TEXT_MUTED, bold=True, anchor="w")
        gl(0, 1, "↑ Outgoing", BG_MID, "#e07820",  bold=True)
        gl(0, 2, "↓ Incoming", BG_MID, "#4090d8",  bold=True)
        tk.Frame(tbl, bg=BORDER, height=1).grid(
            row=1, column=0, columnspan=3, sticky="ew", pady=(0, 1))

        for i, v in enumerate(villages):
            r    = i + 2
            bg   = BG_MID if i % 2 == 0 else BG_PANEL
            vn   = v["village_name"]
            out  = outgoing[vn]
            inc  = incoming[vn]
            gl(r, 0, vn,         bg, TEXT_PRIMARY, anchor="w")
            gl(r, 1, str(out) if out else "—", bg,
               "#e07820" if out else TEXT_MUTED)
            gl(r, 2, str(inc) if inc else "—", bg,
               "#4090d8" if inc else TEXT_MUTED)

        # Totals row
        tk.Frame(tbl, bg=ACCENT_DIM, height=1).grid(
            row=len(villages) + 2, column=0, columnspan=3, sticky="ew", pady=(2, 1))
        tr = len(villages) + 3
        gl(tr, 0, "Total",         BG_HOVER, ACCENT,    bold=True, anchor="w")
        gl(tr, 1, str(total_out),  BG_HOVER, "#e07820", bold=True)
        gl(tr, 2, str(total_in),   BG_HOVER, "#4090d8", bold=True)

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

        # Data source dropdown
        src_var = tk.StringVar(value=load_option("prod_data_source", "Village Data"))
        src_frame = tk.Frame(hdr, bg=BG_MID, highlightthickness=1,
                             highlightbackground=BORDER)
        src_frame.pack(side="right", padx=(8, 0))
        tk.Label(src_frame, text="Data source:", font=FONT_SMALL,
                 bg=BG_MID, fg=TEXT_MUTED).pack(side="left", padx=(8, 4), pady=4)
        styled_combo(src_frame, src_var, ["Village Data", "Parsed"],
                     width=14, state="readonly").pack(side="left", padx=(0, 8), pady=4)

        # Import button
        if not self.is_archived:
            styled_button(hdr, "📥  Import Production",
                          command=lambda: _open_import(),
                          small=True).pack(side="right", padx=(8, 0))

        # Gold bonus toggle — only relevant for Village Data source
        gold_var = tk.BooleanVar(value=load_option("gold_bonus", "False") == "True")
        gold_frame = tk.Frame(hdr, bg=BG_MID, relief="flat", bd=0,
                              highlightthickness=1, highlightbackground=BORDER)
        gold_frame.pack(side="right", padx=(8, 0))
        gold_cb = tk.Checkbutton(
            gold_frame, text="💰 +25% Gold Bonus",
            variable=gold_var,
            command=lambda: (save_option("gold_bonus", gold_var.get()), _refresh()),
            bg=BG_MID, fg=TEXT_PRIMARY, selectcolor=BG_HOVER,
            activebackground=BG_MID, activeforeground=ACCENT,
            font=FONT_SMALL, relief="flat", bd=0, highlightthickness=0)
        gold_cb.pack(padx=8, pady=4)

        make_separator(outer).pack(fill="x", padx=24, pady=10)

        if not villages:
            tk.Label(outer, text="No villages found for this account.",
                     font=FONT_BODY, bg=BG_DARK, fg=TEXT_MUTED).pack(padx=24, anchor="w")
            return

        table_container = tk.Frame(outer, bg=BG_DARK)
        table_container.pack(fill="both", expand=True)

        COLS = [
            (1, "🌲 Wood", "wood", "#7daa6f"),
            (2, "🧱 Clay", "clay", "#b87c4c"),
            (3, "⚙ Iron",  "iron", "#8aabcc"),
            (4, "🌾 Crop", "crop", "#c8b84a"),
        ]

        def _refresh(*_):
            save_option("prod_data_source", src_var.get())
            use_parsed = src_var.get() == "Parsed"
            # Gold bonus only relevant for Village Data
            gold_cb.config(state="disabled" if use_parsed else "normal")
            gold_frame.config(highlightbackground=TEXT_MUTED if use_parsed else BORDER)
            _build_table(use_parsed)

        src_var.trace_add("write", _refresh)

        def _build_table(use_parsed: bool):
            for w in table_container.winfo_children():
                w.destroy()

            rows   = []
            totals = {"wood": 0, "clay": 0, "iron": 0, "crop": 0}

            if use_parsed:
                parsed = load_parsed_production(self.server, self.account)
                for v in villages:
                    vname = v["village_name"]
                    prod  = parsed.get(vname, {"wood":0,"clay":0,"iron":0,"crop":0})
                    rows.append((vname, prod))
                    for k in totals:
                        totals[k] += prod[k]
                note = "  (from imported data)"
            else:
                gold_bonus = gold_var.get()
                for v in villages:
                    vname = v["village_name"]
                    prod  = calculate_village_production(
                        self.server, self.account, vname, gold_bonus)
                    rows.append((vname, prod))
                    for k in totals:
                        totals[k] += prod[k]
                note = "  (incl. 25% gold bonus)" if gold_bonus else ""

            scroll_outer, inner = scrollable_frame(table_container)
            scroll_outer.pack(fill="both", expand=True, padx=24, pady=(0, 16))

            tbl = tk.Frame(inner, bg=BG_DARK)
            tbl.pack(fill="x")
            tbl.columnconfigure(0, minsize=180)
            for c in range(1, 5):
                tbl.columnconfigure(c, minsize=90, uniform="res")

            def gl(row, col, text, bg, fg, bold=False, anchor="center"):
                tk.Label(tbl, text=text,
                         font=("Consolas", 9, "bold") if bold else FONT_SMALL,
                         bg=bg, fg=fg, anchor=anchor, padx=6, pady=3
                         ).grid(row=row, column=col, sticky="nsew",
                                padx=(0, 1), pady=(0, 1))

            gl(0, 0, "Village", BG_MID, TEXT_MUTED, bold=True, anchor="w")
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
            tk.Label(inner,
                     text=f"Total production:  {grand:,} /hr{note}",
                     font=("Consolas", 9, "bold"), bg=BG_DARK, fg=ACCENT
                     ).pack(anchor="w", padx=4, pady=(8, 4))

        def _open_import():
            dlg = ImportProductionDialog(self, self.server, self.account,
                                         [v["village_name"] for v in villages])
            self.wait_window(dlg)
            if src_var.get() == "Parsed":
                _build_table(True)

        # Initial render
        _refresh()

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

    def _show_map(self):
        self._clear_center()
        villages = load_villages(self.server, self.account)

        outer = tk.Frame(self.center, bg=BG_DARK)
        outer.pack(fill="both", expand=True)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(outer, bg=BG_DARK)
        hdr.pack(fill="x", padx=24, pady=(18, 0))
        tk.Label(hdr, text="Map", font=FONT_TITLE,
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack(side="left")
        tk.Label(hdr, text="  scroll to zoom  ·  drag to pan  ·  hover for village name",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(side="left", pady=(6, 0))

        # Trade routes toggle
        show_routes_var = tk.BooleanVar(value=False)
        tr_frame = tk.Frame(hdr, bg=BG_MID, highlightthickness=1,
                            highlightbackground=BORDER)
        tr_frame.pack(side="right", padx=(0, 12))
        tk.Checkbutton(tr_frame, text="🔄 Show Trade Routes",
                       variable=show_routes_var,
                       command=lambda: draw(),
                       bg=BG_MID, fg=TEXT_PRIMARY, selectcolor=BG_HOVER,
                       activebackground=BG_MID, activeforeground=ACCENT,
                       font=FONT_SMALL, relief="flat", bd=0,
                       highlightthickness=0).pack(padx=8, pady=4)

        # coord display in top-right
        coord_lbl = tk.Label(hdr, text="", font=FONT_SMALL,
                             bg=BG_DARK, fg=TEXT_SECONDARY)
        coord_lbl.pack(side="right", padx=8)

        make_separator(outer).pack(fill="x", padx=24, pady=8)

        # ── Canvas ────────────────────────────────────────────────────────────
        map_frame = tk.Frame(outer, bg=BG_DARK)
        map_frame.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        canvas = tk.Canvas(map_frame, bg="#0a0e1a", highlightthickness=1,
                           highlightbackground=BORDER, cursor="crosshair")
        canvas.pack(fill="both", expand=True)

        # ── State ─────────────────────────────────────────────────────────────
        # Travian map: coords range roughly -400..+400 on both axes
        MAP_HALF   = 200          # world spans -200..+200  (401 coords wide)
        MAP_SIZE   = 401          # total world width in game coords
        CELL_BASE  = 4.0          # base pixels per game coord unit at zoom=1
        MIN_ZOOM   = 0.5
        MAX_ZOOM   = 24.0

        state = {
            "zoom":    1.0,
            "pan_x":  0.0,   # offset in canvas pixels
            "pan_y":  0.0,
            "drag_x": None,
            "drag_y": None,
        }

        # Parse village coords
        vdata = []
        coord_lookup = {}   # village_name -> (x, y)
        for v in villages:
            try:
                cx = int(v["coord_x"]); cy = int(v["coord_y"])
                vdata.append({"name": v["village_name"], "x": cx, "y": cy,
                               "capital": v.get("is_capital", "") == "1"})
                coord_lookup[v["village_name"]] = (cx, cy)
            except (ValueError, TypeError, KeyError):
                pass

        # Known (third-party) village data
        kvdata = []
        for kv in load_known_villages(self.server, self.account):
            try:
                cx = int(kv["coord_x"]); cy = int(kv["coord_y"])
                name = kv.get("name", "")
                kvdata.append({"name": name, "x": cx, "y": cy,
                                "vtype": kv.get("vtype", "")})
                coord_lookup.setdefault(name, (cx, cy))
            except (ValueError, TypeError, KeyError):
                pass

        # Collect all trade routes across all villages
        # Each entry: {sx, sy, tx, ty, wood, clay, iron, crop, active}
        all_routes = []
        for v in villages:
            vname = v["village_name"]
            if vname not in coord_lookup:
                continue
            sx, sy = coord_lookup[vname]
            for rt in load_trade_routes(self.server, self.account, vname):
                if rt.get("active","1") in ("0","false","False",""):
                    continue
                target = rt.get("target","")
                # Try own villages first, then known villages
                tc = coord_lookup.get(target)
                if tc is None:
                    for kv in load_known_villages(self.server, self.account):
                        if kv["name"] == target:
                            try:
                                tc = (int(kv["coord_x"]), int(kv["coord_y"]))
                            except (ValueError, TypeError):
                                pass
                            break
                if tc is None:
                    continue
                tx, ty = tc
                try:
                    wood = int(rt.get("wood",0) or 0)
                    clay = int(rt.get("clay",0) or 0)
                    iron = int(rt.get("iron",0) or 0)
                    crop = int(rt.get("crop",0) or 0)
                except ValueError:
                    wood = clay = iron = crop = 0
                all_routes.append({
                    "sx": sx, "sy": sy, "tx": tx, "ty": ty,
                    "wood": wood, "clay": clay, "iron": iron, "crop": crop,
                })

        # ── Coordinate transforms ──────────────────────────────────────────────
        def world_pixels():
            """Total pixel width/height of one world copy at current zoom."""
            return MAP_SIZE * CELL_BASE * state["zoom"]

        def game_to_canvas(gx, gy):
            """Convert game coord → canvas pixel (no wrapping — raw)."""
            w = canvas.winfo_width()  or 800
            h = canvas.winfo_height() or 600
            cell = CELL_BASE * state["zoom"]
            px = w / 2 + (gx * cell) + state["pan_x"]
            py = h / 2 + (-gy * cell) + state["pan_y"]   # y-flip
            return px, py

        def canvas_to_game(cx, cy):
            """Convert canvas pixel → game coord, wrapped to [-200, +200]."""
            w = canvas.winfo_width()  or 800
            h = canvas.winfo_height() or 600
            cell = CELL_BASE * state["zoom"]
            raw_x = (cx - w / 2 - state["pan_x"]) / cell
            raw_y = -((cy - h / 2 - state["pan_y"]) / cell)
            # Wrap into [-200, +200]
            gx = (raw_x + MAP_HALF) % MAP_SIZE - MAP_HALF
            gy = (raw_y + MAP_HALF) % MAP_SIZE - MAP_HALF
            return gx, gy

        # ── Draw ──────────────────────────────────────────────────────────────
        _GRID_COL       = "#1a2540"
        _CELL_COL       = "#111829"
        _AXIS_COL       = "#2a4060"
        _VILLAGE_COL    = "#27ae60"
        _CAPITAL_COL    = "#c8963e"
        _KNOWN_COL      = "#4a90d9"   # blue for third-party known villages
        _VILLAGE_HOVER  = "#58d68d"
        _LABEL_BG       = "#0f1520"
        _TOOLTIP_ID     = [None, None]

        # Trade route arrow colours
        _TR_CROP_ONLY   = "#d4c020"   # yellow  — crop only
        _TR_RES_ONLY    = "#e07820"   # orange  — wood/clay/iron only
        _TR_MIXED       = "#4090d8"   # blue    — crop + any other

        def _route_color(wood, clay, iron, crop):
            has_res  = (wood + clay + iron) > 0
            has_crop = crop > 0
            if has_crop and has_res:   return _TR_MIXED
            if has_crop:               return _TR_CROP_ONLY
            return _TR_RES_ONLY

        def _draw_arrow(x1, y1, x2, y2, color, lw=2, offset=0):
            """Draw an arrow from (x1,y1) to (x2,y2), pulling each endpoint
            inward by `offset` pixels so the line starts/ends at the square edge."""
            if offset > 0:
                import math
                dx, dy = x2 - x1, y2 - y1
                dist = math.hypot(dx, dy)
                if dist < offset * 2 + 2:
                    return   # too short to draw meaningfully
                ux, uy = dx / dist, dy / dist
                x1 += ux * offset
                y1 += uy * offset
                x2 -= ux * offset
                y2 -= uy * offset
            head = max(6, min(14, lw * 4))   # arrowhead scales with line width
            canvas.create_line(x1, y1, x2, y2,
                               fill=color, width=lw,
                               arrow=tk.LAST,
                               arrowshape=(head, head + 2, max(2, lw + 1)),
                               tags=("traderoute",))

        def _clear_tooltip():
            for tid in _TOOLTIP_ID:
                if tid:
                    canvas.delete(tid)
            _TOOLTIP_ID[0] = _TOOLTIP_ID[1] = None

        def draw():
            canvas.delete("all")
            _TOOLTIP_ID[0] = _TOOLTIP_ID[1] = None
            w = canvas.winfo_width()  or 800
            h = canvas.winfo_height() or 600
            cell  = CELL_BASE * state["zoom"]
            wpx   = world_pixels()   # pixel width of one world copy

            # How many tile copies do we need to cover the canvas?
            # At minimum zoom the world is ~401*0.5*4 ≈ 802px, always enough
            # for ±1 copies to cover any reasonable canvas.
            copies = range(-2, 3)

            # ── Grid lines (drawn once per visible tile copy) ─────────────────
            if cell >= 20:   step = 10
            elif cell >= 8:  step = 25
            elif cell >= 3:  step = 50
            else:            step = 100

            for tx in copies:
                for ty in copies:
                    # Origin pixel of this tile copy
                    ox, oy = game_to_canvas(tx * MAP_SIZE, -ty * MAP_SIZE)

                    # Only draw tile if it overlaps the canvas
                    if ox + wpx < 0 or ox > w: continue
                    if oy + wpx < 0 or oy > h: continue

                    # Per-cell grid (every 1 coord unit) — only when zoomed in enough
                    if cell >= 8:
                        for gx in range(-MAP_HALF, MAP_HALF + 1):
                            px = ox + (gx + MAP_HALF) * cell
                            if px < 0 or px > w: continue
                            canvas.create_line(px, max(0, oy), px, min(h, oy + wpx),
                                               fill=_CELL_COL, width=1)
                        for gy in range(-MAP_HALF, MAP_HALF + 1):
                            py = oy + (MAP_HALF - gy) * cell
                            if py < 0 or py > h: continue
                            canvas.create_line(max(0, ox), py, min(w, ox + wpx), py,
                                               fill=_CELL_COL, width=1)

                    # Major grid lines
                    for gx in range(-MAP_HALF, MAP_HALF + 1, step):
                        px = ox + (gx + MAP_HALF) * cell
                        if px < 0 or px > w: continue
                        col = _AXIS_COL if gx == 0 else _GRID_COL
                        lw  = 2 if gx == 0 else 1
                        canvas.create_line(px, 0, px, h, fill=col, width=lw)
                        if cell >= 4 and tx == 0 and abs(gx) % (step * 2) == 0:
                            canvas.create_text(px + 2, 4, text=str(gx),
                                               font=FONT_TINY, fill=TEXT_MUTED, anchor="nw")

                    for gy in range(-MAP_HALF, MAP_HALF + 1, step):
                        py = oy + (MAP_HALF - gy) * cell
                        if py < 0 or py > h: continue
                        col = _AXIS_COL if gy == 0 else _GRID_COL
                        lw  = 2 if gy == 0 else 1
                        canvas.create_line(0, py, w, py, fill=col, width=lw)
                        if cell >= 4 and ty == 0 and abs(gy) % (step * 2) == 0:
                            canvas.create_text(4, py - 2, text=str(gy),
                                               font=FONT_TINY, fill=TEXT_MUTED, anchor="sw")

                    # World border rectangle
                    x0 = ox + 0          * cell
                    y0 = oy + 0          * cell
                    x1 = ox + MAP_SIZE   * cell
                    y1 = oy + MAP_SIZE   * cell
                    canvas.create_rectangle(x0, y0, x1, y1,
                                            outline="#2a4060", width=2, fill="")

            # ── Trade route arrows ────────────────────────────────────────────
            r = max(2, min(9, cell * 0.38))   # needed for offset and village squares

            if show_routes_var.get():
                for rt in all_routes:
                    for tx in copies:
                        for ty in copies:
                            sx_px, sy_px = game_to_canvas(rt["sx"] + tx * MAP_SIZE,
                                                          rt["sy"] + ty * MAP_SIZE)
                            tx_px, ty_px = game_to_canvas(rt["tx"] + tx * MAP_SIZE,
                                                          rt["ty"] + ty * MAP_SIZE)
                            # Only draw if either endpoint is near the canvas
                            if ((-20 < sx_px < w + 20 or -20 < tx_px < w + 20) and
                                (-20 < sy_px < h + 20 or -20 < ty_px < h + 20)):
                                col = _route_color(rt["wood"], rt["clay"],
                                                   rt["iron"], rt["crop"])
                                lw = max(1, min(4, int(cell * 0.3)))
                                _draw_arrow(sx_px, sy_px, tx_px, ty_px,
                                            col, lw, offset=r)

            # ── Village squares (also drawn for each tile copy) ───────────────
            for v in vdata:
                for tx in copies:
                    for ty in copies:
                        px, py = game_to_canvas(v["x"] + tx * MAP_SIZE,
                                                v["y"] + ty * MAP_SIZE)
                        if -r * 2 < px < w + r * 2 and -r * 2 < py < h + r * 2:
                            col = _CAPITAL_COL if v["capital"] else _VILLAGE_COL
                            tag = ("village", v["name"]) if tx == 0 and ty == 0 else ("village_ghost",)
                            canvas.create_rectangle(px - r, py - r, px + r, py + r,
                                                    fill=col, outline="#000", width=1,
                                                    tags=tag)
                            if cell >= 10:
                                canvas.create_text(px, py - r - 3, text=v["name"],
                                                   font=FONT_TINY,
                                                   fill=_CAPITAL_COL if v["capital"] else TEXT_SECONDARY,
                                                   anchor="s", tags=("vlabel",))

            # ── Known (third-party) village squares ───────────────────────────
            for v in kvdata:
                for tx in copies:
                    for ty in copies:
                        px, py = game_to_canvas(v["x"] + tx * MAP_SIZE,
                                                v["y"] + ty * MAP_SIZE)
                        if -r * 2 < px < w + r * 2 and -r * 2 < py < h + r * 2:
                            tag = ("village", v["name"]) if tx == 0 and ty == 0 else ("village_ghost",)
                            canvas.create_rectangle(px - r, py - r, px + r, py + r,
                                                    fill=_KNOWN_COL, outline="#000", width=1,
                                                    tags=tag)
                            if cell >= 10:
                                label = v["name"]
                                if v["vtype"]:
                                    label += f" [{v['vtype']}]"
                                canvas.create_text(px, py - r - 3, text=label,
                                                   font=FONT_TINY,
                                                   fill=_KNOWN_COL,
                                                   anchor="s", tags=("vlabel",))

            # Ensure village squares and labels always sit above trade route arrows
            canvas.tag_raise("village_ghost")
            canvas.tag_raise("village")
            canvas.tag_raise("vlabel")

        # ── Tooltip ───────────────────────────────────────────────────────────
        def show_tooltip(px, py, text):
            _clear_tooltip()
            pad = 4
            t = canvas.create_text(px + 12, py - 12, text=text,
                                   font=FONT_SMALL, fill=TEXT_PRIMARY, anchor="sw")
            bb = canvas.bbox(t)
            if bb:
                r = canvas.create_rectangle(bb[0]-pad, bb[1]-pad,
                                            bb[2]+pad, bb[3]+pad,
                                            fill=_LABEL_BG, outline=BORDER)
                canvas.tag_raise(t, r)
                _TOOLTIP_ID[0] = r
                _TOOLTIP_ID[1] = t

        # ── Event handlers ────────────────────────────────────────────────────
        def on_configure(e):
            draw()

        def on_scroll(e):
            # Windows: e.delta = ±120; Linux: Button-4/5
            factor = 1.15 if (e.delta > 0 or e.num == 4) else (1 / 1.15)
            new_zoom = max(MIN_ZOOM, min(MAX_ZOOM, state["zoom"] * factor))
            if new_zoom == state["zoom"]:
                return
            # Zoom toward the cursor position
            gx, gy  = canvas_to_game(e.x, e.y)
            state["zoom"] = new_zoom
            nx, ny  = game_to_canvas(gx, gy)
            state["pan_x"] += e.x - nx
            state["pan_y"] += e.y - ny
            draw()

        def on_drag_start(e):
            state["drag_x"] = e.x
            state["drag_y"] = e.y
            canvas.config(cursor="fleur")

        def on_drag(e):
            if state["drag_x"] is None:
                return
            state["pan_x"] += e.x - state["drag_x"]
            state["pan_y"] += e.y - state["drag_y"]
            state["drag_x"] = e.x
            state["drag_y"] = e.y
            draw()

        def on_drag_end(e):
            state["drag_x"] = None
            state["drag_y"] = None
            canvas.config(cursor="crosshair")

        def on_motion(e):
            gx, gy = canvas_to_game(e.x, e.y)
            coord_lbl.config(text=f"({int(round(gx))} | {int(round(gy))})")
            # Check village hover
            items = canvas.find_overlapping(e.x - 8, e.y - 8, e.x + 8, e.y + 8)
            hit = None
            for item in items:
                tags = canvas.gettags(item)
                if "village" in tags:
                    hit = tags[1] if len(tags) > 1 else None
                    break
            if hit:
                show_tooltip(e.x, e.y, hit)
            else:
                _clear_tooltip()

        canvas.bind("<Configure>",        on_configure)
        canvas.bind("<MouseWheel>",        on_scroll)
        canvas.bind("<Button-4>",          on_scroll)
        canvas.bind("<Button-5>",          on_scroll)
        canvas.bind("<ButtonPress-1>",     on_drag_start)
        canvas.bind("<B1-Motion>",         on_drag)
        canvas.bind("<ButtonRelease-1>",   on_drag_end)
        canvas.bind("<Motion>",            on_motion)

        # Auto-center on our villages if we have any
        def _initial_center():
            if vdata:
                avg_x = sum(v["x"] for v in vdata) / len(vdata)
                avg_y = sum(v["y"] for v in vdata) / len(vdata)
                w = canvas.winfo_width()  or 800
                h = canvas.winfo_height() or 600
                cell = CELL_BASE * state["zoom"]
                state["pan_x"] = -(avg_x * cell)
                state["pan_y"] = avg_y * cell
            draw()

        canvas.after(50, _initial_center)

    def _show_troop_locations(self):
        self._clear_center()
        villages    = load_villages(self.server, self.account)
        troop_names = get_tribe_troops(self.tribe)

        outer = tk.Frame(self.center, bg=BG_DARK)
        outer.pack(fill="both", expand=True)

        hdr = tk.Frame(outer, bg=BG_DARK)
        hdr.pack(fill="x", padx=24, pady=(24, 0))
        tk.Label(hdr, text="Net Troops",
                 font=FONT_TITLE, bg=BG_DARK, fg=TEXT_PRIMARY).pack(side="left")
        tk.Label(hdr, text="  —  native_in + foreign_in per village",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(side="left", pady=(8, 0))
        make_separator(outer).pack(fill="x", padx=24, pady=10)

        if not villages or not troop_names:
            tk.Label(outer, text="No village or troop data found.",
                     font=FONT_BODY, bg=BG_DARK, fg=TEXT_MUTED).pack(padx=24, anchor="w")
            return

        # Load net troops per village
        rows = []
        account_totals = {t: 0 for t in troop_names}
        for v in villages:
            vname = v["village_name"]
            td = load_troop_data(self.server, self.account, vname, troop_names)
            net = {t: td["native_in"].get(t, 0) + td["foreign_in"].get(t, 0)
                   for t in troop_names}
            rows.append((vname, net))
            for t in troop_names:
                account_totals[t] += net[t]

        scroll_outer, inner = scrollable_frame(outer)
        scroll_outer.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        n_troops = len(troop_names)
        tbl = tk.Frame(inner, bg=BG_DARK)
        tbl.pack(fill="x")
        tbl.columnconfigure(0, minsize=180)
        for c in range(1, n_troops + 1):
            tbl.columnconfigure(c, minsize=80, uniform="nt")

        # Header row
        tk.Label(tbl, text="Village", font=("Consolas", 9, "bold"),
                 bg=BG_MID, fg=TEXT_MUTED, anchor="w", padx=6, pady=3
                 ).grid(row=0, column=0, sticky="nsew", padx=(0,1), pady=(0,1))
        for ci, tname in enumerate(troop_names):
            disp = tname if len(tname) <= 12 else tname[:11] + "…"
            lbl = tk.Label(tbl, text=disp, font=("Consolas", 9, "bold"),
                           bg=BG_MID, fg=ACCENT, anchor="center", padx=4, pady=3)
            lbl.grid(row=0, column=ci + 1, sticky="nsew", padx=(0,1), pady=(0,1))
            lbl.bind("<Enter>", lambda e, w=lbl, f=tname: w.config(text=f))
            lbl.bind("<Leave>", lambda e, w=lbl, d=disp: w.config(text=d))
        tk.Frame(tbl, bg=BORDER, height=1).grid(
            row=1, column=0, columnspan=n_troops + 1, sticky="ew", pady=(0,1))

        # Village rows
        for i, (vname, net) in enumerate(rows):
            r  = i + 2
            bg = BG_MID if i % 2 == 0 else BG_PANEL
            tk.Label(tbl, text=vname, font=FONT_SMALL, bg=bg,
                     fg=TEXT_PRIMARY, anchor="w", padx=8, pady=3
                     ).grid(row=r, column=0, sticky="nsew", padx=(0,1), pady=(0,1))
            for ci, tname in enumerate(troop_names):
                val = net[tname]
                tk.Label(tbl, text=str(val) if val else "—",
                         font=FONT_SMALL, bg=bg,
                         fg=COL_FULL_GREEN if val else TEXT_MUTED,
                         anchor="center", pady=3
                         ).grid(row=r, column=ci + 1, sticky="nsew",
                                padx=(0,1), pady=(0,1))

        # Totals row
        tk.Frame(tbl, bg=ACCENT_DIM, height=1).grid(
            row=len(rows) + 2, column=0, columnspan=n_troops + 1,
            sticky="ew", pady=(2,1))
        tr = len(rows) + 3
        tk.Label(tbl, text="Account Total", font=("Consolas", 9, "bold"),
                 bg=BG_HOVER, fg=ACCENT, anchor="w", padx=8, pady=4
                 ).grid(row=tr, column=0, sticky="nsew", padx=(0,1), pady=(0,1))
        for ci, tname in enumerate(troop_names):
            val = account_totals[tname]
            tk.Label(tbl, text=str(val) if val else "—",
                     font=("Consolas", 9, "bold"), bg=BG_HOVER,
                     fg=COL_FULL_GREEN if val else TEXT_MUTED,
                     anchor="center", pady=4
                     ).grid(row=tr, column=ci + 1, sticky="nsew",
                            padx=(0,1), pady=(0,1))

    def _show_net_production(self):
        self._clear_center()
        villages = load_villages(self.server, self.account)

        outer = tk.Frame(self.center, bg=BG_DARK)
        outer.pack(fill="both", expand=True)

        hdr = tk.Frame(outer, bg=BG_DARK)
        hdr.pack(fill="x", padx=24, pady=(24, 0))
        tk.Label(hdr, text="Net Production",
                 font=FONT_TITLE, bg=BG_DARK, fg=TEXT_PRIMARY).pack(side="left")
        tk.Label(hdr, text="  —  SUM /hr per village (production + trade − consumption − queues − celebration)",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(side="left", pady=(8, 0))
        make_separator(outer).pack(fill="x", padx=24, pady=10)

        if not villages:
            tk.Label(outer, text="No villages found.",
                     font=FONT_BODY, bg=BG_DARK, fg=TEXT_MUTED).pack(padx=24, anchor="w")
            return

        # ── Pre-load shared data ──────────────────────────────────────────────
        use_parsed  = load_option("prod_data_source", "Village Data") == "Parsed"
        parsed_prod = load_parsed_production(self.server, self.account) if use_parsed else {}
        troop_names = get_tribe_troops(self.tribe)
        troop_stats = get_troop_stats(self.tribe)
        all_villages_set = {v["village_name"] for v in villages}

        try:
            speed_mult = float(self.speed.replace("x", ""))
        except (ValueError, AttributeError):
            speed_mult = 1.0

        upkeep_map = {}
        troops_csv = DATA_DIR / "general" / "1x" / "troops.csv"
        if troops_csv.exists():
            with open(troops_csv, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if row["tribe"].strip().lower() == self.tribe.lower():
                        try:
                            upkeep_map[row["name"].strip()] = int(row["crop_upkeep"])
                        except ValueError:
                            upkeep_map[row["name"].strip()] = 1

        cel_table = {}
        cel_csv = DATA_DIR / "general" / "1x" / "celebrations.csv"
        if cel_csv.exists():
            with open(cel_csv, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    try:
                        cel_table[int(row["townhall_level"])] = row
                    except (ValueError, KeyError):
                        pass

        village_roles = load_village_roles(self.server, self.account)

        # ── Compute SUM for every village ─────────────────────────────────────
        rows = []
        account_totals = {"wood": 0, "clay": 0, "iron": 0, "crop": 0}

        for v in villages:
            vname = v["village_name"]

            # Production
            if use_parsed:
                prod = parsed_prod.get(vname, {"wood":0,"clay":0,"iron":0,"crop":0})
            else:
                prod = calculate_village_production(self.server, self.account, vname)

            # Trade
            trade = {"wood":0,"clay":0,"iron":0,"crop":0}
            for rt in load_trade_routes(self.server, self.account, vname):
                if rt.get("active","1") in ("0","false","False",""): continue
                try: freq = max(1, int(rt.get("frequency_min",60) or 60))
                except ValueError: freq = 60
                f = 60.0 / freq
                for k in trade:
                    try: trade[k] -= round(int(rt.get(k,0) or 0) * f)
                    except ValueError: pass
            for ov in villages:
                if ov["village_name"] == vname: continue
                for rt in load_trade_routes(self.server, self.account, ov["village_name"]):
                    if rt.get("target","") != vname: continue
                    if rt.get("active","1") in ("0","false","False",""): continue
                    try: freq = max(1, int(rt.get("frequency_min",60) or 60))
                    except ValueError: freq = 60
                    f = 60.0 / freq
                    for k in trade:
                        try: trade[k] += round(int(rt.get(k,0) or 0) * f)
                        except ValueError: pass

            # Celebration
            vflags   = village_roles.get(vname, {})
            is_small = vflags.get("Small","0") == "1"
            is_large = vflags.get("Large","0") == "1"
            current_blds = load_current_buildings(self.server, self.account, vname)
            th_level = 0
            for slot in current_blds.values():
                if slot.get("building","").lower() == "townhall":
                    try: th_level = int(slot.get("level",0))
                    except ValueError: pass
                    break
            if is_large and th_level < 10: th_level = 0
            celebration = {"wood":0,"clay":0,"iron":0,"crop":0}
            if (is_small or is_large) and th_level > 0:
                cel_row = cel_table.get(th_level, {})
                prefix = "small" if is_small else "great"
                for k in ("wood","clay","iron","crop"):
                    try: celebration[k] = -round(float(cel_row.get(f"{prefix}_{k}_hr",0) or 0))
                    except ValueError: pass

            # Consumption
            consumption = {"wood":0,"clay":0,"iron":0,"crop":0}
            td = load_troop_data(self.server, self.account, vname, troop_names)
            for t in troop_names:
                present = td["native_in"].get(t,0) + td["foreign_in"].get(t,0)
                consumption["crop"] -= present * upkeep_map.get(t, 1)

            # Troop queues
            queue_cost = {"wood":0,"clay":0,"iron":0,"crop":0}
            saved_q = load_troop_queues(self.server, self.account, vname)
            for slot in current_blds.values():
                bname = slot.get("building","")
                blvl  = slot.get("level",0)
                if bname not in PRODUCTION_BUILDINGS: continue
                tname = saved_q.get(bname,"")
                if not tname: continue
                c = calc_queue_hourly_cost(bname, blvl, tname, troop_stats, speed_mult)
                for k in queue_cost: queue_cost[k] -= c[k]

            net = {k: prod[k]+trade[k]+celebration[k]+consumption[k]+queue_cost[k]
                   for k in ("wood","clay","iron","crop")}
            rows.append((vname, net))
            for k in account_totals: account_totals[k] += net[k]

        # ── Grid table ────────────────────────────────────────────────────────
        scroll_outer, inner = scrollable_frame(outer)
        scroll_outer.pack(fill="both", expand=True, padx=24, pady=(0,16))

        COLS = [
            (1, "🌲 Wood", "wood",  "#7daa6f"),
            (2, "🧱 Clay", "clay",  "#b87c4c"),
            (3, "⚙ Iron",  "iron",  "#8aabcc"),
            (4, "🌾 Crop", "crop",  "#c8b84a"),
        ]

        tbl = tk.Frame(inner, bg=BG_DARK)
        tbl.pack(fill="x")
        tbl.columnconfigure(0, minsize=200)
        for c in range(1,5):
            tbl.columnconfigure(c, minsize=100, uniform="res")

        def gl(row, col, text, bg, fg, bold=False, anchor="center"):
            tk.Label(tbl, text=text,
                     font=("Consolas",9,"bold") if bold else FONT_SMALL,
                     bg=bg, fg=fg, anchor=anchor, padx=8, pady=4
                     ).grid(row=row, column=col, sticky="nsew", padx=(0,1), pady=(0,1))

        gl(0,0,"Village", BG_MID, TEXT_MUTED, bold=True, anchor="w")
        for ci, label, _, color in COLS:
            gl(0, ci, label, BG_MID, color, bold=True)
        tk.Frame(tbl, bg=BORDER, height=1).grid(
            row=1, column=0, columnspan=5, sticky="ew", pady=(0,1))

        for i, (vname, net) in enumerate(rows):
            r  = i + 2
            bg = BG_MID if i % 2 == 0 else BG_PANEL
            gl(r, 0, vname, bg, TEXT_PRIMARY, anchor="w")
            for ci, _, key, color in COLS:
                val = net[key]
                fg  = COL_FULL_GREEN if val > 0 else COL_RED if val < 0 else TEXT_MUTED
                gl(r, ci, f"{val:+,}" if val != 0 else "0", bg, fg)

        # Account totals row
        tk.Frame(tbl, bg=ACCENT_DIM, height=1).grid(
            row=len(rows)+2, column=0, columnspan=5, sticky="ew", pady=(2,1))
        tr = len(rows)+3
        gl(tr, 0, "Account Total", BG_HOVER, ACCENT, bold=True, anchor="w")
        for ci, _, key, color in COLS:
            val = account_totals[key]
            fg  = COL_FULL_GREEN if val > 0 else COL_RED if val < 0 else TEXT_MUTED
            gl(tr, ci, f"{val:+,}" if val != 0 else "0", BG_HOVER, fg, bold=True)

        src = "parsed data" if use_parsed else "village data"
        tk.Label(inner, text=f"Production source: {src}  ·  includes trade, celebrations, troop upkeep and queues",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED
                 ).pack(anchor="w", padx=4, pady=(8,4))

    # ── Statistics views ──────────────────────────────────────────────────────

    def _show_farm_top_stats(self):
        self._clear_center()
        outer = tk.Frame(self.center, bg=BG_DARK)
        outer.pack(fill="both", expand=True)

        hdr = tk.Frame(outer, bg=BG_DARK)
        hdr.pack(fill="x", padx=24, pady=(24, 0))
        tk.Label(hdr, text="Farm Top Stats",
                 font=FONT_TITLE, bg=BG_DARK, fg=TEXT_PRIMARY).pack(side="left")
        make_separator(outer).pack(fill="x", padx=24, pady=12)

        card = tk.Frame(outer, bg=BG_PANEL)
        card.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        inner = tk.Frame(card, bg=BG_PANEL)
        inner.pack(expand=True)
        tk.Label(inner, text="📊", font=("Georgia", 32),
                 bg=BG_PANEL, fg=TEXT_MUTED).pack(pady=(60, 8))
        tk.Label(inner, text="Farm Top Stats", font=FONT_HEADING,
                 bg=BG_PANEL, fg=TEXT_SECONDARY).pack()
        tk.Label(inner, text="Coming soon — statistics on farming activity across villages.",
                 font=FONT_SMALL, bg=BG_PANEL, fg=TEXT_MUTED,
                 wraplength=440, justify="center").pack(pady=(6, 0))

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
        view = TradeRoutesView(
            self.center, self.server, self.account,
            village, self.tribe, self.speed, self.is_archived)
        view.pack(fill="both", expand=True)

    def _show_troops(self, village):
        self._clear_center()
        view = VillageTroopsView(
            self.center, self.server, self.account,
            village, self.tribe, self.is_archived)
        view.pack(fill="both", expand=True)

    def _show_resource_layout(self, village):
        self._clear_center()
        vdata      = next((v for v in load_villages(self.server, self.account)
                           if v["village_name"] == village), {})
        is_capital = vdata.get("is_capital", "") == "1"
        view = VillageResourceLayoutView(
            self.center, self.server, self.account,
            village, self.is_archived,
            on_save=lambda: self._refresh_village_list(),
            is_capital=is_capital)
        view.pack(fill="both", expand=True)

    def _show_troop_queues(self, village):
        self._clear_center()
        outer = tk.Frame(self.center, bg=BG_DARK)
        outer.pack(fill="both", expand=True)

        hdr = tk.Frame(outer, bg=BG_DARK)
        hdr.pack(fill="x", padx=24, pady=(24, 0))
        tk.Label(hdr, text=f"{village}  —  Troop Queues",
                 font=FONT_TITLE, bg=BG_DARK, fg=TEXT_PRIMARY).pack(side="left")
        if not self.is_archived:
            status_lbl = tk.Label(hdr, text="", font=FONT_SMALL,
                                  bg=BG_DARK, fg=COL_FULL_GREEN, width=20, anchor="w")
            status_lbl.pack(side="left", padx=(16, 0))
            styled_button(hdr, "💾  Save", accent=True,
                          command=lambda: _save()).pack(side="left")
        make_separator(outer).pack(fill="x", padx=24, pady=10)

        # Collect training buildings present in this village
        current_buildings = load_current_buildings(self.server, self.account, village)
        present = {}   # building_name -> level
        for slot in current_buildings.values():
            bname = slot.get("building", "")
            blvl  = slot.get("level", 0)
            if bname in PRODUCTION_BUILDINGS:
                present[bname] = blvl

        if not present:
            tk.Label(outer,
                     text="No production buildings found in this village's buildings data.\n"
                          "Add buildings via the Buildings menu first.",
                     font=FONT_BODY, bg=BG_DARK, fg=TEXT_MUTED).pack(padx=24, anchor="w")
            return

        troop_stats  = get_troop_stats(self.tribe)
        saved_queues = load_troop_queues(self.server, self.account, village)
        queue_vars   = {}   # building_name -> StringVar

        try:
            speed_mult = float(self.speed.replace("x", ""))
        except (ValueError, AttributeError):
            speed_mult = 1.0

        scroll_outer, inner = scrollable_frame(outer)
        scroll_outer.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        # Header note
        tk.Label(inner, text="Select the troop type being trained in each building.",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(anchor="w", pady=(0, 8))

        tbl = tk.Frame(inner, bg=BG_DARK)
        tbl.pack(fill="x")
        tbl.columnconfigure(0, minsize=180)
        tbl.columnconfigure(1, minsize=60, uniform="bld")
        tbl.columnconfigure(2, minsize=200)
        tbl.columnconfigure(3, minsize=340)

        def gh(col, text):
            tk.Label(tbl, text=text, font=("Consolas", 9, "bold"),
                     bg=BG_MID, fg=TEXT_MUTED, anchor="w" if col == 0 else "center",
                     padx=6, pady=3
                     ).grid(row=0, column=col, sticky="nsew", padx=(0,1), pady=(0,1))

        gh(0, "Building"); gh(1, "Level"); gh(2, "Queued Troop"); gh(3, "Cost /hr")
        tk.Frame(tbl, bg=BORDER, height=1).grid(
            row=1, column=0, columnspan=4, sticky="ew", pady=(0,1))

        cost_lbls = {}   # building_name -> Label showing hourly cost

        def _update_cost(bname):
            tname = queue_vars[bname].get()
            blvl  = present[bname]
            if tname and tname != "— None —":
                c = calc_queue_hourly_cost(bname, blvl, tname, troop_stats, speed_mult)
                txt = (f"🌲{c['wood']:,}  🧱{c['clay']:,}  "
                       f"⚙{c['iron']:,}  🌾{c['crop']:,}  /hr")
            else:
                txt = "—"
            cost_lbls[bname].config(text=txt)

        # Keep PRODUCTION_BUILDINGS order, only show present ones
        for i, bname in enumerate([b for b in PRODUCTION_BUILDINGS if b in present]):
            r   = i + 2
            bg  = BG_MID if i % 2 == 0 else BG_PANEL
            blvl = present[bname]
            avail_troops = troops_for_building(bname, self.tribe)
            opts   = ["— None —"] + avail_troops
            saved  = saved_queues.get(bname, "")
            cur    = saved if saved in avail_troops else "— None —"

            tk.Label(tbl, text=bname, font=FONT_SMALL, bg=bg,
                     fg=TEXT_PRIMARY, anchor="w", padx=6, pady=4
                     ).grid(row=r, column=0, sticky="nsew", padx=(0,1), pady=(0,1))
            tk.Label(tbl, text=str(blvl), font=FONT_SMALL, bg=bg,
                     fg=TEXT_SECONDARY, anchor="center", padx=4, pady=4
                     ).grid(row=r, column=1, sticky="nsew", padx=(0,1), pady=(0,1))

            t_var = tk.StringVar(value=cur)
            queue_vars[bname] = t_var
            state = "disabled" if self.is_archived else "readonly"
            styled_combo(tbl, t_var, opts, width=22, state=state
                         ).grid(row=r, column=2, sticky="nsew", padx=(0,1), pady=(0,1))

            cost_lbl = tk.Label(tbl, text="—", font=FONT_SMALL,
                                bg=bg, fg=TEXT_SECONDARY, anchor="w", padx=8, pady=4)
            cost_lbl.grid(row=r, column=3, sticky="nsew", padx=(0,1), pady=(0,1))
            cost_lbls[bname] = cost_lbl
            t_var.trace_add("write", lambda *_, b=bname: _update_cost(b))
            _update_cost(bname)

        def _save():
            queues = {}
            for bname, var in queue_vars.items():
                val = var.get()
                queues[bname] = val if val != "— None —" else ""
            save_troop_queues(self.server, self.account, village, queues)
            status_lbl.config(text="✓ Saved", fg=COL_FULL_GREEN)
            fade_label(status_lbl, after_ms=3000)

    def _show_net_resources(self, village):
        self._clear_center()
        outer = tk.Frame(self.center, bg=BG_DARK)
        outer.pack(fill="both", expand=True)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(outer, bg=BG_DARK)
        hdr.pack(fill="x", padx=24, pady=(24, 0))
        tk.Label(hdr, text=f"{village}  —  Net Resources",
                 font=FONT_TITLE, bg=BG_DARK, fg=TEXT_PRIMARY).pack(side="left")
        src_note = load_option("prod_data_source", "Village Data")
        tk.Label(hdr, text=f"  (production: {src_note})",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(side="left", pady=(8, 0))
        make_separator(outer).pack(fill="x", padx=24, pady=10)

        # ── Gather data ───────────────────────────────────────────────────────

        # 1. Production
        use_parsed = src_note == "Parsed"
        if use_parsed:
            parsed = load_parsed_production(self.server, self.account)
            raw_prod = parsed.get(village, {"wood": 0, "clay": 0, "iron": 0, "crop": 0})
            prod = {k: raw_prod[k] for k in ("wood", "clay", "iron", "crop")}
        else:
            prod = calculate_village_production(self.server, self.account, village,
                                                gold_bonus=False)

        # 2. Trade (normalised to /hr)
        trade = {"wood": 0, "clay": 0, "iron": 0, "crop": 0}
        all_villages = {v["village_name"] for v in load_villages(self.server, self.account)}
        for route in load_trade_routes(self.server, self.account, village):
            if route.get("active", "1") in ("0", "false", "False", ""):
                continue
            try:
                freq_min = max(1, int(route.get("frequency_min", 60) or 60))
            except ValueError:
                freq_min = 60
            factor = 60.0 / freq_min   # normalise to per-hour
            for key in ("wood", "clay", "iron", "crop"):
                try:
                    trade[key] -= round(int(route.get(key, 0) or 0) * factor)
                except ValueError:
                    pass

        # Incoming: routes from other villages whose target == this village
        for vname in all_villages:
            if vname == village:
                continue
            for route in load_trade_routes(self.server, self.account, vname):
                if route.get("target", "") != village:
                    continue
                if route.get("active", "1") in ("0", "false", "False", ""):
                    continue
                try:
                    freq_min = max(1, int(route.get("frequency_min", 60) or 60))
                except ValueError:
                    freq_min = 60
                factor = 60.0 / freq_min
                for key in ("wood", "clay", "iron", "crop"):
                    try:
                        trade[key] += round(int(route.get(key, 0) or 0) * factor)
                    except ValueError:
                        pass

        # 3. Celebration cost (per hour) based on Small/Large flag + Townhall level
        # Data from travian_data/general/1x/celebrations.csv (per-level per-hour costs)
        village_roles = load_village_roles(self.server, self.account)
        vflags        = village_roles.get(village, {})
        is_small      = vflags.get("Small", "0") == "1"
        is_large      = vflags.get("Large", "0") == "1"

        # Load celebration table
        cel_table = {}   # townhall_level(int) -> {small_*_hr, great_*_hr}
        cel_csv = DATA_DIR / "general" / "1x" / "celebrations.csv"
        if cel_csv.exists():
            with open(cel_csv, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    try:
                        lvl = int(row["townhall_level"])
                        cel_table[lvl] = row
                    except (ValueError, KeyError):
                        pass

        # Get Townhall level from village's current buildings (0 = not built)
        current_buildings = load_current_buildings(self.server, self.account, village)
        th_level = 0
        for slot_data in current_buildings.values():
            if slot_data.get("building", "").lower() == "townhall":
                try:
                    th_level = int(slot_data.get("level", 0))
                except ValueError:
                    th_level = 0
                break

        # Clamp great celebration to minimum level 10
        if is_large and 0 < th_level < 10:
            th_level = 0   # treat as unavailable

        def _get_celebration(level: int) -> dict:
            if level == 0:
                return {"wood": 0, "clay": 0, "iron": 0, "crop": 0}
            row = cel_table.get(level, {})
            if is_small:
                return {
                    "wood": -round(float(row.get("small_wood_hr", 0) or 0)),
                    "clay": -round(float(row.get("small_clay_hr", 0) or 0)),
                    "iron": -round(float(row.get("small_iron_hr", 0) or 0)),
                    "crop": -round(float(row.get("small_crop_hr", 0) or 0)),
                }
            elif is_large:
                return {
                    "wood": -round(float(row.get("great_wood_hr", 0) or 0)),
                    "clay": -round(float(row.get("great_clay_hr", 0) or 0)),
                    "iron": -round(float(row.get("great_iron_hr", 0) or 0)),
                    "crop": -round(float(row.get("great_crop_hr", 0) or 0)),
                }
            return {"wood": 0, "clay": 0, "iron": 0, "crop": 0}

        if is_small:
            cel_label = f"Celebration (Small, TH{th_level})" if th_level else "Celebration (Small, no TH)"
        elif is_large:
            cel_label = f"Celebration (Large, TH{th_level})" if th_level else "Celebration (Large, no TH)"
        else:
            cel_label = "Celebration"

        # 4. Troop crop consumption (always shown)
        upkeep_map = {}
        troops_csv = DATA_DIR / "general" / "1x" / "troops.csv"
        if troops_csv.exists():
            with open(troops_csv, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if row["tribe"].strip().lower() == self.tribe.lower():
                        try:
                            upkeep_map[row["name"].strip()] = int(row["crop_upkeep"])
                        except ValueError:
                            upkeep_map[row["name"].strip()] = 1

        troop_names = get_tribe_troops(self.tribe)
        troop_data  = load_troop_data(self.server, self.account, village, troop_names)
        consumption = {"wood": 0, "clay": 0, "iron": 0, "crop": 0}
        for t in troop_names:
            present = (troop_data["native_in"].get(t, 0) +
                       troop_data["foreign_in"].get(t, 0))
            consumption["crop"] -= present * upkeep_map.get(t, 1)

        # ── Table ─────────────────────────────────────────────────────────────
        table_container = tk.Frame(outer, bg=BG_DARK)
        table_container.pack(fill="both", expand=True)

        COLS = [
            (1, "🌲 Wood", "wood",  "#7daa6f"),
            (2, "🧱 Clay", "clay",  "#b87c4c"),
            (3, "⚙ Iron",  "iron",  "#8aabcc"),
            (4, "🌾 Crop", "crop",  "#c8b84a"),
        ]

        celebration = _get_celebration(th_level)

        # 5. Troop queue cost /hr (sum across all production buildings)
        troop_stats  = get_troop_stats(self.tribe)
        saved_queues = load_troop_queues(self.server, self.account, village)
        current_blds = load_current_buildings(self.server, self.account, village)
        try:
            speed_mult = float(self.speed.replace("x", ""))
        except (ValueError, AttributeError):
            speed_mult = 1.0

        queue_cost = {"wood": 0, "clay": 0, "iron": 0, "crop": 0}
        for slot in current_blds.values():
            bname = slot.get("building", "")
            blvl  = slot.get("level", 0)
            if bname not in PRODUCTION_BUILDINGS:
                continue
            tname = saved_queues.get(bname, "")
            if not tname:
                continue
            c = calc_queue_hourly_cost(bname, blvl, tname, troop_stats, speed_mult)
            for k in queue_cost:
                queue_cost[k] -= c[k]

        totals = {k: prod[k] + trade[k] + celebration[k] + consumption[k] + queue_cost[k]
                  for k in ("wood","clay","iron","crop")}

        ROWS = [
            ("Production",   prod,       BG_PANEL),
            ("Trade",        trade,      BG_MID),
            (cel_label,      celebration,BG_PANEL),
            ("Consumption",  consumption,BG_MID),
            ("Troop Queues", queue_cost, BG_PANEL),
        ]

        tbl = tk.Frame(table_container, bg=BG_DARK)
        tbl.pack(fill="x", padx=24)
        tbl.columnconfigure(0, minsize=220)
        for c in range(1, 5):
            tbl.columnconfigure(c, minsize=110, uniform="res")

        def gl(row, col, text, bg, fg, bold=False, anchor="center"):
            tk.Label(tbl, text=text,
                     font=("Consolas", 9, "bold") if bold else FONT_SMALL,
                     bg=bg, fg=fg, anchor=anchor, padx=8, pady=5
                     ).grid(row=row, column=col, sticky="nsew",
                            padx=(0, 1), pady=(0, 1))

        gl(0, 0, "", BG_MID, TEXT_MUTED, bold=True, anchor="w")
        for ci, label, _, color in COLS:
            gl(0, ci, label, BG_MID, color, bold=True)
        tk.Frame(tbl, bg=BORDER, height=1).grid(
            row=1, column=0, columnspan=5, sticky="ew", pady=(0, 1))

        for ri, (row_label, data, bg) in enumerate(ROWS):
            r = ri + 2
            row_fg = TEXT_MUTED if row_label == "Celebration" \
                     and not is_small and not is_large else TEXT_SECONDARY
            gl(r, 0, row_label, bg, row_fg, anchor="w")
            for ci, _, key, color in COLS:
                val = data[key]
                if val == 0:
                    gl(r, ci, "—", bg, TEXT_MUTED)
                elif val > 0:
                    gl(r, ci, f"+{val:,}" if row_label != "Production" else f"{val:,}",
                       bg, color)
                else:
                    gl(r, ci, f"{val:,}", bg, COL_RED)

        sep_r = len(ROWS) + 2
        sum_r = len(ROWS) + 3
        tk.Frame(tbl, bg=ACCENT_DIM, height=1).grid(
            row=sep_r, column=0, columnspan=5, sticky="ew", pady=(2, 1))
        gl(sum_r, 0, "SUM /hr", BG_HOVER, ACCENT, bold=True, anchor="w")
        for ci, _, key, color in COLS:
            val = totals[key]
            fg  = COL_FULL_GREEN if val > 0 else COL_RED if val < 0 else TEXT_MUTED
            gl(sum_r, ci, f"{val:+,}" if val != 0 else "0", BG_HOVER, fg, bold=True)

        # Notes
        notes = []
        if (is_small or is_large) and th_level == 0:
            notes.append("⚠  No Townhall found in this village's buildings — celebration cost set to 0.")
        if is_large and 0 < th_level < 10:
            notes.append("⚠  Great Celebration requires Townhall level 10+.")
        if not (is_small or is_large):
            notes.append("ℹ  Set Small or Large in Account Overview to include celebration costs.")
        for note in notes:
            tk.Label(table_container, text=note, font=FONT_SMALL,
                     bg=BG_DARK, fg=COL_ORANGE if note.startswith("⚠") else TEXT_MUTED,
                     wraplength=560, justify="left"
                     ).pack(anchor="w", padx=24, pady=(6, 0))

    def _open_troops_import(self):
        if self.is_archived:
            return
        TroopOverviewImportDialog(
            self, self.server, self.account, self.tribe,
            on_complete=self._refresh_village_list)

    def _open_reinforcements_import(self):
        if self.is_archived:
            return
        ReinforcementsImportDialog(
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