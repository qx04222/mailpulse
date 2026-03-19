"""
Telegram Bot server — polling mode.
Supports:
- Private chat natural language Q&A
- Group chat @mention queries
- /report <company> — on-demand report generation
- /status <company> — view pending action items
- /help — usage help
"""
import asyncio
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from ..config import settings, load_companies
from .query import process_query, find_company

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# -- Command handlers -------------------------------------------------

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """*Email Digest Bot*

*Commands:*
/report <company> — generate a full report
/status <company> — view pending action items
/help — show this help

*Natural language:*
Send a message directly, e.g.:
- "Arcview this week new clients?"
- "Summarize TorqueMax situation"

In group chats, @mention the bot."""
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from ..storage.action_items import get_pending_items

    company_name = " ".join(context.args) if context.args else None
    if not company_name:
        # Show all companies
        companies = load_companies()
        lines = ["*Pending Action Items*\n"]
        for c in companies:
            items = get_pending_items(c["id"])
            if items:
                overdue = [i for i in items if i["status"] == "overdue"]
                pending = [i for i in items if i["status"] in ("pending", "in_progress")]
                lines.append(f"*{c['name']}*: {len(pending)} pending, {len(overdue)} overdue")
        if len(lines) == 1:
            lines.append("(no pending items)")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    company = find_company(company_name)
    if not company:
        await update.message.reply_text(f"Company not found: {company_name}")
        return

    items = get_pending_items(company["id"])
    if not items:
        await update.message.reply_text(f"{company['name']} has no pending items")
        return

    lines = [f"*{company['name']} Pending Items*\n"]
    for item in items:
        emoji = "!" if item["status"] == "overdue" else "-"
        lines.append(f"{emoji} {item['title']}\n   seen {item.get('seen_count', 1)} times")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    company_name = " ".join(context.args) if context.args else None
    if not company_name:
        await update.message.reply_text("Usage: /report <company>\nExample: /report Arcview")
        return

    company = find_company(company_name)
    if not company:
        await update.message.reply_text(f"Company not found: {company_name}")
        return

    await update.message.reply_text(f"Generating {company['name']} report, please wait...")

    try:
        from ..main import run_company_report_only
        docx_bytes, report_url = await run_company_report_only(company)

        if docx_bytes:
            from io import BytesIO
            doc_file = BytesIO(docx_bytes)
            doc_file.name = f"{company['name']}_report.docx"
            await update.message.reply_document(
                document=doc_file,
                caption=f"{company['name']} email report generated",
            )
        else:
            await update.message.reply_text("Report generation failed, please try again later.")
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        await update.message.reply_text(f"Report error: {str(e)[:100]}")


# -- Natural language message handler ---------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle natural language messages."""
    text = update.message.text
    if not text:
        return

    # In group chats, only respond when @mentioned
    if update.message.chat.type in ("group", "supergroup"):
        bot_username = context.bot.username
        if f"@{bot_username}" not in text:
            return
        text = text.replace(f"@{bot_username}", "").strip()

    if not text:
        return

    await update.message.chat.send_action("typing")

    chat_id = update.message.chat_id
    if "history" not in context.chat_data:
        context.chat_data["history"] = []

    try:
        answer = await process_query(
            question=text,
            chat_context=context.chat_data["history"],
        )

        context.chat_data["history"].append({"role": "user", "content": text})
        context.chat_data["history"].append({"role": "assistant", "content": answer})
        context.chat_data["history"] = context.chat_data["history"][-6:]

        chunks = [answer[i:i+4096] for i in range(0, len(answer), 4096)]
        for chunk in chunks:
            await update.message.reply_text(chunk)

    except Exception as e:
        logger.error(f"Query error: {e}")
        await update.message.reply_text(f"Error processing query: {str(e)[:100]}")


# -- Entry point ------------------------------------------------------

def create_bot_app() -> Application:
    """Create and configure the bot application."""
    app = Application.builder().token(settings.telegram_bot_token).build()

    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app


async def run_bot():
    """Run bot in polling mode."""
    app = create_bot_app()
    logger.info("Bot starting in polling mode...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("Bot is running. Press Ctrl+C to stop.")

    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
