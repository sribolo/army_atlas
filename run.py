import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402

app = create_app(os.environ.get("FLASK_CONFIG", "development"))

if __name__ == "__main__":
    # Default to 5001, not Flask's usual 5000 — macOS's AirPlay Receiver
    # binds port 5000 by default and will intercept requests instead.
    app.run(port=int(os.environ.get("FLASK_RUN_PORT", 5001)))
