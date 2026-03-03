import io
import socket
import logging
import subprocess
import tempfile

from PIL import Image

from config import PRINTER_IP, PRINTER_SUBNET, PRINTER_PORT

logger = logging.getLogger(__name__)

_cached_printer_ip: str | None = None

PJL_HEADER = (
    b"\x1b%-12345X@PJL\r\n"
    b"@PJL RESET\r\n"
    b"@PJL SET PAPER=LETTER\r\n"
    b"@PJL ENTER LANGUAGE=PDF\r\n"
)
PJL_FOOTER = b"\x1b%-12345X"


def discover_printer() -> str | None:
    """Scan the printer subnet for an open port 9100. Return first hit."""
    global _cached_printer_ip

    # Use static IP if configured and reachable
    if PRINTER_IP:
        if _is_port_open(PRINTER_IP):
            logger.info("Using configured printer IP: %s", PRINTER_IP)
            return PRINTER_IP
        logger.warning("Configured PRINTER_IP %s is not reachable, falling back to scan", PRINTER_IP)

    # Try cached IP first
    if _cached_printer_ip and _is_port_open(_cached_printer_ip):
        return _cached_printer_ip

    logger.info("Scanning %s.0/24 for printer on port %d", PRINTER_SUBNET, PRINTER_PORT)
    for host in range(2, 255):
        ip = f"{PRINTER_SUBNET}.{host}"
        if _is_port_open(ip):
            logger.info("Found printer at %s", ip)
            _cached_printer_ip = ip
            return ip

    logger.warning("No printer found on subnet")
    return None


def _is_port_open(ip: str, timeout: float = 0.3) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((ip, PRINTER_PORT))
        return True
    except (OSError, TimeoutError):
        return False


def _fit_to_letter(pdf_bytes: bytes) -> bytes:
    """Use Ghostscript to reprocess a PDF to fit on Letter paper."""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as infile, \
         tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as outfile:
        infile.write(pdf_bytes)
        infile.flush()
        result = subprocess.run(
            [
                "gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER",
                "-sDEVICE=pdfwrite",
                "-sPAPERSIZE=letter",
                "-dFIXEDMEDIA",
                "-dPDFFitPage",
                f"-sOutputFile={outfile.name}",
                infile.name,
            ],
            capture_output=True,
        )
        if result.returncode != 0:
            logger.error("Ghostscript failed: %s", result.stderr.decode())
            raise RuntimeError("Failed to reprocess PDF to Letter size")
        with open(outfile.name, "rb") as f:
            return f.read()


LETTER_WIDTH = 2550   # 8.5" at 300 dpi
LETTER_HEIGHT = 3300  # 11"  at 300 dpi


def print_image(image_bytes: bytes) -> None:
    """Convert an image to a letter-sized PDF and print it."""
    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert("RGB")

    # Scale image to fit letter page preserving aspect ratio (both up and down)
    width_ratio = LETTER_WIDTH / img.width
    height_ratio = LETTER_HEIGHT / img.height
    scale_ratio = min(width_ratio, height_ratio)

    new_width = int(img.width * scale_ratio)
    new_height = int(img.height * scale_ratio)
    img = img.resize((new_width, new_height), Image.LANCZOS)

    # Center on white letter-sized background
    background = Image.new("RGB", (LETTER_WIDTH, LETTER_HEIGHT), (255, 255, 255))
    x = (LETTER_WIDTH - img.width) // 2
    y = (LETTER_HEIGHT - img.height) // 2
    background.paste(img, (x, y))

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        background.save(tmp, "PDF", resolution=300)
        tmp.flush()
        with open(tmp.name, "rb") as f:
            pdf_bytes = f.read()

    print_pdf(pdf_bytes)


def print_pdf(pdf_bytes: bytes) -> None:
    """Send a PDF to the printer via raw TCP on port 9100.

    Reprocesses the PDF to Letter size via Ghostscript, then sends it
    with a PJL reset to wake the Bizhub 223 from sleep mode.
    """
    ip = discover_printer()
    if ip is None:
        raise RuntimeError("Printer not found on the network")

    pdf_bytes = _fit_to_letter(pdf_bytes)
    logger.info("Reprocessed PDF to Letter size (%d bytes)", len(pdf_bytes))

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(30)
        s.connect((ip, PRINTER_PORT))
        s.sendall(PJL_HEADER)
        s.sendall(pdf_bytes)
        s.sendall(PJL_FOOTER)
    logger.info("Sent %d bytes to printer at %s", len(pdf_bytes), ip)
