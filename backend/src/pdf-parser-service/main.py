from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import requests
import pdfplumber
from io import BytesIO
import pytesseract
from PIL import Image
from pymongo import MongoClient
import os
from pydantic import BaseModel

app = FastAPI()

# MongoDB setup
client = MongoClient(os.environ.get("MONGO_URI"))
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

@app.post("/parse_pdf")
async def parse_pdf(request: ParseRequest):
    cloudinary_url = request.cloudinary_url
    try:
        # 1️⃣ Download PDF from Cloudinary
        resp = requests.get(cloudinary_url)
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
                # Extract text
                text = page.extract_text() or ""
                full_text += text + "\n"

                # Extract images
                for i, img in enumerate(page.images):
                    page_image = page.to_image(resolution=150)
                    im = page_image.original.crop((img["x0"], img["top"], img["x1"], img["bottom"]))
                    img_path = os.path.join(FIGURE_FOLDER, f"page{page_num}_img{i}.png")
                    im.save(img_path)

                    # OCR text from figure (if pytesseract installed)
                    caption = ""
                    try:
                        caption = pytesseract.image_to_string(Image.open(img_path))
                    except Exception:
                        caption = "[OCR failed]"

                    parsed_json["figures"].append({"imgPath": img_path, "caption": caption.strip()})

        # 3️⃣ Extract sections
        sections = []
        current_heading = None
        current_text = ""
        for line in full_text.split("\n"):
            line_lower = line.strip().lower()
            if line_lower in SECTION_HEADINGS:
                if current_heading:
                    sections.append({"heading": current_heading, "text": current_text.strip()})
                current_heading = line.strip()
                current_text = ""
            else:
                current_text += line + "\n"
        if current_heading:
            sections.append({"heading": current_heading, "text": current_text.strip()})
        parsed_json["sections"] = sections

        # 4️⃣ Title & Abstract
        if sections:
            parsed_json["title"] = sections[0]["text"].split("\n")[0]
            abstract_section = next((s for s in sections if s["heading"].lower() == "abstract"), None)
            parsed_json["abstract"] = abstract_section["text"] if abstract_section else ""

        # 5️⃣ Authors (lines between title and abstract)
        if sections and abstract_section:
            title_lines = sections[0]["text"].split("\n")
            parsed_json["authors"] = title_lines[1:len(title_lines)]

        # 6️⃣ References
        ref_section = next((s for s in sections if s["heading"].lower() == "references"), None)
        if ref_section:
            refs = [r.strip() for r in ref_section["text"].split("\n") if r.strip()]
            parsed_json["references"] = refs

        # 7️⃣ Save to MongoDB and serialize ObjectId
        print("Saving parsed JSON to MongoDB")
        inserted = parsed_collection.insert_one(parsed_json)
        print("Parsed JSON saved with ID:", inserted.inserted_id)
        parsed_json["_id"] = str(inserted.inserted_id)

        return JSONResponse(content={"message": "PDF parsed successfully", "parsed": parsed_json})

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
