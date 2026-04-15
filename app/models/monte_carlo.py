import random

from .data_loader import load_trm_data


def simulate_trm(n=10):
    records = load_trm_data()
    values = [item["trm"] for item in records]
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    std = variance ** 0.5

    return [round(random.gauss(mean, std), 2) for _ in range(n)]