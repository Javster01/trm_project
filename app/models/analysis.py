from statistics import pstdev

from .data_loader import load_trm_data


def get_analysis():
    values = load_trm_data()

    return {
        "mean": float(sum(values) / len(values)),
        "std": float(pstdev(values)),
        "max": float(max(values)),
        "min": float(min(values)),
    }