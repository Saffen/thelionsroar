# thelionsroar/api/main.py
import yaml
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_FILE = Path("data/widgets.yaml")

def load_data():
    if not DATA_FILE.exists():
        return {"zones": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

@app.get("/widgets/config")
async def get_config():
    # Returnerer hele YAML-strukturen inklusive 'data' feltet
    return load_data()