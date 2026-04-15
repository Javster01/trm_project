from .data_loader import load_trm_data


def predict_trm():
    values = load_trm_data()
    return float(sum(values) / len(values))