import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
PASSWORD = os.environ["PASSWORD"]

PRINTER_SUBNET = os.getenv("PRINTER_SUBNET", "192.168.0")
PRINTER_PORT = int(os.getenv("PRINTER_PORT", "9100"))
