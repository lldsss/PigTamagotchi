"""Один процесс: HTTP-приложение и aiogram long polling."""

import asyncio
import logging
import os
import uuid
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)
from aiohttp import web
from dotenv import load_dotenv

from .auth import telegram_user
from .game import GameError, MESSAGES
from .storage import Store

WEB = Path(__file__).resolve().parents[2] / "web"


def create_app(store: Store, token: str = "", demo: bool = False) -> web.Application:
    @web.middleware
    async def errors(request, handler):
        try:
            response = await handler(request)
        except web.HTTPException as exc:
            response = web.json_response({"error": exc.reason}, status=exc.status)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app = web.Application(middlewares=[errors], client_max_size=16384)

    async def api(request):
        cookie = None
        if demo:
            # Демо изолировано от настоящих пользователей Telegram.
            raw = request.cookies.get("pig_demo", "")
            try:
                cookie = str(uuid.UUID(raw))
            except ValueError:
                cookie = str(uuid.uuid4())
            user_id = f"demo:{cookie}"
        else:
            try:
                user_id = telegram_user(request.headers.get("X-Telegram-Init-Data", ""), token)
            except ValueError as exc:
                return web.json_response({"error": str(exc)}, status=401)
        action = None
        if request.method == "POST":
            try:
                body = await request.json()
            except (ValueError, UnicodeDecodeError):
                raise web.HTTPBadRequest(reason="Некорректный запрос.") from None
            action = body.get("action") if isinstance(body, dict) else None
            if not isinstance(action, str) or action not in MESSAGES:
                raise web.HTTPBadRequest(reason="Неизвестное действие.")
        try:
            state = await asyncio.to_thread(store.access, user_id, action)
        except GameError as exc:
            return web.json_response({"error": str(exc)}, status=409)
        response = web.json_response(
            {"pet": state, "demo": demo, "message": MESSAGES.get(action, "")}
        )
        if cookie:
            response.set_cookie(
                "pig_demo", cookie, httponly=True, samesite="Lax", max_age=31536000,
                secure=request.secure or request.headers.get("X-Forwarded-Proto") == "https",
            )
        return response

    async def health(request):
        return web.json_response({"status": "ok"})

    async def index(request):
        return web.FileResponse(WEB / "index.html")

    async def asset(request):
        name = request.match_info["name"]
        if name not in {"app.js", "style.css", "pig.svg"}:
            raise web.HTTPNotFound()
        return web.FileResponse(WEB / name)

    app.router.add_get("/health", health)
    app.router.add_get("/", index)
    app.router.add_get("/api/pet", api)
    app.router.add_post("/api/action", api)
    app.router.add_get("/{name}", asset)
    return app


def create_dispatcher(url: str) -> Dispatcher:
    router = Router()

    @router.message(CommandStart())
    @router.message(Command("play"))
    async def start(message: Message):
        if message.chat.type != "private":
            await message.answer("Приходи в личные сообщения — Пуня ждёт тебя 🐷")
            return
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="К моей свинке 🐷", web_app=WebAppInfo(url=url))
        ]])
        await message.answer(
            "Это Пуня 🐷\nМаленькая свинка, которой нужны твои забота и обнимашки.",
            reply_markup=keyboard,
        )

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher


async def main():
    load_dotenv()
    demo = os.getenv("DEMO_MODE", "false").lower() == "true"
    token = os.getenv("BOT_TOKEN", "")
    url = os.getenv("WEBAPP_URL", "")
    if not demo and (not token or urlparse(url).scheme != "https" or not urlparse(url).netloc):
        raise SystemExit("Укажи BOT_TOKEN и публичный HTTPS WEBAPP_URL в .env либо DEMO_MODE=true.")
    store = Store(os.getenv("DATABASE_PATH", "data/pigs.sqlite3"))
    runner = web.AppRunner(create_app(store, token, demo))
    await runner.setup()
    bot = None
    try:
        host, port = os.getenv("HOST", "127.0.0.1"), int(os.getenv("PORT", "8080"))
        await web.TCPSite(runner, host, port).start()
        logging.info("Приложение запущено: http://%s:%s (деморежим: %s)", host, port, demo)
        if demo:
            await asyncio.Event().wait()
        else:
            bot = Bot(token)
            await bot.set_my_commands([
                BotCommand(command="start", description="Познакомиться с Пуней"),
                BotCommand(command="play", description="Открыть домик"),
            ])
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="Моя свинка", web_app=WebAppInfo(url=url))
            )
            await create_dispatcher(url).start_polling(bot)
    finally:
        if bot:
            await bot.session.close()
        await runner.cleanup()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
