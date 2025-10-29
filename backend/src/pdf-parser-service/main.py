# # updated_parser.py
# from fastapi import FastAPI, HTTPException
# from fastapi.responses import JSONResponse
# import requests
# import pdfplumber
# from io import BytesIO
# import pytesseract
# from PIL import Image, ImageFilter, ImageOps
# from pymongo import MongoClient
# import os
# import re   # 🔹 ADDED: regex helpers
# from pydantic import BaseModel

# app = FastAPI()

# # MongoDB setup
# client = MongoClient(os.environ.get("MONGO_URI"))
# print("Connected to MongoDB" + str(client))
# db = client['research_paper_explorer']
# parsed_collection = db['parsed_papers']

# # Temporary folder for images
# FIGURE_FOLDER = "figures"
# os.makedirs(FIGURE_FOLDER, exist_ok=True)

# # Section headings
# SECTION_HEADINGS = [
#     "abstract", "introduction", "methods", "materials and methods",
#     "results", "discussion", "conclusion", "references"
# ]

# class ParseRequest(BaseModel):
#     cloudinary_url: str

# def serialize_doc(doc):
#     """Convert ObjectId to string for JSON serialization."""
#     doc["_id"] = str(doc["_id"])
#     return doc

# # 🔹 NEW: Improve matching of headings (same as before, kept)
# def match_heading(line: str):
#     line_clean = line.strip().lower()
#     for h in SECTION_HEADINGS:
#         if re.match(rf"^(\d+\.|\bI\b\.|\bII\b\.)?\s*{re.escape(h.lower())}\b", line_clean):
#             return True
#     return False

# # 🔹 NEW: image preprocessing to improve OCR
# def preprocess_pil_image(pil_img: Image.Image) -> Image.Image:
#     # Convert to grayscale, increase contrast, resize for better OCR accuracy
#     img = pil_img.convert("L")                      # grayscale
#     img = ImageOps.invert(img) if is_light_text_on_dark(img) else img
#     # Resize: enlarge small pages to help Tesseract
#     w, h = img.size
#     scale = max(1, int(2000 / max(w, h)))          # try to get a reasonable resolution
#     if scale > 1:
#         img = img.resize((w * scale, h * scale), Image.LANCZOS)
#     # Apply mild sharpening and despeckle
#     img = img.filter(ImageFilter.MedianFilter(size=3))
#     img = img.filter(ImageFilter.SHARPEN)
#     return img

# def is_light_text_on_dark(img: Image.Image) -> bool:
#     # Quick heuristic to detect inverted pages
#     # sample few pixels: if mean brightness < 128 -> probably dark bg
#     stat = ImageStat.Stat(img)
#     return stat.mean[0] < 120

# from PIL import ImageStat  # used in is_light_text_on_dark

# # 🔹 NEW: Clean OCR/text artifacts: hyphenation, newlines, whitespace, and a conservative merged-word fix
# def clean_extracted_text(raw: str) -> str:
#     if not raw:
#         return ""

#     text = raw

#     # 1) Fix hyphenation at line ends: "exam-\nple" -> "example"
#     #    Also handle "word-\n next" -> "word next"
#     text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)         # join hyphenated broken word
#     text = re.sub(r"(\w)-\s*\n\s+(\w)", r"\1 \2", text)       # conservative: hyphen + newline + space -> join with space

#     # 2) Replace remaining newlines with spaces where appropriate
#     #    But keep double newlines as paragraph breaks
#     text = re.sub(r"\n{2,}", "\n\n", text)                    # preserve paragraph breaks
#     text = re.sub(r"\n", " ", text)                           # replace single newlines with space

#     # 3) Collapse multiple spaces
#     text = re.sub(r"[ \t]{2,}", " ", text)

#     # 4) Conservative fix for some merged words where punctuation was lost:
#     #    Insert space between a lowercase letter followed by uppercase (e.g., "endOf" -> "end Of")
#     #    This is conservative and won't split "iPhone" etc. but reduces some runs.
#     text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)

#     # 5) Fix common OCR artifacts: 'ﬁ' ligatures, odd unicode
#     text = text.replace("\ufb01", "fi").replace("\ufb02", "ff").replace("ﬂ", "fl")

#     # 6) Trim
#     text = text.strip()
#     return text

# # 🔹 UPDATED parse endpoint with improved OCR, preprocessing and cleaning
# @app.post("/parse_pdf")
# async def parse_pdf(request: ParseRequest):
#     cloudinary_url = request.cloudinary_url
#     try:
#         # 1️⃣ Download PDF from Cloudinary
#         resp = requests.get(cloudinary_url, timeout=30)
#         if resp.status_code != 200:
#             raise HTTPException(status_code=400, detail="Failed to download PDF")
#         pdf_file = BytesIO(resp.content)

#         parsed_json = {
#             "title": "",
#             "authors": [],
#             "abstract": "",
#             "sections": [],
#             "figures": [],
#             "references": []
#         }

#         # 2️⃣ Extract text and images
#         full_text = ""
#         with pdfplumber.open(pdf_file) as pdf:
#             for page_num, page in enumerate(pdf.pages, start=1):
#                 # Try extracting text layer first
#                 text = page.extract_text()
#                 if not text or text.strip() == "":
#                     print(f"⚠️ No text layer on page {page_num}, using OCR with preprocessing...")
#                     # convert page to PIL image
#                     pil_page = page.to_image(resolution=200).original
#                     pil_page = preprocess_pil_image(pil_page)   # 🔹 ADDED: preprocess image before OCR
#                     # use tesseract with page segmentation mode and English
#                     try:
#                         # psm 1 = automatic page segmentation with OSD, psm 3 or 1 often works; psm 6 works for uniform blocks
#                         ocr_config = r"--psm 1 --oem 3 -c preserve_interword_spaces=1"
#                         text = pytesseract.image_to_string(pil_page, lang="eng", config=ocr_config)
#                     except Exception as exc:
#                         print("OCR failed on page", page_num, "->", exc)
#                         text = ""
#                 else:
#                     # If we have a text layer, we still sanitize it (remove strange line breaks)
#                     print(f"ℹ️ Using text layer for page {page_num}")

#                 # 🔹 CLEAN the extracted text (hyphenation, whitespace, merged-case heuristics)
#                 cleaned = clean_extracted_text(text)
#                 full_text += cleaned + "\n\n"

#                 # Extract images (figures)
#                 for i, img in enumerate(page.images):
#                     page_image = page.to_image(resolution=150)
#                     im = page_image.original.crop((img["x0"], img["top"], img["x1"], img["bottom"]))
#                     img_path = os.path.join(FIGURE_FOLDER, f"page{page_num}_img{i}.png")
#                     im.save(img_path)
#                     # OCR caption from figure after light preprocessing
#                     caption = ""
#                     try:
#                         fig_img = Image.open(img_path)
#                         fig_img = preprocess_pil_image(fig_img)   # 🔹 PREPROCESS figure before OCR
#                         caption = pytesseract.image_to_string(fig_img, lang="eng", config="--psm 6")
#                     except Exception:
#                         caption = "[OCR failed]"
#                     parsed_json["figures"].append({"imgPath": img_path, "caption": caption.strip()})

#         # Debug: print a preview
#         print("\n=== Extracted Text Preview ===")
#         print(full_text[:1000])
#         print("=== End Preview ===\n")

#         # 3️⃣ Extract sections (use match_heading)
#         sections = []
#         current_heading = None
#         current_text = ""
#         for line in full_text.split("\n"):
#             if match_heading(line):
#                 if current_heading:
#                     sections.append({"heading": current_heading, "text": current_text.strip()})
#                 current_heading = line.strip()
#                 current_text = ""
#             else:
#                 current_text += line + "\n"
#         if current_heading:
#             sections.append({"heading": current_heading, "text": current_text.strip()})
#         parsed_json["sections"] = sections

#         print("Detected Sections:", [s["heading"] for s in sections])

#         # 4️⃣ Title & Abstract (improved and conservative)
#         if sections:
#             parsed_json["title"] = sections[0]["text"].split("\n")[0][:250]
#             abstract_section = next((s for s in sections if "abstract" in s["heading"].lower()), None)
#             parsed_json["abstract"] = abstract_section["text"] if abstract_section else ""

#         # Fallbacks
#         if not parsed_json["title"]:
#             # take first non-empty line from full_text
#             first_line = next((ln.strip() for ln in full_text.split("\n") if ln.strip()), "")
#             parsed_json["title"] = first_line[:250]
#         if not parsed_json["abstract"]:
#             # try a regex to capture a block after 'abstract' word (conservative)
#             m = re.search(r"abstract[:\s]+(.*?)(\n{2,}|\Z)", full_text, re.IGNORECASE | re.DOTALL)
#             if m:
#                 parsed_json["abstract"] = m.group(1).strip()

#         # 5️⃣ Authors (improved but still heuristic)
#         if parsed_json["title"]:
#             lines = [ln.strip() for ln in full_text.split("\n") if ln.strip()]
#             try:
#                 idx = next(i for i, ln in enumerate(lines) if parsed_json["title"].strip() in ln)
#                 # authors commonly appear in next 1-4 lines — filter out lines that look like affiliations or empty
#                 candidate = []
#                 for ln in lines[idx+1: idx+6]:
#                     if ln and len(ln) < 120 and not re.search(r"\b(intro|abstract|index|keywords)\b", ln.lower()):
#                         candidate.append(ln)
#                 parsed_json["authors"] = candidate
#             except StopIteration:
#                 parsed_json["authors"] = []

#         # 6️⃣ References
#         ref_section = next((s for s in sections if "reference" in s["heading"].lower()), None)
#         if ref_section:
#             refs = [r.strip() for r in ref_section["text"].split("\n") if r.strip()]
#             parsed_json["references"] = refs

#         # 7️⃣ Save to MongoDB
#         print("Saving parsed JSON to MongoDB...")
#         inserted = parsed_collection.insert_one(parsed_json)
#         parsed_json["_id"] = str(inserted.inserted_id)
#         print("Saved with ID:", parsed_json["_id"])

#         print("parsed_json:", parsed_json)

#         return JSONResponse(content={"message": "PDF parsed successfully", "parsed": parsed_json})

#     except Exception as e:
#         print("❌ Exception during parsing:", str(e))
#         return JSONResponse(content={"error": str(e)}, status_code=500)

# updated_parser.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import requests
import pdfplumber
from io import BytesIO
import pytesseract
from PIL import Image, ImageFilter, ImageOps
from pymongo import MongoClient
import os
import re   # 🔹 ADDED: regex helpers
from pydantic import BaseModel

app = FastAPI()

# MongoDB setup
client = MongoClient(os.environ.get("MONGO_URI"))
print("Connected to MongoDB" + str(client))
db = client['research_paper_explorer']
parsed_collection = db['parsed_papers']

# Temporary folder for images
FIGURE_FOLDER = "figures"
os.makedirs(FIGURE_FOLDER, exist_ok=True)

# Section headings
SECTION_HEADINGS = [
    "abstract", "introduction", "methods", "materials and methods",
    "results", "discussion", "conclusion", "references"
]

class ParseRequest(BaseModel):
    cloudinary_url: str

def serialize_doc(doc):
    """Convert ObjectId to string for JSON serialization."""
    doc["_id"] = str(doc["_id"])
    return doc

# 🔹 NEW: Improve matching of headings (same as before, kept)
def match_heading(line: str):
    line_clean = line.strip().lower()
    for h in SECTION_HEADINGS:
        if re.match(rf"^(\d+\.|\bI\b\.|\bII\b\.)?\s*{re.escape(h.lower())}\b", line_clean):
            return True
    return False

# 🔹 NEW: image preprocessing to improve OCR
def preprocess_pil_image(pil_img: Image.Image) -> Image.Image:
    # Convert to grayscale, increase contrast, resize for better OCR accuracy
    img = pil_img.convert("L")                      # grayscale
    img = ImageOps.invert(img) if is_light_text_on_dark(img) else img
    # Resize: enlarge small pages to help Tesseract
    w, h = img.size
    scale = max(1, int(2000 / max(w, h)))          # try to get a reasonable resolution
    if scale > 1:
        img = img.resize((w * scale, h * scale), Image.LANCZOS)
    # Apply mild sharpening and despeckle
    img = img.filter(ImageFilter.MedianFilter(size=3))
    img = img.filter(ImageFilter.SHARPEN)
    return img

def is_light_text_on_dark(img: Image.Image) -> bool:
    # Quick heuristic to detect inverted pages
    # sample few pixels: if mean brightness < 128 -> probably dark bg
    stat = ImageStat.Stat(img)
    return stat.mean[0] < 120

from PIL import ImageStat  # used in is_light_text_on_dark

# 🔹 NEW: Clean OCR/text artifacts: hyphenation, newlines, whitespace, and a conservative merged-word fix
def clean_extracted_text(raw: str) -> str:
    if not raw:
        return ""

    text = raw

    # 1) Fix hyphenation at line ends: "exam-\nple" -> "example"
    #    Also handle "word-\n next" -> "word next"
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)         # join hyphenated broken word
    text = re.sub(r"(\w)-\s*\n\s+(\w)", r"\1 \2", text)       # conservative: hyphen + newline + space -> join with space

    # 2) Replace remaining newlines with spaces where appropriate
    #    But keep double newlines as paragraph breaks
    text = re.sub(r"\n{2,}", "\n\n", text)                    # preserve paragraph breaks
    text = re.sub(r"\n", " ", text)                           # replace single newlines with space

    # 3) Collapse multiple spaces
    text = re.sub(r"[ \t]{2,}", " ", text)

    # 4) Conservative fix for some merged words where punctuation was lost:
    #    Insert space between a lowercase letter followed by uppercase (e.g., "endOf" -> "end Of")
    #    This is conservative and won't split "iPhone" etc. but reduces some runs.
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)

    # 5) Fix common OCR artifacts: 'ﬁ' ligatures, odd unicode
    text = text.replace("\ufb01", "fi").replace("\ufb02", "ff").replace("ﬂ", "fl")

    # 6) Trim
    text = text.strip()
    return text

# 🔹 UPDATED parse endpoint with improved OCR, preprocessing and cleaning
@app.post("/parse_pdf")
async def parse_pdf(request: ParseRequest):
    cloudinary_url = request.cloudinary_url
    try:
        # 1️⃣ Download PDF from Cloudinary
        resp = requests.get(cloudinary_url, timeout=30)
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to download PDF")
        pdf_file = BytesIO(resp.content)

        parsed_json = {
            "title": "",
            "authors": [],
            "abstract": "",
            "sections": [],
            "figures": [],
            "references": []
        }

        # 2️⃣ Extract text and images
        full_text = ""
        with pdfplumber.open(pdf_file) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                # Try extracting text layer first
                text = page.extract_text()
                if not text or text.strip() == "":
                    print(f"⚠️ No text layer on page {page_num}, using OCR with preprocessing...")
                    # convert page to PIL image
                    pil_page = page.to_image(resolution=200).original
                    pil_page = preprocess_pil_image(pil_page)   # 🔹 ADDED: preprocess image before OCR
                    # use tesseract with page segmentation mode and English
                    try:
                        # psm 1 = automatic page segmentation with OSD, psm 3 or 1 often works; psm 6 works for uniform blocks
                        ocr_config = r"--psm 1 --oem 3 -c preserve_interword_spaces=1"
                        text = pytesseract.image_to_string(pil_page, lang="eng", config=ocr_config)
                    except Exception as exc:
                        print("OCR failed on page", page_num, "->", exc)
                        text = ""
                else:
                    # If we have a text layer, we still sanitize it (remove strange line breaks)
                    print(f"ℹ️ Using text layer for page {page_num}")

                # 🔹 CLEAN the extracted text (hyphenation, whitespace, merged-case heuristics)
                cleaned = clean_extracted_text(text)
                full_text += cleaned + "\n\n"

                # Extract images (figures)
                for i, img in enumerate(page.images):
                    page_image = page.to_image(resolution=150)
                    im = page_image.original.crop((img["x0"], img["top"], img["x1"], img["bottom"]))
                    img_path = os.path.join(FIGURE_FOLDER, f"page{page_num}_img{i}.png")
                    im.save(img_path)
                    # OCR caption from figure after light preprocessing
                    caption = ""
                    try:
                        fig_img = Image.open(img_path)
                        fig_img = preprocess_pil_image(fig_img)   # 🔹 PREPROCESS figure before OCR
                        caption = pytesseract.image_to_string(fig_img, lang="eng", config="--psm 6")
                    except Exception:
                        caption = "[OCR failed]"
                    parsed_json["figures"].append({"imgPath": img_path, "caption": caption.strip()})

        # Debug: print a preview
        print("\n=== Extracted Text Preview ===")
        print(full_text[:1000])
        print("=== End Preview ===\n")

        # 3️⃣ Extract sections (use match_heading)
        sections = []
        current_heading = None
        current_text = ""
        for line in full_text.split("\n"):
            if match_heading(line):
                if current_heading:
                    sections.append({"heading": current_heading, "text": current_text.strip()})
                current_heading = line.strip()
                current_text = ""
            else:
                current_text += line + "\n"
        if current_heading:
            sections.append({"heading": current_heading, "text": current_text.strip()})
        parsed_json["sections"] = sections

        print("Detected Sections:", [s["heading"] for s in sections])

        # 4️⃣ Title & Abstract (improved and conservative)
        if sections:
            parsed_json["title"] = sections[0]["text"].split("\n")[0][:250]
            abstract_section = next((s for s in sections if "abstract" in s["heading"].lower()), None)
            parsed_json["abstract"] = abstract_section["text"] if abstract_section else ""

        # Fallbacks
        if not parsed_json["title"]:
            # take first non-empty line from full_text
            first_line = next((ln.strip() for ln in full_text.split("\n") if ln.strip()), "")
            parsed_json["title"] = first_line[:250]
        if not parsed_json["abstract"]:
            # try a regex to capture a block after 'abstract' word (conservative)
            m = re.search(r"abstract[:\s]+(.*?)(\n{2,}|\Z)", full_text, re.IGNORECASE | re.DOTALL)
            if m:
                parsed_json["abstract"] = m.group(1).strip()

        # 5️⃣ Authors (improved but still heuristic)
        if parsed_json["title"]:
            lines = [ln.strip() for ln in full_text.split("\n") if ln.strip()]
            try:
                idx = next(i for i, ln in enumerate(lines) if parsed_json["title"].strip() in ln)
                # authors commonly appear in next 1-4 lines — filter out lines that look like affiliations or empty
                candidate = []
                for ln in lines[idx+1: idx+6]:
                    if ln and len(ln) < 120 and not re.search(r"\b(intro|abstract|index|keywords)\b", ln.lower()):
                        candidate.append(ln)
                parsed_json["authors"] = candidate
            except StopIteration:
                parsed_json["authors"] = []

        # 6️⃣ References
        ref_section = next((s for s in sections if "reference" in s["heading"].lower()), None)
        if ref_section:
            refs = [r.strip() for r in ref_section["text"].split("\n") if r.strip()]
            parsed_json["references"] = refs

        # 7️⃣ Save to MongoDB
        print("Saving parsed JSON to MongoDB...")
        inserted = parsed_collection.insert_one(parsed_json)
        parsed_json["_id"] = str(inserted.inserted_id)
        print("Saved with ID:", parsed_json["_id"])
        print("parsed_json:", parsed_json)

        return JSONResponse(content={"message": "PDF parsed successfully", "parsed": parsed_json})

    except Exception as e:
        print("❌ Exception during parsing:", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)