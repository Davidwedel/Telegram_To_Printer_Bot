import socket
import logging
import subprocess
import tempfile

from config import PRINTER_SUBNET, PRINTER_PORT

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
