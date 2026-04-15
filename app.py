import io
import os

import easyocr
import fitz  # PyMuPDF
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

# Initialize EasyOCR reader once at startup (downloads model on first run)
print("EasyOCRモデルを読み込んでいます...")
reader = easyocr.Reader(["ja", "en"], gpu=False)
print("準備完了")

app = FastAPI(title="手書き文字認識アプリ")

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


def image_bytes_to_array(image_bytes: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return np.array(img)


def pdf_to_images(pdf_bytes: bytes, dpi: int = 150) -> list[bytes]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    for page in doc:
        pix = page.get_pixmap(matrix=mat)
        images.append(pix.tobytes("png"))
    doc.close()
    return images


def recognize_image(image_bytes: bytes) -> str:
    img_array = image_bytes_to_array(image_bytes)
    results = reader.readtext(img_array, paragraph=True)
    lines = [text for (_, text, _) in results]
    return "\n".join(lines) if lines else "（文字を検出できませんでした）"


@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = os.path.join("static", "index.html")
    if os.path.exists(html_path):
        with open(html_path, encoding="utf-8") as f:
            return f.read()
    return HTMLResponse("<h1>static/index.html が見つかりません</h1>", status_code=500)


@app.post("/recognize")
async def recognize(
    file: UploadFile = File(...),
    pages: str = Form(""),
):
    filename = (file.filename or "").lower()
    ext = os.path.splitext(filename)[1]

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="PDF・PNG・JPGファイルをアップロードしてください",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="ファイルが空です")

    # --- Image file (single page) ---
    if ext in {".png", ".jpg", ".jpeg"}:
        text = recognize_image(file_bytes)
        return {"total_pages": 1, "results": [{"page": 1, "text": text}]}

    # --- PDF file ---
    try:
        images = pdf_to_images(file_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"PDF読み込みエラー: {e}")

    total_pages = len(images)

    # Parse page selection
    selected: list[int] = []
    if pages.strip():
        for part in pages.split(","):
            part = part.strip()
            if "-" in part:
                start_s, end_s = part.split("-", 1)
                selected.extend(range(int(start_s), int(end_s) + 1))
            elif part.isdigit():
                selected.append(int(part))
        selected = sorted({p for p in selected if 1 <= p <= total_pages})
    else:
        selected = list(range(1, total_pages + 1))

    if not selected:
        raise HTTPException(status_code=400, detail="有効なページが選択されていません")

    results = []
    for page_num in selected:
        text = recognize_image(images[page_num - 1])
        results.append({"page": page_num, "text": text})

    return {"total_pages": total_pages, "results": results}
