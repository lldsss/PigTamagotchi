"""Проверки обработчиков без открытия TCP-порта."""

import json
import tempfile
import unittest
from pathlib import Path

from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from pig_tamagotchi.__main__ import create_app
from pig_tamagotchi.storage import Store
from test_api import TOKEN, init_data


class ApiHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = Store(str(Path(self.folder.name) / "pets.db"))
        self.app = create_app(self.store, TOKEN)

    async def asyncTearDown(self):
        self.folder.cleanup()

    async def request(self, path, body=None, user=42, signed=True):
        headers = {"X-Telegram-Init-Data": init_data(user)} if signed else {}
        request = make_mocked_request("POST" if body is not None else "GET", path, headers)
        if body is not None:
            request._read_bytes = json.dumps(body).encode()
        match = await self.app.router.resolve(request)
        request._match_info = match
        try:
            response = await match.handler(request)
        except web.HTTPException as exc:
            return exc.status, {}
        return response.status, json.loads(response.body)

    async def test_authentication_and_unknown_actions(self):
        self.assertEqual((await self.request("/api/pet", signed=False))[0], 401)
        for action in ["buy_fake", "eat_fake", "invent"]:
            self.assertEqual((await self.request("/api/action", {"action": action}))[0], 400)
        self.assertEqual((await self.request("/api/action", []))[0], 400)

    async def test_shop_price_is_server_controlled_and_players_isolated(self):
        status, data = await self.request(
            "/api/action", {"action": "buy_apple", "price": 0, "coins": 999999}
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["pet"]["coins"], 4)
        self.assertEqual(data["pet"]["inventory"], {"apple": 1})
        self.assertEqual((await self.request("/api/action", {"action": "buy_apple"}))[0], 409)
        self.assertEqual((await self.request("/api/pet", user=43))[1]["pet"]["coins"], 20)

    async def test_daily_and_feeding_cooldowns(self):
        _, data = await self.request("/api/action", {"action": "daily"})
        self.assertEqual(data["pet"]["coins"], 60)
        self.assertEqual((await self.request("/api/action", {"action": "daily"}))[0], 409)
        await self.request("/api/action", {"action": "buy_berry"})
        self.assertEqual((await self.request("/api/action", {"action": "eat_berry"}))[0], 200)
        self.assertEqual((await self.request("/api/action", {"action": "feed"}))[0], 409)

    async def test_walk_busy_state_and_new_catalog(self):
        _, data = await self.request("/api/action", {"action": "walk"})
        self.assertEqual(data["pet"]["activity"], "walk")
        self.assertEqual(data["pet"]["coins"], 20)
        self.assertEqual(len(data["pet"]["foods"]), 4)
        self.assertEqual((await self.request("/api/action", {"action": "pet"}))[0], 409)
        self.assertEqual((await self.request("/api/action", {"action": "buy_carrot"}))[0], 200)
