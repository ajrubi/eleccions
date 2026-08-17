"""Entry point: starts the Flask development server.

For anything beyond local development, run this app behind a real WSGI
server (gunicorn/waitress) instead of Flask's built-in dev server.
"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=debug)
