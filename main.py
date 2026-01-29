from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageDraw, ImageFont
import uuid
import os
import re
import sqlite3
from datetime import datetime
import io
import base64

app = FastAPI()
templates = Jinja2Templates(directory="templates")

BASE_IMAGE = "template.png"
OUTPUT_DIR = "/tmp/wishing"  # Changed to /tmp for serverless
FONT_PATH = "fonts/Amiri-Regular.ttf"       # Arabic + English
EMOJI_FONT_PATH = "fonts/Segoe UI Emoji.TTF" # Emojis

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ===== TEXT BOX =====
BOX_LEFT   = 189
BOX_TOP    = 289
BOX_RIGHT  = 898
BOX_BOTTOM = 600
MARGIN = 20

MAX_WIDTH  = BOX_RIGHT - BOX_LEFT - 2 * MARGIN
MAX_HEIGHT = BOX_BOTTOM - BOX_TOP - 2 * MARGIN

COLOR = (118, 68, 68)

# ===== Emoji detection =====
EMOJI_PATTERN = re.compile("["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002700-\U000027BF"
    "\U0001F900-\U0001F9FF"
    "\U00002600-\U000026FF"
"]+", flags=re.UNICODE)

def split_text_emojis(text):
    """Split text into normal text and emojis"""
    parts = EMOJI_PATTERN.split(text)
    emojis = EMOJI_PATTERN.findall(text)
    result = []
    for i, part in enumerate(parts):
        if part:
            result.append(("text", part))
        if i < len(emojis):
            result.append(("emoji", emojis[i]))
    return result

# ===== Text wrapping =====
def wrap_text(draw, text, font, max_width):
    words = text.split(" ")
    lines = []
    current = ""
    for word in words:
        test = current + (" " if current else "") + word
        w = draw.textbbox((0, 0), test, font=font)[2]
        if w <= max_width:
            current = test
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines

# ===== Fit text inside box =====
def fit_text(draw, text, start_size):
    font_size = start_size
    while font_size >= 18:
        font = ImageFont.truetype(FONT_PATH, font_size)
        lines = wrap_text(draw, text, font, MAX_WIDTH)
        line_height = font.getbbox("Ay")[3]
        total_height = len(lines) * (line_height + 10)
        if total_height <= MAX_HEIGHT:
            return font, lines
        font_size -= 2
    return font, lines

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/submit")
def submit(wish: str = Form(...), name: str = Form(...)):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # ===== Save to SQLite before generating template =====
    # Using /tmp for serverless environment
    db_path = "/tmp/wishes.db"
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        # Create table if it doesn't exist
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS wishes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                wishing TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        # Insert new record
        cur.execute(
            "INSERT INTO wishes (name, wishing, created_at) VALUES (?, ?, ?)",
            (name, wish, current_time),
        )
        conn.commit()
    finally:
        conn.close()

    # Open image
    img = Image.open(BASE_IMAGE).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # Prepare name
    prepared_name = f"{name}"

    # Text alignment
    align = "la"
    text_x = BOX_LEFT + MARGIN

    # ===== Draw wish =====
    
    font, lines = fit_text(draw, wish, start_size=65)
    emoji_font = ImageFont.truetype(EMOJI_FONT_PATH, font.size)
    y = BOX_TOP + MARGIN

    for line in lines:
        parts = split_text_emojis(line)
        cursor_x = text_x
        for part_type, part in parts:
            if part_type == "text":
                draw.text((cursor_x, y), part, font=font, fill=COLOR, anchor="la",align="center")
                cursor_x += draw.textbbox((0,0), part, font=font)[2]
            else:  # emoji
                draw.text((cursor_x, y), part, font=emoji_font, fill=COLOR, anchor="la")
                cursor_x += draw.textbbox((0,0), part, font=emoji_font)[2]
        y += font.getbbox("Ay")[3] + 10

    # ===== Draw name =====
    name_font = ImageFont.truetype(FONT_PATH, 55)
    draw.text(
        (((BOX_LEFT+BOX_RIGHT)/2)-85, y+150),
        prepared_name,
        font=name_font,
        fill=COLOR,
        anchor="la"
    )

    # ===== Save to BytesIO instead of file for serverless =====
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    filename = f"{prepared_name}_{current_time}.png"
    
    return Response(
        content=img_io.getvalue(),
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )

# This is required for Vercel
handler = app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
