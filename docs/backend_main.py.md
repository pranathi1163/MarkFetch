# `main.py`

> **Path:** `backend/main.py`  
> **Last documented:** 2026-06-29 18:02

---

## Dependencies / Imports

- `fastapi.FastAPI`
- `fastapi.File`
- `fastapi.HTTPException`
- `fastapi.UploadFile`
- `fastapi.middleware.cors.CORSMiddleware`
- `fastapi.responses.FileResponse`
- `os`
- `pydantic.BaseModel`
- `pypdf.PdfReader`
- `typing.Any`
- `typing.Dict`
- `typing.List`
- `uuid`
- `uvicorn`

## Classes

### `Highlight` — line 24

### `UploadResponse` — line 31

## Functions

### `async upload_pdf(file)` — line 38
**Decorator:** `@app.post('/api/upload', response_model=UploadResponse)`  

### `async get_pdf(filename)` — line 170
**Decorator:** `@app.get('/api/pdf/{filename}')`  

### `visitor_text(t, cm, tm, font_dict, font_size)` — line 123
