from flask import Blueprint, render_template, jsonify
from models.analysis import get_analysis
from models.random_forest import predict_trm
from models.monte_carlo import simulate_trm
from models.llm_integration import get_recommendation

prediction_bp = Blueprint('prediction', __name__)

@prediction_bp.route("/")
def index():
    return render_template("index.html")

@prediction_bp.route("/predict")
def predict():
    analysis = get_analysis()
    prediction = predict_trm()
    simulation = simulate_trm()
    recommendation = get_recommendation(prediction)

    return jsonify({
        "analysis": analysis,
        "prediction": prediction,
        "simulation": simulation,
        "recommendation": recommendation
    })