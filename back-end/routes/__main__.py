"""Dev entrypoint: `python -m routes` runs the Flask dev server.

Prod uses `gunicorn routes:app` (the package's `app`); this module is only the
development convenience runner that the old `python routes.py` provided.
"""

from routes import app
from utils.settings import backend_port

if __name__ == "__main__":
    # threaded so long-lived responses (e.g. SSE streams) don't block other
    # requests on the single dev worker.
    app.run(host="0.0.0.0", port=backend_port, debug=True, threaded=True)
