"""
Reads 'zabach JNR PRICE LIST.xlsx' and produces a cleaned 'zabach_items.csv'.

Usage:
    pip install openpyxl
    python scripts/clean_price_list.py "zabach JNR PRICE LIST.xlsx" zabach_items.csv
"""
import csv
import re
import sys
from pathlib import Path
from openpyxl import load_workbook


# ---------- Configuration ----------

# Sheet name -> category name in the app
SHEET_TO_CATEGORY = {
    'laboratory':                'LABORATORY',
    'stationaries':              'STATIONERY',
    'exercise':                  'EXERCISE BOOKS',
    'home science':              'HOME SCIENCE',
    'agriculture':               'AGRICULTURE',
    'art and craft':             'ART & CRAFT',
    'music':                     'MUSIC',
    'office equipment':          'OFFICE EQUIPMENT',
    'sports practical material': 'SPORTS',
    'text books':                'TEXT BOOKS',
    # misc handled separately below
}

# Manual routing for rows that appear in the misc sheet
MISC_OVERRIDES = {
    'bowl medium size':   'HOME SCIENCE',
    'colander':           'HOME SCIENCE',
    'blender 3 in one':   'HOME SCIENCE',
    'fork jembe':         'AGRICULTURE',
    'water dispenser':    'HOME SCIENCE',
    # pellet tes -> leave uncategorised; user reviews
    # epson printer l3210 -> duplicate; skip
}

# Rows to skip entirely (duplicates, bad data)
SKIP_ITEMS = {
    'epson printer l3210',  # duplicate of the one in OFFICE EQUIPMENT
}

# Brands to extract from item titles (case-insensitive)
KNOWN_BRANDS = [
    'GRIFFCHEM', 'GRIGGCHEM', 'GRIFCHEM', 'BOROSIL', 'SIMAX', 'LOBA', 'CDH',
    'M&G', 'DOMS', 'NATARAJ', 'PELIKAN', 'CASIO', 'KLB', 'OXFORD', 'MORAN',
    'EAEP', 'E.A.E.P', 'STORYMOJA', 'LONGHON', 'SPARO', 'MIKASA', 'SAMBA',
    'MOLTEN', 'DUNLOP', 'UMBRO', 'KEMPA', 'KANGARO', 'DELI', 'PRITT',
    'FIVE STAR', 'BIC', 'STEADLER', 'STAEDTLER', 'FABER-CASTELL', 'FABER CASTELL',
    'SUPERFINE', 'ECONOMIC', 'KASUKU', 'KARTASI', 'CROWN', 'CROWNBIRD',
    'FULTONE', 'MUNGYO', 'OMEGA', 'ROK', 'SUMO', 'HELIOS', 'SUPERFINE',
    'ECON', 'ECONO', 'MIC', 'PRESTO', 'ONE PLANET', 'ACCESS', 'SPOT LIGHT',
    'TEEPEE', 'OFFICE POINT', 'MIDGO', 'GEM', 'RAPID', 'INNOVIA',
    'AFRI', 'HASH', 'OLIBYA', 'K-GAS', 'SEA-GAS', 'KM-H07W', 'KM-H06W',
    'CASTON', 'CHINA', 'KENYA', 'JAPAN', 'THAILAND', 'INDIA', 'ENGLAND',
]

# Simple typo corrections applied to whole title
TYPO_FIXES = {
    r'\bBURSEN\b':          'BUNSEN',
    r'\bMOTOR AND PESTILE\b': 'MORTAR AND PESTLE',
    r'\bANTHYDROUS\b':      'ANHYDROUS',
    r'\bCUPRIC SULHATE\b':  'CUPRIC SULPHATE',
    r'\bHYDRCHLORIC\b':     'HYDROCHLORIC',
    r'\bTERMOMETER\b':      'THERMOMETER',
    r'\bSERAMIC\b':         'CERAMIC',
    r'\bBENEDIC\b':         'BENEDICT',
    r'\bHYDROMETRE\b':      'HYDROMETER',
    r'\bPROTRACTER\b':      'PROTRACTOR',
    r'\bBLACKBOAD\b':       'BLACKBOARD',
    r'\bCOPASS\b':          'COMPASS',
    r'\bSTATINESS\b':       'STAINLESS',
    r'\bSTAILNESS\b':       'STAINLESS',
    r'\bSET SQUATE\b':      'SET SQUARE',
    r'\bTECHNIAL\b':        'TECHNICAL',
    r'\bGEOMERTICAL\b':     'GEOMETRICAL',
    r'\bSCISSORS FABRIC\b': 'FABRIC SCISSORS',
    r'\bMISROSCOPE\b':      'MICROSCOPE',
    r'\bDESPOSAL\b':        'DISPOSAL',
    r'\bDISSCTING\b':       'DISSECTING',
    r'\bJOINY\b':           'JOINT',
    r'\bSTAINESS\b':        'STAINLESS',
    r'\bWOODE\b':           'WOODEN',
    r'\bCOLOURD\b':         'COLOURED',
    r'\bPOWDERD\b':         'POWDERED',
    r'\bTOLEO\b':           'TOLEO',  # Swahili, keep
}

# Unit normalisation
UNIT_MAP = {
    '':        'EACH',
    'each':    'EACH',
    'pkt':     'PKT',
    'pack':    'PKT',
    '1pkt':    'PKT',
    'packet':  'PKT',
    'ream':    'REAM',
    'roll':    'ROLL',
    '1roll':   'ROLL',
    'pair':    'PAIR',
    '1pair':   'PAIR',
    'set':     'SET',
    '1set':    'SET',
    'mtr':     'MTR',
    '1mtr':    'MTR',
    '1/2 litre': '500ML',
    'litre':   'L',
    'kgs':     'KG',
    'kg':      'KG',
    'sack':    'SACK',
    '1 sack':  'SACK',
    '6pcs':    'PCS',
    'pcs':     'PCS',
    'leaves':  'LEAVES',
}

# Columns in the various sheet layouts
STANDARD_HEADERS = {
    'laboratory':               {'name': 1, 'category': 2, 'price': 3},
    'stationaries':             {'name': 2, 'brand': 3, 'unit': 4, 'price': 5},
    'exercise':                 {'name': 2, 'brand': 3, 'unit': 4, 'price': 5},
    'home science':             {'name': 2, 'brand': 3, 'unit': 4, 'price': 5},
    'agriculture':              {'name': 2, 'brand': 3, 'unit': 4, 'price': 5},
    'art and craft':            {'name': 2, 'brand': 3, 'unit': 4, 'price': 5},
    'music':                    {'name': 2, 'brand': 3, 'unit': 4, 'price': 5},
    'office equipment':         {'name': 2, 'brand': 3, 'unit': 4, 'price': 5},
    'sports practical material':{'name': 2, 'brand': 3, 'unit': 4, 'price': 5},
    'text books':               {'name': 2, 'brand': 3, 'unit': 4, 'price': 5},
    'misc':                     {'name': 2, 'brand': 3, 'unit': 4, 'price': 5},
}


def clean_title(raw: str) -> str:
    """Normalise whitespace, casing, and apply typo fixes."""
    s = str(raw or '').strip()
    s = re.sub(r'\s+', ' ', s)
    for pattern, replacement in TYPO_FIXES.items():
        s = re.sub(pattern, replacement, s, flags=re.IGNORECASE)
    return s


def extract_brand(title: str) -> tuple[str, str]:
    """Pull a known brand out of the title if present. Returns (clean_title, brand)."""
    upper = title.upper()
    found = ''
    for brand in KNOWN_BRANDS:
        # word-boundary match, case-insensitive
        if re.search(rf'\b{re.escape(brand)}\b', upper):
            # remove the brand from the title (all occurrences)
            title = re.sub(rf'\b{re.escape(brand)}\b', '', title, flags=re.IGNORECASE)
            found = brand
            break  # only one brand per row
    # tidy leftover double spaces
    title = re.sub(r'\s+', ' ', title).strip(' ,-')
    return title, found


def normalise_unit(raw: str) -> str:
    key = str(raw or '').strip().lower()
    return UNIT_MAP.get(key, 'EACH')


def parse_price(raw) -> float | None:
    """Return a float price or None if it can't be parsed."""
    if raw is None:
        return None
    s = str(raw).strip().replace(',', '')
    if not s or s.lower() in ('till', '-', 'n/a'):
        return None
    # reject obviously-wrong concatenations like 110165220
    try:
        val = float(s)
    except ValueError:
        # strip trailing non-numeric
        m = re.match(r'^([\d.]+)', s)
        if not m:
            return None
        try:
            val = float(m.group(1))
        except ValueError:
            return None
    # sanity check
    if val <= 0 or val > 1_000_000:
        return None
    return val


def process_sheet(ws, sheet_key: str, rows_out: list, warnings: list):
    layout = STANDARD_HEADERS.get(sheet_key)
    if not layout:
        warnings.append(f"Unknown sheet: {sheet_key}")
        return

    category = SHEET_TO_CATEGORY.get(sheet_key)
    is_misc = sheet_key == 'misc'

    for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if not row:
            continue

        def cell(col_num):
            """col_num is 1-based; index into row tuple."""
            if col_num is None or col_num > len(row):
                return None
            return row[col_num - 1]

        name_raw = cell(layout.get('name'))
        if not name_raw:
            continue

        title = clean_title(name_raw)
        if not title:
            continue
        if title.lower() in SKIP_ITEMS:
            warnings.append(f"Skipped (dup): {title}")
            continue

        # Category routing
        if is_misc:
            cat = MISC_OVERRIDES.get(title.lower())
            if not cat:
                warnings.append(f"misc row not routed: {title}")
                continue
        else:
            cat = category

        # Brand
        explicit_brand = clean_title(cell(layout.get('brand')) or '')
        title, extracted_brand = extract_brand(title)
        brand = explicit_brand or extracted_brand

        unit = normalise_unit(cell(layout.get('unit')))
        price = parse_price(cell(layout.get('price')))

        if price is None:
            warnings.append(f"{sheet_key}: no price for '{title}' (raw={cell(layout.get('price'))!r})")
            continue

        rows_out.append({
            'title': title,
            'category': cat,
            'brand': brand,
            'unit': unit,
            'price': f'{price:.2f}',
        })


def main(xlsx_path: str, csv_out: str):
    wb = load_workbook(xlsx_path, data_only=True)
    rows_out: list[dict] = []
    warnings: list[str] = []

    for ws in wb.worksheets:
        key = ws.title.strip().lower()
        process_sheet(ws, key, rows_out, warnings)

    # Write CSV
    with open(csv_out, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['title', 'category', 'brand', 'unit', 'price'])
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"Wrote {len(rows_out)} rows to {csv_out}")
    print(f"Skipped/unrouted: {len(warnings)}")
    if warnings:
        with open('import_warnings.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(warnings))
        print("See import_warnings.txt for details")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    xlsx = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else 'zabach_items.csv'
    main(xlsx, out)