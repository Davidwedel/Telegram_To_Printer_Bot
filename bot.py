import hmac
import logging
import traceback

import aiohttp
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import ADMIN_CHAT_ID, BOT_TOKEN, PASSWORD
from db import authorize_user, init_db, is_authorized
from printer import print_image, print_pdf

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def notify_admin(context: ContextTypes.DEFAULT_TYPE, message: str) -> None:
    if not ADMIN_CHAT_ID:
        return
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)
    except Exception:
        logger.exception("Failed to notify admin")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Welcome! Send me a PDF, image, or photo to print.")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Send a PDF, image, or photo to print.\n"
        "New users will be asked for a password once.\n"
        "Use /admin <message> to send a message to the admin."
    )


AUTH_SUCCESS_MSG = "Authenticated! Use /admin to contact the admin."


async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("You need to authenticate first. Send me a message to get started.")
        return
    if context.args:
        user = update.effective_user
        message = " ".join(context.args)
        await notify_admin(
            context,
            f"Message from user {user.id} (@{user.username}):\n{message}",
        )
        await update.message.reply_text("Your message has been sent to the admin.")
    else:
        context.user_data["awaiting_admin_msg"] = True
        await update.message.reply_text(
            "Your next message will be sent to the admin. Send /cancel to cancel."
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.pop("awaiting_admin_msg", None) or context.user_data.pop("awaiting_auth", None):
        context.user_data.pop("pending_doc", None)
        context.user_data.pop("pending_type", None)
        await update.message.reply_text("Cancelled.")
    else:
        await update.message.reply_text("Nothing to cancel.")


async def checkbell(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("You need to authenticate first. Send me a message to get started.")
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://192.168.0.215", timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    await update.message.reply_text("bell checked")
                else:
                    await update.message.reply_text("bell check failed")
    except Exception:
        logger.exception("Bell check failed")
        await update.message.reply_text("bell check failed")


async def _complete_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check password, authorize user, and handle the pending action. Returns True on success."""
    user = update.effective_user
    if not hmac.compare_digest(update.message.text.strip(), PASSWORD):
        context.user_data.pop("pending_doc", None)
        context.user_data.pop("pending_type", None)
        context.user_data.pop("awaiting_auth", None)
        await update.message.reply_text("Wrong password.")
        return False

    authorize_user(user.id, user.username)
    context.user_data.pop("awaiting_auth", None)
    logger.info("Authorized user %s (%s)", user.id, user.username)

    pending = context.user_data.pop("pending_doc", None)
    pending_type = context.user_data.pop("pending_type", "pdf")

    if pending is None:
        await update.message.reply_text(AUTH_SUCCESS_MSG + "\n\nSend me a PDF, image, or photo to print.")
        return True

    await update.message.reply_text(AUTH_SUCCESS_MSG + "\n\nPrinting...")
    try:
        file = await pending.get_file()
        data = bytes(await file.download_as_bytearray())
        if pending_type == "image":
            print_image(data)
        else:
            print_pdf(data)
        await update.message.reply_text("Sent to printer.")
    except Exception:
        logger.exception("Print failed")
        await update.message.reply_text("Printing failed. Is the printer on?")
        await notify_admin(
            context,
            f"Print failed (auth flow)\nUser: {user.id} (@{user.username})\n\n{traceback.format_exc()}",
        )
    return True


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.text.strip().lower() == "ping":
        await update.message.reply_text("ping")
        return

    if context.user_data.get("awaiting_auth"):
        await _complete_auth(update, context)
        return

    if not is_authorized(update.effective_user.id):
        context.user_data["awaiting_auth"] = True
        await update.message.reply_text("Please send the password to continue.")
        return

    if context.user_data.pop("awaiting_admin_msg", False):
        user = update.effective_user
        await notify_admin(
            context,
            f"Message from user {user.id} (@{user.username}):\n{update.message.text}",
        )
        await update.message.reply_text("Your message has been sent to the admin.")
        return

    await update.message.reply_text("Send me a PDF, image, or photo to print.")


IMAGE_MIME_TYPES = {"image/jpeg", "image/png"}


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    doc = update.message.document
    is_image = doc.mime_type in IMAGE_MIME_TYPES
    is_pdf = doc.mime_type == "application/pdf"

    if not is_pdf and not is_image:
        await update.message.reply_text("Please send a PDF or image file.")
        return

    user_id = update.effective_user.id
    if is_authorized(user_id):
        await update.message.reply_text("Printing...")
        try:
            file = await doc.get_file()
            data = bytes(await file.download_as_bytearray())
            if is_image:
                print_image(data)
            else:
                print_pdf(data)
            await update.message.reply_text("Sent to printer.")
        except Exception:
            logger.exception("Print failed")
            await update.message.reply_text("Printing failed. Is the printer on?")
            user = update.effective_user
            await notify_admin(
                context,
                f"Print failed (document)\nUser: {user.id} (@{user.username})\nFile: {doc.file_name}\n\n{traceback.format_exc()}",
            )
    else:
        context.user_data["pending_doc"] = doc
        context.user_data["pending_type"] = "image" if is_image else "pdf"
        context.user_data["awaiting_auth"] = True
        await update.message.reply_text("Please send the password to print this file.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    photo = update.message.photo[-1]  # highest resolution

    user_id = update.effective_user.id
    if is_authorized(user_id):
        await update.message.reply_text("Printing...")
        try:
            file = await photo.get_file()
            data = bytes(await file.download_as_bytearray())
            print_image(data)
            await update.message.reply_text("Sent to printer.")
        except Exception:
            logger.exception("Print failed")
            await update.message.reply_text("Printing failed. Is the printer on?")
            user = update.effective_user
            await notify_admin(
                context,
                f"Print failed (photo)\nUser: {user.id} (@{user.username})\n\n{traceback.format_exc()}",
            )
    else:
        context.user_data["pending_doc"] = photo
        context.user_data["pending_type"] = "image"
        context.user_data["awaiting_auth"] = True
        await update.message.reply_text("Please send the password to print this photo.")


def main() -> None:
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("admin", contact_admin))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("checkbell", checkbell))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    logger.info("Bot starting")
    app.run_polling()


if __name__ == "__main__":
    main()
