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
import markdown

# IP-lås baseret på dine logs
ALLOWED_IP = "192.168.0.1"

# Initialisér app med deaktiveret redirect for at undgå Nginx 404/307 loops
app = FastAPI(title="The Lion's Roar API", redirect_slashes=False)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Hjælpefunktion til at verificere IP
def verify_ip(request: Request):
    forwarded = request.headers.get("X-Forwarded-For")
    client_ip = forwarded.split(',')[0] if forwarded else request.client.host
    
    if client_ip != ALLOWED_IP:
        print(f"FORBIDDEN ACCESS ATTEMPT FROM: {client_ip}")
        raise HTTPException(status_code=403, detail=f"Forbidden: Your IP ({client_ip}) is not allowed")
    return client_ip

# Setup af templates og assets
templates = Jinja2Templates(directory="/app/templates")

if os.path.exists("/app/assets"):
    app.mount("/assets", StaticFiles(directory="/app/assets"), name="assets")

# --- ENDPOINTS ---

@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/", response_class=HTMLResponse)
async def get_admin_editor(request: Request):
    verify_ip(request)
    return templates.TemplateResponse("admin_editor.html", {"request": request})

@app.post("/admin/preview")
async def admin_preview(request: Request, content: str = Form(...)):
    verify_ip(request)
    html_content = markdown.markdown(content, extensions=['extra', 'codehilite'])
    return JSONResponse({"html": html_content})

@app.post("/admin/publish")
async def handle_publish(
    request: Request,
    title: str = Form(...),
    author: str = Form(...),
    publish_at: str = Form(...),
    section: str = Form("news"),
    type: str = Form("report"),
    status: str = Form("scheduled"),
    tags: str = Form(""),
    image_credit: str = Form(""),
    image_source: str = Form("Lion's Roar archives"),
    image_type: str = Form("illustration"),
    teaser: str = Form(...),
    content: str = Form(...),
    discord_announce: bool = Form(True),
    image: UploadFile = File(None)
):
    verify_ip(request)
    
    try:
        # 1. Parse dato og generer ID
        dt = datetime.fromisoformat(publish_at)
        article_id = f"{dt.strftime('%Y%m%d%H%M')}-{slugify(title)}"
        year_folder = dt.strftime('%Y')
        
        # 2. Håndter billed-upload
        image_ref = ""
        if image and image.filename:
            ext = os.path.splitext(image.filename)[1].lower()
            img_name = f"{article_id}{ext}"
            img_dest = f"/app/assets/images/{img_name}"
            
            os.makedirs(os.path.dirname(img_dest), exist_ok=True)
            with open(img_dest, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)
            
            image_ref = f"/assets/images/{img_name}"

        # 3. Process Tags (lav tekst om til liste)
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

        # 4. Opbyg Frontmatter (YAML) præcis efter dit format
        frontmatter = {
            "id": article_id,
            "title": title,
            "section": section,
            "type": type,
            "authors": [author],
            "teaser": teaser,
            "publish_at": dt.strftime('%d-%m-%Y %H:%M'),
            "status": status,
            "discord_announce": discord_announce,
            "tags": tag_list,
            "image": {
                "src": image_ref,
                "credit": image_credit,
                "source": image_source,
                "image_type": image_type
            },
            "kicker": "",
            "correction_of": "",
            "editor_note": "",
            "template": "news_article"
        }

        # Generer Markdown indhold
        md_output = "---\n"
        md_output += yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)
        md_output += "---\n"
        md_output += content

        # 5. Gem filen i mountet content volume
        save_path = f"/app/content/news/{year_folder}/{article_id}.md"
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(md_output)

        return JSONResponse({
            "status": "ok", 
            "message": f"Article '{title}' saved as {status}: {article_id}.md",
            "id": article_id
        })

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)