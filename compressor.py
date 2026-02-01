# compressor.py
import io
import os
import hashlib
import shutil
import subprocess
import tempfile
from typing import Dict, Tuple,Optional

from PIL import Image
import pikepdf


# -------------------------
# Helpers
# -------------------------
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


from typing import Optional
import os, shutil

def _find_ghostscript_exe() -> Optional[str]:
    env_path = os.environ.get("GHOSTSCRIPT")
    if env_path and os.path.exists(env_path):
        return env_path

    for c in ["gswin64c.exe", "gswin64c", "gswin32c.exe", "gswin32c", "gs"]:
        exe = shutil.which(c)
        if exe:
            return exe
    return None



def _is_digitally_signed_pdf(data: bytes) -> bool:
    """
    Basit ve pratik kontrol:
    - /ByteRange görürsek çoğunlukla dijital imza vardır.
    Ghostscript ile rebuild imzayı bozar; o yüzden aggressive'i skip ederiz.
    """
    return b"/ByteRange" in data


def _count_text_ops_in_page(page) -> int:
    """
    PDF content stream içinde metin operatörlerini sayarak (Tj, TJ, Tf) kaba bir text yoğunluğu ölçer.
    """
    try:
        contents = page.get("/Contents")
        if contents is None:
            return 0

        # Contents tek stream veya array olabilir
        def _read_stream_bytes(obj) -> bytes:
            try:
                return obj.read_bytes()
            except Exception:
                return b""

        raw = b""
        if isinstance(contents, pikepdf.Array):
            for c in contents:
                raw += _read_stream_bytes(c)
        else:
            raw = _read_stream_bytes(contents)

        # Basit text operator sayımı
        return raw.count(b"Tj") + raw.count(b"TJ") + raw.count(b"Tf")
    except Exception:
        return 0


def is_scan_like_pdf(data: bytes, img_threshold: int = 2, text_ops_threshold: int = 10) -> bool:
    """
    Scan / image ağırlıklı PDF tespiti:
    - Sayfalardaki image XObject sayısı fazla mı?
    - Text operator (Tj/TJ/Tf) sayısı düşük mü?
    """
    try:
        with pikepdf.open(io.BytesIO(data)) as pdf:
            total_images = 0
            total_text_ops = 0

            for page in pdf.pages:
                # Image say
                try:
                    resources = page.get("/Resources") or {}
                    xobj = resources.get("/XObject") or {}
                    if isinstance(xobj, pikepdf.Dictionary):
                        for _, xo in xobj.items():
                            try:
                                # xo bir stream olabilir
                                subtype = xo.get("/Subtype")
                                if subtype == "/Image":
                                    total_images += 1
                            except Exception:
                                pass
                except Exception:
                    pass

                total_text_ops += _count_text_ops_in_page(page)

            # Heuristik karar
            if total_images >= img_threshold and total_text_ops <= text_ops_threshold:
                return True
            return False
    except Exception:
        # PDF okunamıyorsa scan diye varsaymak yerine conservative davran
        return False


# -------------------------
# Image optimization (JPEG/JPG)
# -------------------------
def optimize_jpeg(data: bytes, quality: int = 75, min_size_kb: int = 50) -> bytes:
    """
    JPEG'i yeniden encode eder:
    - quality düşürür
    - optimize/progressive
    - EXIF/metadata doğal olarak temizlenmiş olur
    """
    if len(data) < min_size_kb * 1024:
        return data

    try:
        img = Image.open(io.BytesIO(data))
        img = img.convert("RGB")

        out = io.BytesIO()
        img.save(out, format="JPEG", quality=quality, optimize=True, progressive=True)
        optimized = out.getvalue()
        return optimized if len(optimized) < len(data) else data
    except Exception:
        return data


# -------------------------
# PDF optimization (Conservative: pikepdf)
# -------------------------
def optimize_pdf_pikepdf(data: bytes, min_size_kb: int = 200) -> bytes:
    """
    pikepdf ile "hafif" optimize:
    - stream compress (sürüm uyumlu)
    """
    if len(data) < min_size_kb * 1024:
        return data

    try:
        input_io = io.BytesIO(data)
        output_io = io.BytesIO()
        with pikepdf.open(input_io) as pdf:
            pdf.save(output_io, compress_streams=True)
        optimized = output_io.getvalue()
        return optimized if len(optimized) < len(data) else data
    except Exception:
        return data


# -------------------------
# PDF optimization (Aggressive: Ghostscript)
# -------------------------
def optimize_pdf_ghostscript(
    data: bytes,
    preset: str = "ebook",
    min_size_kb: int = 200
) -> bytes:
    """
    Ghostscript ile agresif PDF rebuild.
    preset: screen | ebook | printer | prepress  (ghostscript PDFSETTINGS)
    """
    if len(data) < min_size_kb * 1024:
        return data

    gs = _find_ghostscript_exe()
    if not gs:
        return data

    # İmzalı PDF'yi bozma
    if _is_digitally_signed_pdf(data):
        return data

    preset = preset.lower().strip()
    if preset not in {"screen", "ebook", "printer", "prepress"}:
        preset = "ebook"

    with tempfile.TemporaryDirectory() as td:
        in_path = os.path.join(td, "in.pdf")
        out_path = os.path.join(td, "out.pdf")

        with open(in_path, "wb") as f:
            f.write(data)

        # iLovePDF benzeri yaklaşım: pdfwrite + PDFSETTINGS
        cmd = [
            gs,
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            f"-dPDFSETTINGS=/{preset}",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            f"-sOutputFile={out_path}",
            in_path
        ]

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(out_path):
                out_bytes = open(out_path, "rb").read()
                return out_bytes if len(out_bytes) < len(data) else data
            return data
        except Exception:
            return data


# -------------------------
# Main decision engine
# -------------------------
def compress_file(filename: str, data: bytes) -> Dict:
    """
    Akıllı karar motoru:
    - JPG/JPEG => re-encode
    - PDF => önce Ghostscript (iLovePDF benzeri), olmazsa pikepdf fallback
    """
    ext = os.path.splitext((filename or "").lower())[1]

    original_size = len(data)
    original_hash = sha256_bytes(data)

    algorithm = "none"
    optimized = data

    # ---- Images ----
    if ext in [".jpg", ".jpeg"]:
        optimized = optimize_jpeg(data, quality=75)
        algorithm = "jpeg_quality_75"

    # ---- PDFs ----
    elif ext == ".pdf":
        # 1) Önce Ghostscript dene (iLovePDF tarzı)
        gs_out = optimize_pdf_ghostscript(data, preset="ebook")
        if gs_out != data:
            optimized = gs_out
            algorithm = "pdf_gs_ebook"
        else:
            # 2) Olmazsa pikepdf fallback
            optimized = optimize_pdf_pikepdf(data)
            algorithm = "pdf_pikepdf"

    optimized_size = len(optimized)
    optimized_hash = sha256_bytes(optimized)

    return {
        "data": optimized,
        "algorithm": algorithm,
        "original_size": original_size,
        "optimized_size": optimized_size,
        "saving_ratio": round(1 - (optimized_size / original_size), 4)
        if optimized_size < original_size else 0,
        "original_hash": original_hash,
        "optimized_hash": optimized_hash,
    }

