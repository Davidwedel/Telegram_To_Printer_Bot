import hmac
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
from db import authorize_user, init_db, is_authorized
from printer import print_pdf

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Welcome! Send me a PDF file to print.")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Send a PDF file to print.\n"
        "New users will be asked for a password once."
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pending = context.user_data.get("pending_doc")
    if not pending:
        await update.message.reply_text("Send me a PDF file to print.")
        return

    if hmac.compare_digest(update.message.text.strip(), PASSWORD):
        user = update.effective_user
        authorize_user(user.id, user.username)
        context.user_data.pop("pending_doc")
        logger.info("Authorized user %s (%s)", user.id, user.username)
        await update.message.reply_text("Authenticated! Printing...")
        try:
            file = await pending.get_file()
            pdf_bytes = await file.download_as_bytearray()
            print_pdf(bytes(pdf_bytes))
            await update.message.reply_text("Sent to printer.")
        except Exception:
            logger.exception("Print failed")
            await update.message.reply_text("Printing failed. Is the printer on?")
    else:
        context.user_data.pop("pending_doc")
        await update.message.reply_text("Wrong password. File rejected.")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    doc = update.message.document
    if doc.mime_type != "application/pdf":
        await update.message.reply_text("Please send a PDF file.")
        return

    user_id = update.effective_user.id
    if is_authorized(user_id):
        await update.message.reply_text("Printing...")
        try:
            file = await doc.get_file()
            pdf_bytes = await file.download_as_bytearray()
            print_pdf(bytes(pdf_bytes))
            await update.message.reply_text("Sent to printer.")
        except Exception:
            logger.exception("Print failed")
            await update.message.reply_text("Printing failed. Is the printer on?")
    else:
        context.user_data["pending_doc"] = doc
        await update.message.reply_text("Send the password to print this file.")


def main() -> None:
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    logger.info("Bot starting")
    app.run_polling()


if __name__ == "__main__":
    main()
