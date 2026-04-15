from flask import Flask
import os
import sys

# Agregar el directorio padre al path para importaciones correctas
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from controllers.prediction_controller import prediction_bp

def create_app():
    # Obtener la ruta base de la aplicación
    base_dir = os.path.abspath(os.path.dirname(__file__))
    
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, 'views', 'templates'),
        static_folder=os.path.join(base_dir, 'views', 'static')
    )
    
    app.register_blueprint(prediction_bp)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)