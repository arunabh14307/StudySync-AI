"""
PDF and Document Processing Engine for StudySync AI.
Uses PyMuPDF (fitz) to extract text page-by-page, inspect metadata,
detect scanned documents requiring OCR, and enforce file-size and page limits.
"""

from typing import Dict, Any, List, Optional
import fitz  # PyMuPDF

# Safety limits for processing on local machine
MAX_PDF_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_TXT_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_PAGE_LIMIT = 150                   # 150 pages
ALLOWED_EXTENSIONS = {".pdf", ".txt"}


def format_file_size(size_bytes: int) -> str:
    """Formats file size into human-readable units (Bytes, KB, MB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{round(size_bytes / 1024, 1)} KB"
    else:
        return f"{round(size_bytes / (1024 * 1024), 2)} MB"


def format_pdf_date(date_str: Optional[str]) -> str:
    """Converts PyMuPDF date strings (e.g. D:20240115123000) to ISO-like YYYY-MM-DD HH:MM."""
    if not date_str or not isinstance(date_str, str):
        return ""
    clean = date_str.strip()
    if clean.startswith("D:"):
        clean = clean[2:]
    if len(clean) >= 8:
        year = clean[0:4]
        month = clean[4:6]
        day = clean[6:8]
        if len(clean) >= 12:
            hour = clean[8:10]
            minute = clean[10:12]
            return f"{year}-{month}-{day} {hour}:{minute}"
        return f"{year}-{month}-{day}"
    return date_str


def validate_uploaded_file(file_name: str, file_size: int, file_bytes: Optional[bytes] = None) -> Dict[str, Any]:
    """
    Validates file extension, size limits, and basic integrity checks.
    
    Returns:
        Dict[str, Any]: {
            "valid": bool,
            "error": Optional[str],
            "file_type": str,
            "file_size_formatted": str
        }
    """
    if not file_name or "." not in file_name:
        return {
            "valid": False,
            "error": "The uploaded file does not have a recognizable file extension. Please upload a .pdf or .txt file.",
            "file_type": "unknown",
            "file_size_formatted": format_file_size(file_size)
        }

    ext = "." + file_name.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return {
            "valid": False,
            "error": f"Unsupported file format '{ext}'. StudySync AI currently supports PDF (.pdf) and Plain Text (.txt) study documents.",
            "file_type": ext,
            "file_size_formatted": format_file_size(file_size)
        }

    # Size validations
    if file_size <= 0:
        return {
            "valid": False,
            "error": "The uploaded file is empty (0 bytes). Please upload a document with study content.",
            "file_type": ext,
            "file_size_formatted": "0 B"
        }

    if ext == ".pdf" and file_size > MAX_PDF_SIZE_BYTES:
        return {
            "valid": False,
            "error": f"The PDF file '{file_name}' ({format_file_size(file_size)}) exceeds the maximum allowed limit of {MAX_PDF_SIZE_BYTES // (1024 * 1024)} MB. Please upload a smaller document.",
            "file_type": ext,
            "file_size_formatted": format_file_size(file_size)
        }

    if ext == ".txt" and file_size > MAX_TXT_SIZE_BYTES:
        return {
            "valid": False,
            "error": f"The text file '{file_name}' ({format_file_size(file_size)}) exceeds the maximum allowed limit of {MAX_TXT_SIZE_BYTES // (1024 * 1024)} MB. Please upload a smaller document.",
            "file_type": ext,
            "file_size_formatted": format_file_size(file_size)
        }

    # Header integrity check for PDF
    if ext == ".pdf" and file_bytes is not None:
        if len(file_bytes) < 4 or not file_bytes.startswith(b'%PDF'):
            return {
                "valid": False,
                "error": "Invalid file format. The file does not have a valid PDF header (%PDF-). It may be corrupted or disguised as a PDF.",
                "file_type": ext,
                "file_size_formatted": format_file_size(file_size)
            }

    return {
        "valid": True,
        "error": None,
        "file_type": ext,
        "file_size_formatted": format_file_size(file_size)
    }


def extract_text_from_pdf(pdf_bytes: bytes, max_pages: int = MAX_PAGE_LIMIT) -> Dict[str, Any]:
    """
    Extracts selectable text and metadata page-by-page from PDF bytes using PyMuPDF.

    Returns:
        Dict[str, Any]: {
            "success": bool,
            "text": str,
            "page_count": int,
            "pages": List[str],
            "metadata": Dict[str, Any],
            "is_scanned": bool,
            "error": Optional[str]
        }
    """
    if not pdf_bytes or len(pdf_bytes) == 0:
        return {
            "success": False,
            "text": "",
            "page_count": 0,
            "pages": [],
            "metadata": {},
            "is_scanned": False,
            "error": "The uploaded PDF file is empty (0 bytes)."
        }

    # Verify file-size limit
    if len(pdf_bytes) > MAX_PDF_SIZE_BYTES:
        return {
            "success": False,
            "text": "",
            "page_count": 0,
            "pages": [],
            "metadata": {},
            "is_scanned": False,
            "error": f"File exceeds maximum allowed size ({MAX_PDF_SIZE_BYTES // (1024 * 1024)} MB). Please upload a smaller document."
        }

    # Verify PDF magic header bytes: %PDF-
    if not pdf_bytes.startswith(b'%PDF'):
        return {
            "success": False,
            "text": "",
            "page_count": 0,
            "pages": [],
            "metadata": {},
            "is_scanned": False,
            "error": "Invalid file format. The uploaded file does not have a valid PDF header (%PDF-)."
        }

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        if doc.is_encrypted:
            return {
                "success": False,
                "text": "",
                "page_count": 0,
                "pages": [],
                "metadata": {},
                "is_scanned": False,
                "error": "The PDF file is encrypted or password-protected. Please upload an unlocked PDF document."
            }

        total_pages = len(doc)
        if total_pages == 0:
            return {
                "success": False,
                "text": "",
                "page_count": 0,
                "pages": [],
                "metadata": {},
                "is_scanned": False,
                "error": "The PDF document contains 0 pages."
            }

        pages_to_process = min(total_pages, max_pages)
        pages_text: List[str] = []
        full_text_chunks: List[str] = []
        total_images_found = 0

        for page_idx in range(pages_to_process):
            page = doc[page_idx]
            page_text = page.get_text("text") or ""
            cleaned_page = page_text.strip()
            pages_text.append(cleaned_page)

            if cleaned_page:
                full_text_chunks.append(f"--- Page {page_idx + 1} ---\n{cleaned_page}")

            # Check if page has images
            images = page.get_images()
            total_images_found += len(images)

        full_text = "\n\n".join(full_text_chunks).strip()

        meta = doc.metadata or {}
        cleaned_meta = {
            "title": meta.get("title") or "Untitled Document",
            "author": meta.get("author") or "Unknown Author",
            "subject": meta.get("subject") or "General Study Material",
            "keywords": meta.get("keywords") or "",
            "creator": meta.get("creator") or "",
            "producer": meta.get("producer") or "",
            "creation_date": format_pdf_date(meta.get("creationDate")),
            "modification_date": format_pdf_date(meta.get("modDate")),
            "page_count": total_pages,
            "file_size_bytes": len(pdf_bytes),
            "file_size_formatted": format_file_size(len(pdf_bytes)),
            "total_images": total_images_found
        }

        doc.close()

        # Check for scanned / non-selectable text documents
        total_words = len(full_text.split())
        is_scanned = total_images_found > 0 and total_words < 10

        if not full_text or is_scanned:
            err_msg = (
                "Scanned Document Detected: No selectable or digital text was found in this PDF. "
                "This document appears to be composed of scanned page images or photographs without an embedded text layer. "
                "Standard PDF extraction requires an underlying digital text stream. To extract notes from this document, "
                "Optical Character Recognition (OCR) is required (e.g. using Adobe Acrobat OCR, Google Drive OCR, or Tesseract) "
                "to recognize the text, or you can paste the text manually into the Manual Note Editor."
                if (total_images_found > 0 or is_scanned) else
                "The PDF document contains blank pages with no extractable text."
            )
            return {
                "success": False,
                "text": "",
                "page_count": total_pages,
                "pages": pages_text,
                "metadata": cleaned_meta,
                "is_scanned": total_images_found > 0 or is_scanned,
                "error": err_msg
            }

        return {
            "success": True,
            "text": full_text,
            "page_count": total_pages,
            "pages": pages_text,
            "metadata": cleaned_meta,
            "is_scanned": False,
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "text": "",
            "page_count": 0,
            "pages": [],
            "metadata": {},
            "is_scanned": False,
            "error": f"Failed to parse PDF document (corrupted or malformed file): {str(e)}"
        }


def extract_text_from_txt(txt_bytes: bytes, file_name: str = "document.txt", encoding: str = 'utf-8') -> Dict[str, Any]:
    """
    Extracts text from uploaded plain text (.txt) file bytes.
    Tries utf-8 first, falls back to latin-1 if decoding error occurs.
    """
    if not txt_bytes or len(txt_bytes) == 0:
        return {
            "success": False,
            "text": "",
            "page_count": 1,
            "pages": [],
            "metadata": {"title": "Text File", "author": "Unknown", "file_size_formatted": "0 B"},
            "is_scanned": False,
            "error": "The uploaded text file is empty (0 bytes)."
        }

    # Size limit validation
    if len(txt_bytes) > MAX_TXT_SIZE_BYTES:
        return {
            "success": False,
            "text": "",
            "page_count": 0,
            "pages": [],
            "metadata": {},
            "is_scanned": False,
            "error": f"File exceeds maximum allowed size for text files ({MAX_TXT_SIZE_BYTES // (1024 * 1024)} MB)."
        }

    try:
        try:
            content = txt_bytes.decode(encoding)
        except UnicodeDecodeError:
            content = txt_bytes.decode('latin-1')

        content = content.strip()
        if not content:
            return {
                "success": False,
                "text": "",
                "page_count": 1,
                "pages": [],
                "metadata": {"title": "Text File", "author": "Unknown", "file_size_formatted": format_file_size(len(txt_bytes))},
                "is_scanned": False,
                "error": "The text file contains only whitespace."
            }

        title_derived = file_name.rsplit(".", 1)[0].replace("_", " ").title() if file_name else "Plain Text Notes"
        meta = {
            "title": title_derived,
            "author": "User Upload",
            "subject": "General Study Material",
            "file_size_bytes": len(txt_bytes),
            "file_size_formatted": format_file_size(len(txt_bytes)),
            "line_count": len(content.splitlines()),
            "word_count": len(content.split())
        }

        return {
            "success": True,
            "text": content,
            "page_count": 1,
            "pages": [content],
            "metadata": meta,
            "is_scanned": False,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "text": "",
            "page_count": 0,
            "pages": [],
            "metadata": {},
            "is_scanned": False,
            "error": f"Failed to read text file: {str(e)}"
        }
