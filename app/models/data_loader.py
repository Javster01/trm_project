import csv
import os
import re
from datetime import datetime


def _parse_date(s: str):
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    raise ValueError(f"Bad date: {s}")


def _parse_float(s: str):
    s = s.strip()

    # limpiar moneda y espacios
    s = s.replace("$", "").replace(" ", "")
    s = re.sub(r"[^0-9,\.\-]", "", s)

    # eliminar separadores colgantes (ej: "3,631.49,")
    s = s.rstrip(".,")

    # manejar separadores
    if "," in s and "." in s:
        if s.rfind(".") > s.rfind(","):
            # formato US: 3,631.49
            s = s.replace(",", "")
        else:
            # formato EU: 3.631,49
            s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        parts = s.split(",")
        # si parece separador de miles (1,234 o 12,345,678)
        if len(parts[-1]) == 3 and all(p.isdigit() for p in parts):
            s = "".join(parts)
        else:
            s = s.replace(",", ".")
    elif "." in s:
        parts = s.split(".")
        # si parece separador de miles estilo EU sin decimales (1.234)
        if len(parts[-1]) == 3 and all(p.isdigit() for p in parts):
            s = "".join(parts)

    return float(s)


def _default_csv_path():
    base = os.path.abspath(os.path.dirname(__file__))
    candidates = [
        os.path.abspath(os.path.join(base, "..", "data", "raw", "TRM_20260413.csv")),
        os.path.abspath(os.path.join(base, "..", "data", "TRM_20260413.csv")),
        os.path.expanduser("~/Downloads/TRM_20260413.csv"),
    ]

    for p in candidates:
        if os.path.exists(p):
            return p

    return None


def load_trm_data(path: str = None):
    """
    Retorna un DataFrame-like simple (lista de dicts) para análisis:
    [
        {"date": datetime, "trm": float},
        ...
    ]
    """

    if path is None:
        path = _default_csv_path()

    if not path:
        raise FileNotFoundError("No se encontró CSV TRM en app/data/raw, app/data ni ~/Downloads")

    if not os.path.exists(path):
        raise FileNotFoundError(path)

    data = []

    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    # 🔥 limpieza de separadores tipo: "VALOR ; VIGENCIA"
    cleaned = [re.sub(r"\s*;\s*", ";", line.strip()) for line in lines if line.strip()]

    reader = csv.reader(cleaned, delimiter=';')

    headers = next(reader)
    headers = [re.sub(r"[^a-z0-9]", "", h.lower()) for h in headers]

    val_idx = None
    date_idx = None

    for i, h in enumerate(headers):
        if "valor" in h or "trm" in h:
            val_idx = i
        if "vigenciadesde" in h or "fecha" in h:
            date_idx = i

    if val_idx is None or date_idx is None:
        raise ValueError("No se detectaron columnas correctamente")

    for row in reader:
        if len(row) <= max(val_idx, date_idx):
            continue
        try:
            data.append({
                "date": _parse_date(row[date_idx]),
                "trm": _parse_float(row[val_idx])
            })
        except Exception:
            continue

    if not data:
        raise ValueError("No se pudieron extraer datos")

    # ordenar por fecha
    data.sort(key=lambda x: x["date"])

    return data