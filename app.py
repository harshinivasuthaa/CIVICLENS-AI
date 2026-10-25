import os
from app import create_app

env = os.getenv("FLASK_ENV", "development")
app = create_app(env)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    # Local runnable development server
    print(f"Starting CIVICLENS AI server on http://127.0.0.1:{port} ({env} mode)")
    app.run(host="127.0.0.1", port=port, debug=(env == "development"))
