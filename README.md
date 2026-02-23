# Telegram Print Bot

A Telegram bot that prints PDF files on a network printer (Konica Minolta Bizhub 223), designed to run on a Raspberry Pi.

## How It Works

1. Send a PDF to the bot on Telegram
2. First-time users authenticate with a password (stored in SQLite)
3. The bot auto-discovers the printer on the local subnet via port 9100
4. PDFs are reprocessed to Letter size with Ghostscript, then sent over raw TCP using PJL

## Setup

### Requirements

- Raspberry Pi (or any Linux host) connected to the printer via Ethernet
- Python 3.12+
- Ghostscript (`sudo apt install ghostscript`)

### Network

Run once to configure a static IP and DHCP server on `eth0` for the printer LAN:

```bash
sudo bash setup_network.sh
```

### Bot

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file:

```
BOT_TOKEN=<your Telegram bot token>
PASSWORD=<password for user authentication>
```

Run:

```bash
python bot.py
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | *required* | Telegram Bot API token |
| `PASSWORD` | *required* | Password users enter to authorize |
| `PRINTER_SUBNET` | `192.168.0` | First three octets of the printer subnet |
| `PRINTER_PORT` | `9100` | Raw printing port (PJL/PCL) |

## License

GNU AGPL v3 -- see [LICENSE](LICENSE).
