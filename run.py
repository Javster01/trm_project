#!/usr/bin/env python
"""Punto de entrada principal de la aplicación Flask."""

from app import create_app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
