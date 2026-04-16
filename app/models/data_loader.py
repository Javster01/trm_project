import csv
import json
import os
import re
import ssl
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TRM_PUBLIC_API_URL = "https://www.datos.gov.co/resource/32sa-8pi3.json"
TRM_API_RECENT_LIMIT = 365


def _parse_date(s: str):
    if s is None:
        raise ValueError("Bad date: None")

    if not isinstance(s, str):
        s = str(s)

    s = s.strip()
    for fmt in (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d/%m/%y",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue

    if "T" in s:
        try:
            return datetime.strptime(s.split("T", 1)[0], "%Y-%m-%d")
        except Exception:
            pass

    raise ValueError(f"Bad date: {s}")


def _parse_float(s: str):
    if s is None:
        raise ValueError("Bad float: None")

    if isinstance(s, (int, float)):
        return float(s)

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


def _http_get_json(url: str, timeout=20):
    req = Request(url=url, headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        # En algunos entornos locales falla la validación CA para HTTPS de datos.gov.co.
        # Reintento de compatibilidad para no perder los últimos datos.
        if "CERTIFICATE_VERIFY_FAILED" in str(exc):
            insecure_ctx = ssl._create_unverified_context()
            with urlopen(req, timeout=timeout, context=insecure_ctx) as response:
                return json.loads(response.read().decode("utf-8"))
        raise


def _records_from_api_rows(rows):
    data = []
    for row in rows or []:
        if isinstance(row, dict):
            value_raw = row.get("valor") or row.get("trm")
            date_raw = row.get("vigenciadesde") or row.get("fecha")
        elif isinstance(row, list):
            # Compatibilidad básica si endpoint devuelve filas tabulares.
            value_raw = row[0] if len(row) > 0 else None
            date_raw = row[1] if len(row) > 1 else None
        else:
            continue

        if value_raw is None or date_raw is None:
            continue

        try:
            data.append({
                "date": _parse_date(date_raw),
                "trm": _parse_float(value_raw),
            })
        except Exception:
            continue

    data.sort(key=lambda x: x["date"])
    return data


def _load_trm_data_from_public_api(limit=50000, order_desc=False):
    order_direction = "desc" if order_desc else "asc"
    params = {
        "$select": "valor,vigenciadesde",
        "$where": "valor is not null and vigenciadesde is not null",
        "$order": f"vigenciadesde {order_direction}",
        "$limit": str(limit),
    }
    url = f"{TRM_PUBLIC_API_URL}?{urlencode(params)}"
    payload = _http_get_json(url)
    if isinstance(payload, list):
        return _records_from_api_rows(payload)

    # Tolerancia ante respuestas con envoltorio tipo {"data": [...]}.
    if isinstance(payload, dict):
        candidate_rows = payload.get("data") or payload.get("results") or payload.get("rows") or []
        return _records_from_api_rows(candidate_rows)

    return []


def _merge_records_prefer_api(csv_data, api_data):
    merged_by_date = {}

    for item in csv_data or []:
        key = item["date"].strftime("%Y-%m-%d")
        merged_by_date[key] = item

    # API tiene prioridad sobre CSV en fechas solapadas (últimos datos)
    for item in api_data or []:
        key = item["date"].strftime("%Y-%m-%d")
        merged_by_date[key] = item

    merged = list(merged_by_date.values())
    merged.sort(key=lambda x: x["date"])
    return merged


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


def _load_trm_data_from_csv(path: str):
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

    data.sort(key=lambda x: x["date"])
    return data


def load_trm_data(path: str = None):
    """
    Retorna un DataFrame-like simple (lista de dicts) para análisis:
    [
        {"date": datetime, "trm": float},
        ...
    ]
    """

    # Objetivo: CSV para histórico + API para los últimos datos.
    if path is None:
        path = _default_csv_path()

    csv_data = []
    if path:
        try:
            csv_data = _load_trm_data_from_csv(path)
        except Exception:
            csv_data = []

    api_recent_data = []
    try:
        api_recent_data = _load_trm_data_from_public_api(limit=TRM_API_RECENT_LIMIT, order_desc=True)
    except Exception:
        api_recent_data = []

    merged = _merge_records_prefer_api(csv_data, api_recent_data)
    if merged:
        return merged

    # Último fallback: intentar API completa
    try:
        api_full_data = _load_trm_data_from_public_api()
        if api_full_data:
            return api_full_data
    except Exception:
        pass

    if path:
        return _load_trm_data_from_csv(path)

    raise FileNotFoundError("No se pudo cargar TRM ni desde API pública ni desde CSV local")