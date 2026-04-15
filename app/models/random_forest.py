from .data_loader import load_trm_data


def predict_trm():
    records = load_trm_data()
    values = [item["trm"] for item in records]
    return float(sum(values) / len(values))