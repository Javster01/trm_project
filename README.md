# TRM Prediction Project

Proyecto de predicción del TRM (Tasa Representativa del Mercado) usando Machine Learning.

## Estructura del Proyecto

```
app/
├── __init__.py
├── app.py                 # Configuración principal de Flask
├── models/                # Lógica de datos y predicciones
│   ├── __init__.py
│   ├── data_loader.py
│   ├── analysis.py
│   ├── random_forest.py
│   ├── monte_carlo.py
│   └── llm_integration.py
├── controllers/           # Endpoints y rutas
│   ├── __init__.py
│   └── prediction_controller.py
└── views/                 # Frontend (HTML, CSS, JS)
    ├── __init__.py
    ├── templates/
    │   └── index.html
    └── static/
        ├── css/
        └── js/
```

## Instalación

1. Crear entorno virtual:
```bash
python -m venv venv
source venv/bin/activate
```

2. Instalar dependencias:
```bash
pip install -r requirements.txt
```

## Ejecución

### Opción 1: Usar run.py (Recomendado)
```bash
source venv/bin/activate
python run.py
```

### Opción 2: Usar app.py directamente
```bash
source venv/bin/activate
python app/app.py
```

La aplicación estará disponible en `http://localhost:5000`

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

