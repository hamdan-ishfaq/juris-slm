# main.py
# src/main.py - App entry point
import uvicorn
from src.api import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=True)