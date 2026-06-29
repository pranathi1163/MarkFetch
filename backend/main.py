import os
import uuid
from pypdf import PdfReader
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any

app = FastAPI(title="PDF Highlight Extractor API")

# Configure CORS so the frontend can easily make requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

class Highlight(BaseModel):
    id: str
    page_index: int
    text: str
    rect: List[float]  # [x0, y0, x1, y1] in top-left coordinate system
    color: List[float]  # [r, g, b]

class UploadResponse(BaseModel):
    filename: str
    pdf_url_path: str
    pages: Dict[int, Dict[str, float]]
    highlights: List[Highlight]

@app.post("/api/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    # Generate unique filename to avoid overwrites
    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    # Save the file
    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Parse the PDF for highlights
    try:
        reader = PdfReader(file_path)
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")
    
    pages_data = {}
    highlights_data = []
    highlight_counter = 0
    
    try:
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            
            # Fetch page dimensions from mediabox
            mb = page.mediabox
            width = float(mb.width)
            height = float(mb.height)
            
            pages_data[page_num] = {
                "width": width,
                "height": height
            }
            
            # Find annotations list
            annots = []
            if "/Annots" in page:
                annots_obj = page["/Annots"]
                if hasattr(annots_obj, "get_object"):
                    annots_obj = annots_obj.get_object()
                annots = annots_obj
            
            for annot_ref in annots:
                try:
                    annot = annot_ref.get_object()
                except Exception:
                    continue
                
                if annot and annot.get("/Subtype") == "/Highlight":
                    rect_data = annot.get("/Rect")
                    if not rect_data:
                        continue
                        
                    # Parse bounding box [x0, y0, x1, y1] (bottom-left to top-right)
                    x0_pdf, y0_pdf, x1_pdf, y1_pdf = [float(v) for v in rect_data]
                    
                    # Convert to top-left coordinate system (PDF.js standard viewport coordinates)
                    x0 = x0_pdf
                    y0 = height - y1_pdf
                    x1 = x1_pdf
                    y1 = height - y0_pdf
                    
                    # 1. Try /Contents field first (some PDF editors store highlighted text here)
                    text = ""
                    contents_val = annot.get("/Contents")
                    if contents_val:
                        if hasattr(contents_val, "get_object"):
                            contents_val = contents_val.get_object()
                        text = str(contents_val).strip()
                    
                    # 2. Fallback: use visitor pattern to collect only text within highlight rect
                    if not text:
                        parts = []
                        # Add a small tolerance margin around the rect
                        margin = 3.0
                        
                        def visitor_text(t, cm, tm, font_dict, font_size):
                            # tm[4] = x, tm[5] = y in PDF bottom-left coordinates
                            tx = tm[4]
                            ty = tm[5]
                            if (x0_pdf - margin <= tx <= x1_pdf + margin and
                                    y0_pdf - margin <= ty <= y1_pdf + margin):
                                parts.append(t)
                        
                        try:
                            page.extract_text(visitor_text=visitor_text)
                            text = "".join(parts).strip()
                        except Exception:
                            text = ""
                    
                    if not text:
                        text = "[No text extracted]"
                        
                    # Get highlight stroke color (default to yellow)
                    color = [1.0, 1.0, 0.0]
                    c_val = annot.get("/C")
                    if c_val:
                        if hasattr(c_val, "get_object"):
                            c_val = c_val.get_object()
                        color = [float(v) for v in c_val]
                        
                    highlights_data.append(Highlight(
                        id=f"h_{highlight_counter}",
                        page_index=page_num,
                        text=text,
                        rect=[x0, y0, x1, y1],
                        color=color
                    ))
                    highlight_counter += 1
                    
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Error extracting highlights: {str(e)}")
        
    return UploadResponse(
        filename=file.filename,
        pdf_url_path=safe_filename,
        pages=pages_data,
        highlights=highlights_data
    )

@app.get("/api/pdf/{filename}")
async def get_pdf(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="application/pdf", filename=filename)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
