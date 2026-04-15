import base64
import io
import os
from typing import Optional

import anthropic
import fitz  # PyMuPDF
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

app = FastAPI(title="手書き文字認識アプリ")

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

client = anthropic.Anthropic()

SYSTEM_PROMPT = """あなたは手書き文字の読み取り（OCR）の専門家です。
手書きの日本語（ひらがな・カタカナ・漢字・数字・英字）を正確に読み取ってください。

以下の点に注意してください：
- 表形式の場合は、表の構造を維持してテキスト化してください
- 印鑑や押印が文字に重なっていても、下の文字を読み取ってください
- 文字が不鮮明・かすれている場合は、文脈から最も適切な文字を推定してください
- 読み取れない文字は「□」で表してください
- 縦書き・横書きどちらにも対応してください
- 認識したテキストのみを出力し、余分な説明は不要です"""


def pdf_to_images(pdf_bytes: bytes, dpi: int = 150) -> list[bytes]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    for page in doc:
        pix = page.get_pixmap(matrix=mat)
        images.append(pix.tobytes("png"))
    doc.close()
    return images


def recognize_image(image_bytes: bytes, page_num: int, hint: Optional[str]) -> str:
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    user_content: list = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": b64,
            },
        },
        {
            "type": "text",
            "text": (
                f"この画像（{page_num}ページ目）の手書き文字を読み取ってテキストに変換してください。"
                + (f"\n\nヒント・補足情報: {hint}" if hint else "")
            ),
        },
    ]

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_content}],
    )
    return response.content[0].text


ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


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
    hint: Optional[str] = Form(None),
    pages: Optional[str] = Form(None),
):
    filename = (file.filename or "").lower()
    ext = os.path.splitext(filename)[1]

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="PDF・PNG・JPGファイルをアップロードしてください")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="ファイルが空です")

    # 画像ファイルの場合はそのまま処理
    if ext in {".png", ".jpg", ".jpeg"}:
        # PNGに統一して送る
        img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        text = recognize_image(buf.getvalue(), 1, hint)
        return {"total_pages": 1, "results": [{"page": 1, "text": text}]}

    # PDFの場合
    try:
        images = pdf_to_images(file_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"PDF読み込みエラー: {e}")

    total_pages = len(images)

    selected: list[int] = []
    if pages and pages.strip():
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
        text = recognize_image(images[page_num - 1], page_num, hint)
        results.append({"page": page_num, "text": text})

    return {"total_pages": total_pages, "results": results}
