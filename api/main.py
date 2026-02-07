import os
import shutil
import yaml
from pathlib import Path
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from slugify import slugify

app = FastAPI(title="The Lion's Roar API")

# --- OPRINDELIG KONFIGURATION OG CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sti til widget data
DATA_FILE = Path("/app/data/widgets.yaml")

def load_data():
    if not DATA_FILE.exists():
        return {"zones": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# Oprindeligt endpoint bevaret
@app.get("/widgets/config")
async def get_config():
    """Returnerer hele YAML-strukturen inklusive 'data' feltet."""
    return load_data()

# --- SETUP AF TEMPLATES OG ASSETS ---
# Vi bruger /app prefix da det kører i Docker med de nye mounts
templates = Jinja2Templates(directory="/app/templates")

if os.path.exists("/app/assets"):
    app.mount("/assets", StaticFiles(directory="/app/assets"), name="assets")

# --- ADMIN PANEL ENDPOINTS ---

@app.get("/api/admin", response_class=HTMLResponse)
async def get_admin_editor(request: Request):
    """Serverer selve editoren."""
    return templates.TemplateResponse("admin_editor.html", {"request": request})

@app.post("/api/admin/publish")
async def handle_publish(
    title: str = Form(...),
    author: str = Form(...),
    teaser: str = Form(...),
    content: str = Form(...),
    publish_at: str = Form(...),
    image: UploadFile = File(None)
):
    try:
        # 1. Parse dato og generer ID (YYYYMMDDHHMM-slug)
        dt = datetime.fromisoformat(publish_at)
        article_id = f"{dt.strftime('%Y%m%d%H%M')}-{slugify(title)}"
        year_folder = dt.strftime('%Y')
        
        # 2. Håndter billed-upload til mountet volume
        image_ref = ""
        if image and image.filename:
            ext = os.path.splitext(image.filename)[1].lower()
            img_name = f"{article_id}{ext}"
            img_dest = f"/app/assets/images/{img_name}"
            
            os.makedirs(os.path.dirname(img_dest), exist_ok=True)
            with open(img_dest, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)
            
            image_ref = f"/assets/images/{img_name}"

        # 3. Opbyg Frontmatter (YAML) baseret på projektets standarder
        frontmatter = {
            "id": article_id,
            "title": title,
            "teaser": teaser,
            "authors": [author],
            "publish_at": dt.strftime('%d-%m-%Y %H:%M'),
            "status": "scheduled",
            "image": {
                "src": image_ref,
                "alt": title
            }
        }

        # Generer Markdown indhold
        md_output = "---\n"
        md_output += yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)
        md_output += "---\n\n"
        md_output += content

        # 4. Gem filen i mountet content volume
        save_path = f"/app/content/news/{year_folder}/{article_id}.md"
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(md_output)

        return JSONResponse({
            "status": "ok", 
            "message": f"Artikel '{title}' er gemt: {article_id}.md",
            "id": article_id
        })

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)