# TRM Prediction Project

Proyecto de predicción del TRM (Tasa Representativa del Mercado) usando Machine Learning.

## Estructura del Proyecto

```
run.py                    # Punto de entrada principal de la aplicación
app/
├── __init__.py            # Factory function para crear la app Flask
├── models/                # Lógica de datos y predicciones (namespace package)
│   ├── data_loader.py
│   ├── analysis.py
│   ├── random_forest.py
│   ├── monte_carlo.py
│   ├── llm_integration.py
│   ├── mlflow_integration.py
│   ├── prediction_service.py
│   └── visualization.py
├── controllers/           # Endpoints y rutas (namespace package)
│   └── prediction_controller.py
└── views/                 # Frontend (HTML, CSS, JS) (namespace package)
    ├── templates/
    │   └── pages/
    │       ├── home.html
    │       ├── dashboard.html
    │       ├── prediction.html
    │       ├── data.html
    │       ├── eda.html
    │       └── base.html
    └── static/
        ├── css/
        │   └── index.css
        └── js/
            └── index.js
```

## Instalación

1. Crear entorno virtual:
```bash
python -m venv .venv
source .venv/bin/activate
```

2. Instalar dependencias:
```bash
pip install -r requirements.txt
```

3. Configurar variables de entorno:
```bash
cp .env.example .env
```

Edita el archivo `.env` y agrega tu API Key de OpenRouter:
```
OPENROUTER_API_KEY=tu_api_key_aqui
```

Obtén tu API Key en: [https://openrouter.ai](https://openrouter.ai)

## Ejecución

### Opción 1: Script automático (Recomendado)
Ejecuta ambos servicios (Flask y MLflow) automáticamente:
```bash
./start_services.sh
```

La aplicación estará disponible en `http://localhost:5000`
MLflow estará disponible en `http://127.0.0.1:5001`

**Logs:**
- Flask: `flask.log`
- MLflow: `mlflow.log`

### Opción 2: Manual
**Terminal 1 - MLflow:**
```bash
source .venv/bin/activate
mlflow server --host 127.0.0.1 --port 5001 --backend-store-uri sqlite:///mlflow.db --default-artifact-root ./mlruns
```

**Terminal 2 - Flask:**
```bash
source .venv/bin/activate
python run.py
```

## Arquitectura MVC

El proyecto sigue el patrón **Model-View-Controller** con Flask:

| Capa | Componentes | Responsabilidad |
|------|-------------|-----------------|
| **M** (Models) | `app/models/` | Lógica de negocio: carga de datos, análisis, predicciones, integración con MLflow |
| **V** (Views) | `app/views/` | Interfaz de usuario: templates HTML, CSS y JavaScript |
| **C** (Controllers) | `app/controllers/` | Enrutamiento: endpoints Flask que coordinan modelos y vistas |
| **Factory** | `app/__init__.py` | Crea la instancia de Flask y registra blueprints |

**Flujo típico:**
1. Usuario accede a una URL (`http://localhost:5000/prediccion`)
2. Flask enruta a `prediction_controller.py` 
3. Controller llama a modelos en `app/models/`
4. Vista renderiza `app/views/templates/pages/prediction.html`

## Uso

Accede a `http://localhost:5000` en tu navegador para ver la interfaz de predicción del TRM.


## Carpeta de datos

Coloca tus archivos CSV con la TRM en la carpeta `app/data/raw/` (creada por el proyecto).

El cargador `load_trm_data()` buscará automáticamente en estas rutas (en este orden):

- la ruta que se le pase explícitamente a `load_trm_data(path)`;
- `app/data/raw/TRM_20260413.csv`;
- `app/data/TRM_20260413.csv`;
- `~/Downloads/TRM_20260413.csv`;
- `./TRM_20260413.csv` (raíz del repo).

Ejemplo: copia el CSV al proyecto:

```bash
cp ~/Downloads/TRM_20260413.csv app/data/raw/
```

O prueba la carga desde Python pasando la ruta completa:

```python
from app.models.data_loader import load_trm_data
vals = load_trm_data('/Users/tu_usuario/Downloads/TRM_20260413.csv')
print(vals[:10])
```

