import logging

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import BOT_TOKEN, PASSWORD
from printer import print_pdf

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

authenticated_chats: set[int] = set()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome! Send me the password to get started."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "1. Send the password to authenticate.\n"
        "2. Send a PDF file and I'll print it."
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id

    if update.message.text.strip() == PASSWORD:
        authenticated_chats.add(chat_id)
        await update.message.reply_text("Authenticated! You can now send PDF files.")
    elif chat_id not in authenticated_chats:
        await update.message.reply_text("Please send the password first.")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id

    if chat_id not in authenticated_chats:
        await update.message.reply_text("Please authenticate first by sending the password.")
        return

    doc = update.message.document
    if doc.mime_type != "application/pdf":
        await update.message.reply_text("Please send a PDF file.")
        return

    await update.message.reply_text("Printing...")

    try:
        file = await doc.get_file()
        pdf_bytes = await file.download_as_bytearray()
        print_pdf(bytes(pdf_bytes))
        await update.message.reply_text("Sent to printer.")
    except Exception:
        logger.exception("Print failed")
        await update.message.reply_text("Printing failed. Is the printer on?")


def main() -> None:
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    logger.info("Bot starting")
    app.run_polling()


if __name__ == "__main__":
    main()
