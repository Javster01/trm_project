from flask import Flask
import os

from .controllers.prediction_controller import prediction_bp


def create_app():
    """Factory function para crear la aplicación Flask."""
    base_dir = os.path.abspath(os.path.dirname(__file__))
    
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, 'views', 'templates'),
        static_folder=os.path.join(base_dir, 'views', 'static')
    )
    
    # Registrar blueprints
    app.register_blueprint(prediction_bp)

    return app
