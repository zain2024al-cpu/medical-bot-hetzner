# modules/general_services/routing_nav.py
# Handles top-level gs: navigation callbacks (main menu + sub-module routing).

import logging

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler

logger = logging.getLogger(__name__)


async def _dispatch_gs_nav(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if not data.startswith("gs:"):
        return
    action = data[len("gs:"):]

    if action == "main":
        from modules.general_services.views import build_gs_menu
        text, kb = build_gs_menu()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if action == "arrivals":
        from modules.general_services.arrivals.views import build_arrivals_menu
        text, kb = build_arrivals_menu()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if action == "departures":
        from modules.general_services.departures.views import build_departures_menu
        text, kb = build_departures_menu()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if action == "public_services":
        from modules.general_services.public_services.views import build_public_services_menu
        text, kb = build_public_services_menu()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return


def register_nav_handler(app) -> None:
    app.add_handler(
        CallbackQueryHandler(_dispatch_gs_nav, pattern=r"^gs:"),
        group=15,
    )
