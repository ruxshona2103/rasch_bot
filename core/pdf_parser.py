import fitz  # PyMuPDF


def pdf_to_png_pages(pdf_bytes: bytes, dpi: int = 200) -> list[bytes]:
    """1 sahifa = 1 savol qoidasi bo'yicha PDF'ni PNG sahifalarga ajratadi."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    pages: list[bytes] = []
    try:
        for page in doc:
            pixmap = page.get_pixmap(matrix=matrix)
            pages.append(pixmap.tobytes("png"))
    finally:
        doc.close()
    return pages
