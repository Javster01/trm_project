import os
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI


# Cargar variables de entorno desde archivo .env
load_dotenv()


# Modelos gratuitos disponibles en OpenRouter
AVAILABLE_MODELS = [
    {
        "id": "arcee-ai/trinity-large-preview:free",
        "name": "Arcee Trinity Large Preview",
        "provider": "Arcee AI",
        "description": "Trinity-Large-Preview es un modelo de lenguaje de gran escala con arquitectura Mixture-of-Experts, optimizado para eficiencia y alto rendimiento. Destaca en tareas creativas, conversación y uso en entornos agenticos con herramientas complejas. Admite contextos muy largos y ofrece pesos abiertos, pensado para aplicaciones reales y experimentación.",
    },
    {
        "id": "z-ai/glm-4.5-air:free",
        "name": "GLM-4.5 Air",
        "provider": "Z-AI",
        "description": "GLM-4.5-Air es una versión ligera de su modelo principal, basada en arquitectura Mixture-of-Experts y optimizada para aplicaciones centradas en agentes. Ofrece modos híbridos de inferencia: uno de “razonamiento” para tareas complejas y otro rápido para interacción en tiempo real. Permite controlar el comportamiento del modelo activando o desactivando el razonamiento según la necesidad.",
    },
    {
        "id": "openai/gpt-4o-mini",
        "name": "GPT-4o Mini",
        "provider": "OpenAI",
        "description": "GPT-4o mini es un modelo reciente de OpenAI que admite entradas de texto e imagen con salida en texto. Es una opción avanzada y mucho más económica que otros modelos, manteniendo alto nivel de inteligencia. Logra alto rendimiento en benchmarks y supera a modelos anteriores en preferencias de uso en chat.",
    },
]


def get_investment_recommendation(current_trm: float, predicted_trm: float) -> dict:
    """
    Calcula recomendación de inversión basada en cambio porcentual de TRM.
    
    Condiciones:
    - Compra: si la TRM baja un 10% o más
    - Mantener: si la TRM sube menos del 10%
    - Venta: si la TRM sube más del 10%
    
    Args:
        current_trm: Valor actual de TRM
        predicted_trm: Valor predicho de TRM
    
    Returns:
        dict con recomendación y análisis
    """
    change_abs = predicted_trm - current_trm
    change_pct = (change_abs / current_trm) * 100 if current_trm > 0 else 0

    if change_pct <= -10:
        recommendation = "COMPRA"
        reasoning = f"La TRM bajará aproximadamente {abs(change_pct):.2f}%, lo que es favorable para comprar USD"
    elif change_pct < 10:
        recommendation = "MANTENER"
        reasoning = f"La TRM se mantendrá relativamente estable o subirá menos del 10% ({change_pct:.2f}%)"
    else:
        recommendation = "VENTA"
        reasoning = f"La TRM subirá más del 10% ({change_pct:.2f}%), lo que favorece la venta de USD"

    return {
        "recommendation": recommendation,
        "change_absolute": round(change_abs, 2),
        "change_percentage": round(change_pct, 2),
        "reasoning": reasoning,
        "current_trm": round(current_trm, 2),
        "predicted_trm": round(predicted_trm, 2),
    }


def get_available_models() -> list:
    """Retorna lista de modelos disponibles en OpenRouter."""
    return AVAILABLE_MODELS


def create_openrouter_client() -> OpenAI:
    """
    Crea cliente de OpenAI configurado para OpenRouter.
    
    Requiere variable de entorno: OPENROUTER_API_KEY
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY no está configurada en las variables de entorno"
        )

    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )


def chat_with_llm(
    model_id: str,
    user_message: str,
    current_trm: float,
    predicted_trm_rf: float,
    predicted_trm_mc: float,
    rf_daily_forecast: list = None,
    mc_daily_forecast: dict = None,
    system_context: Optional[str] = None,
) -> dict:
    """
    Envía mensaje a LLM de OpenRouter con contexto de predicciones.
    
    Args:
        model_id: ID del modelo de OpenRouter
        user_message: Mensaje del usuario
        current_trm: Valor actual de TRM
        predicted_trm_rf: Predicción Random Forest para próximo mes
        predicted_trm_mc: Predicción Monte Carlo para próximo mes
        rf_daily_forecast: Lista de predicciones diarias de Random Forest
        mc_daily_forecast: Dict con proyecciones probabilísticas de Monte Carlo
        system_context: Contexto del sistema personalizado (opcional)
    
    Returns:
        dict con respuesta del modelo
    """
    try:
        client = create_openrouter_client()

        # Construir contexto del sistema si no se proporciona
        if not system_context:
            # Calcular recomendaciones de ambos modelos
            investment_rec_rf = get_investment_recommendation(current_trm, predicted_trm_rf)
            investment_rec_mc = get_investment_recommendation(current_trm, predicted_trm_mc)
            
            # Construir información de predicciones diarias
            daily_forecast_info = ""
            if rf_daily_forecast:
                daily_forecast_info += "\n\n📅 PRONÓSTICO RANDOM FOREST (Próximos 30 días):\n"
                for day_forecast in rf_daily_forecast[:7]:  # Mostrar primeros 7 días
                    date = day_forecast.get("date", "?")
                    prediction = day_forecast.get("prediction", 0)
                    daily_forecast_info += f"  - {date}: ${prediction:.2f}\n"
                if len(rf_daily_forecast) > 7:
                    daily_forecast_info += f"  ... y {len(rf_daily_forecast) - 7} días más\n"
            
            if mc_daily_forecast and isinstance(mc_daily_forecast, dict):
                daily_forecast_info += "\n\n📊 PROYECCIÓN MONTE CARLO (Análisis probabilístico):\n"
                percentiles = mc_daily_forecast.get("percentiles", {})
                daily_forecast_info += f"  - Escenario pesimista (P5): ${percentiles.get('p05', current_trm):.2f}\n"
                daily_forecast_info += f"  - Escenario probable (P50): ${percentiles.get('p50', current_trm):.2f}\n"
                daily_forecast_info += f"  - Escenario optimista (P95): ${percentiles.get('p95', current_trm):.2f}\n"
            
            system_context = f"""Eres un asesor financiero experto en tasas de cambio.
Tu objetivo es ayudar a los usuarios a entender las predicciones de TRM (Tasa de Cambio Representativa del Mercado) de Colombia y proporcionar recomendaciones de inversión.

📊 DATOS ACTUALES:
- TRM Actual: ${current_trm:.2f}

🤖 PREDICCIONES Y RECOMENDACIONES:

Random Forest:
  - Predicción próximo mes: ${predicted_trm_rf:.2f}
  - Cambio esperado: {investment_rec_rf['change_percentage']:.2f}%
  - Recomendación: {investment_rec_rf['recommendation']}

Monte Carlo (Simulación de 1000 escenarios):
  - Predicción próximo mes: ${predicted_trm_mc:.2f}
  - Cambio esperado: {investment_rec_mc['change_percentage']:.2f}%
  - Recomendación: {investment_rec_mc['recommendation']}
{daily_forecast_info}

💡 REGLAS DE INVERSIÓN PARA AMBOS MODELOS:
- COMPRA: si la TRM baja un 10% o más
- MANTENER: si la TRM sube menos del 10%
- VENTA: si la TRM sube más del 10%

📝 INSTRUCCIONES:
1. Puedes responder preguntas sobre la TRM del próximo mes
2. Considera AMBOS modelos en tus análisis - Random Forest (machine learning) y Monte Carlo (probabilístico)
3. Puedes detallar predicciones diarias específicas (ej: "¿cuánto bajará pasado mañana?")
4. Cuando el usuario pida consejos de inversión:
   - Presenta ambas recomendaciones claramente
   - Explica tu análisis comparativo de ambos modelos
   - SIEMPRE da tu opinión sobre cuál modelo es más confiable en este caso y por qué
5. Sé conciso pero informativo en tus respuestas
6. Si el usuario pregunta sobre un día específico, consulta el pronóstico Random Forest

🔍 CRITERIOS PARA EVALUAR CONFIABILIDAD:
- Random Forest: Bueno cuando hay patrones claros en los datos históricos, pero trata cada día independientemente
- Monte Carlo: Mejor para entender rango de posibilidades (volatilidad), refleja incertidumbre real
- Si ambos modelos predicen lo mismo (misma recomendación): MÁS CONFIABLE (convergencia)
- Si predicen diferente: Analiza cuál tiene sentido según el contexto económico actual"""

        # Hacer llamada al LLM
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "http://localhost:5000",
                "X-OpenRouter-Title": "TRM Predictor",
            },
            model=model_id,
            messages=[
                {"role": "system", "content": system_context},
                {"role": "user", "content": user_message},
            ],
            temperature=0.7,
            max_tokens=1500,
        )

        response_text = completion.choices[0].message.content

        # Si el usuario preguntó sobre inversión, agregar ambas recomendaciones
        investment_recommendations = None
        if any(keyword in user_message.lower() for keyword in ["inversión", "invertir", "comprar", "vender", "consejo", "recomendación"]):
            investment_rec_rf = get_investment_recommendation(current_trm, predicted_trm_rf)
            investment_rec_mc = get_investment_recommendation(current_trm, predicted_trm_mc)
            investment_recommendations = {
                "random_forest": investment_rec_rf,
                "monte_carlo": investment_rec_mc,
            }

        return {
            "success": True,
            "model": model_id,
            "response": response_text,
            "investment_recommendations": investment_recommendations,
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "model": model_id,
            "response": None,
            "investment_recommendations": None,
            "error": str(e),
        }