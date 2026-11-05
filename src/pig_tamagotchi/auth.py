"""Проверка подписи и срока действия Telegram initData."""

import time

from aiogram.utils.web_app import safe_parse_webapp_init_data


def telegram_user(init_data: str, token: str) -> str:
    try:
        data = safe_parse_webapp_init_data(token=token, init_data=init_data)
        age = time.time() - data.auth_date.timestamp()
        if data.user is None or not -30 <= age <= 86400:
            raise ValueError("Expired or missing user")
        return f"tg:{data.user.id}"
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("Открой приложение заново через бота.") from exc
