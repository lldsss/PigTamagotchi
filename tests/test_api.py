import hashlib
import hmac
import json
import tempfile
import time
import unittest
from pathlib import Path
from urllib.parse import urlencode

from aiohttp.test_utils import TestClient, TestServer

from pig_tamagotchi.__main__ import create_app, create_dispatcher
from pig_tamagotchi.auth import telegram_user
from pig_tamagotchi.storage import Store

TOKEN = "123456:example-test-token"


def init_data(user_id=42, age=0):
    fields = {
        "auth_date": str(int(time.time()) - age),
        "user": json.dumps({"id": user_id, "first_name": "Test"}),
        "query_id": "test-query",
    }
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


class AuthTests(unittest.TestCase):
    def test_signature_and_expiration(self):
        self.assertEqual(telegram_user(init_data(), TOKEN), "tg:42")
        for value in ["", init_data(age=90000), init_data(age=-300),
                      init_data().replace("Test", "Fake")]:
            with self.assertRaises(ValueError):
                telegram_user(value, TOKEN)

    def test_bot_handlers_register(self):
        dispatcher = create_dispatcher("https://example.com")
        self.assertEqual(len(dispatcher.sub_routers), 1)


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = Store(str(Path(self.folder.name) / "pets.db"))
        self.client = TestClient(TestServer(create_app(self.store, TOKEN)))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        self.folder.cleanup()

    async def test_http_health_is_public(self):
        response = await self.client.get("/health")
        self.assertEqual(response.status, 200)
        self.assertEqual(await response.json(), {"status": "ok"})

    async def test_production_rejects_unsigned_requests(self):
        response = await self.client.get("/api/pet")
        self.assertEqual(response.status, 401)

    async def test_authorized_action_and_cooldown(self):
        headers = {"X-Telegram-Init-Data": init_data()}
        response = await self.client.post("/api/action", headers=headers, json={"action": "feed"})
        self.assertEqual(response.status, 200)
        self.assertEqual((await response.json())["pet"]["coins"], 28)
        response = await self.client.post("/api/action", headers=headers, json={"action": "feed"})
        self.assertEqual(response.status, 409)
        response = await self.client.post("/api/action", headers=headers, json={"action": "invent"})
        self.assertEqual(response.status, 400)
        response = await self.client.post("/api/action", headers=headers, json=[])
        self.assertEqual(response.status, 400)

    async def test_demo_cookie_and_static_files(self):
        async with TestClient(TestServer(create_app(self.store, demo=True))) as client:
            response = await client.get("/api/pet")
            self.assertTrue((await response.json())["demo"])
            self.assertIn("pig_demo", response.cookies)
            await client.post("/api/action", json={"action": "play"})
            response = await client.get("/api/pet")
            self.assertEqual((await response.json())["pet"]["coins"], 30)
            for path in ["/", "/style.css", "/app.js", "/pig.svg", "/pig-3d.js"]:
                response = await client.get(path)
                self.assertEqual(response.status, 200)
            self.assertEqual((await client.get("/.env")).status, 404)
