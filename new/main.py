from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from PIL import Image
import uuid
import os
from datetime import datetime
import re

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Configuration
BASE_IMAGE = "template.png"
OUTPUT_DIR = "wishing"
FONT_PATH = "fonts/Amiri-Regular.ttf"
EMOJI_FONT_PATH = "fonts/Segoe UI Emoji.ttf"

# Create output directory
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Register fonts
try:
    pdfmetrics.registerFont(TTFont('Amiri', FONT_PATH))
    pdfmetrics.registerFont(TTFont('Emoji', EMOJI_FONT_PATH))
    FONT_NAME = 'Amiri'
    EMOJI_FONT = 'Emoji'
except Exception as e:
    print(f"Font registration error: {e}")
    FONT_NAME = 'Helvetica'
    EMOJI_FONT = 'Helvetica'
# Text box coordinates
BOX_LEFT = 189
BOX_TOP = 289
BOX_RIGHT = 898
BOX_BOTTOM = 600
MARGIN = 20

MAX_WIDTH = BOX_RIGHT - BOX_LEFT - 2 * MARGIN

# Text styling - unified color
TEXT_COLOR = (118/255, 68/255, 68/255)  # Normalized RGB for ReportLab
FONT_SIZE_WISH = 28
FONT_SIZE_NAME = 32
LINE_SPACING = 10

# Emoji detection pattern
EMOJI_PATTERN = re.compile("["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002700-\U000027BF"
    "\U0001F900-\U0001F9FF"
    "\U00002600-\U000026FF"
    "\U0001F004-\U0001F9E6"
"]+", flags=re.UNICODE)

def has_emoji(text):
    """Check if text contains emoji"""
    return bool(EMOJI_PATTERN.search(text))

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

def calculate_text_width(c, text, font_name, emoji_font, font_size):
    """Calculate width of text with emoji support"""
    parts = split_text_emojis(text)
    total_width = 0
    for part_type, part in parts:
        if part_type == "text":
            total_width += c.stringWidth(part, font_name, font_size)
        else:
            total_width += c.stringWidth(part, emoji_font, font_size)
    return total_width

def wrap_text(c, text, font_name, emoji_font, font_size, max_width):
    """Wrap text to fit within specified width with emoji support"""
    words = text.split(' ')
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        text_width = calculate_text_width(c, test_line, font_name, emoji_font, font_size)
        
        if text_width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines

def draw_text_with_emoji(c, x, y, text, font_name, emoji_font, font_size, color):
    """Draw text with emoji support"""
    parts = split_text_emojis(text)
    current_x = x
    
    c.setFillColorRGB(*color)
    
    for part_type, part in parts:
        if part_type == "text":
            c.setFont(font_name, font_size)
            c.drawString(current_x, y, part)
            current_x += c.stringWidth(part, font_name, font_size)
        else:  # emoji
            c.setFont(emoji_font, font_size)
            c.drawString(current_x, y, part)
            current_x += c.stringWidth(part, emoji_font, font_size)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/submit")
async def submit(wish: str = Form(...), name: str = Form(...)):
    try:
        # Get template image dimensions
        template_img = Image.open(BASE_IMAGE)
        img_width, img_height = template_img.size
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '_')).strip()[:30]
        filename = f"{safe_name}_{timestamp}.pdf"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        # Create PDF canvas
        c = canvas.Canvas(filepath, pagesize=(img_width, img_height))
        
        # Draw template image as background
        c.drawImage(BASE_IMAGE, 0, 0, width=img_width, height=img_height)
        
        # Convert wish to uppercase
        wish_upper = wish
        wish_upper=f"'' {wish_upper} ''"
        # Wrap wish text
        wish_lines = wrap_text(c, wish_upper, FONT_NAME, EMOJI_FONT, FONT_SIZE_WISH, MAX_WIDTH)
        
        # Calculate total height for vertical centering
        total_text_height = len(wish_lines) * (FONT_SIZE_WISH + LINE_SPACING)
        
        # Starting Y position (ReportLab uses bottom-left origin)
        # Convert from top-left to bottom-left coordinate system
        y_start = img_height - BOX_TOP - MARGIN - (total_text_height // 3)
        y_position = y_start -200
        
        # Draw wish lines (center aligned, uppercase)
        for line in wish_lines:
            line_width = calculate_text_width(c, line, FONT_NAME, EMOJI_FONT, FONT_SIZE_WISH)
            x_position = BOX_LEFT + MARGIN + (MAX_WIDTH - line_width) / 2
            
            draw_text_with_emoji(c, x_position, y_position, line, FONT_NAME, EMOJI_FONT, FONT_SIZE_WISH, TEXT_COLOR)
            y_position -= (FONT_SIZE_WISH + LINE_SPACING)
        
        # Draw name (center aligned)
        y_position -= 25  # Extra space before name
        name_width = calculate_text_width(c, name, FONT_NAME, EMOJI_FONT, FONT_SIZE_NAME)
        name_x = BOX_LEFT + MARGIN + (MAX_WIDTH - name_width) / 2
        
        draw_text_with_emoji(c, name_x, y_position-100, name, FONT_NAME, EMOJI_FONT, FONT_SIZE_NAME, TEXT_COLOR)
        
        # Save PDF
        c.save()
        
        return FileResponse(filepath, media_type="application/pdf", filename=filename)
        
    except Exception as e:
        return {"error": str(e), "details": "Check font paths and template image"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)