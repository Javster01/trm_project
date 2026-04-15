def get_recommendation(prediction):
    current = 4000  # ejemplo base

    change = (prediction - current) / current

    if change <= -0.10:
        return "Comprar USD"
    elif change < 0.10:
        return "Mantener"
    else:
        return "Vender USD"