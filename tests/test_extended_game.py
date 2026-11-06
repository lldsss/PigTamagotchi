import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from pig_tamagotchi.game import NEGLECT_LIMIT, GameError, Pet
from pig_tamagotchi.storage import Store


class ExtendedGameTests(unittest.TestCase):
    def test_shop_and_shared_feeding_timer(self):
        pet = Pet(updated_at=1000, coins=100, satiety=10)
        pet.act("buy_apple", 1000)
        self.assertEqual((pet.coins, pet.inventory["apple"]), (84, 1))
        pet.act("eat_apple", 1000)
        self.assertEqual((pet.satiety, pet.inventory["apple"]), (50, 0))
        with self.assertRaises(GameError):
            pet.act("feed", 2199)
        pet.act("feed", 2200)
        with self.assertRaises(GameError):
            pet.act("eat_apple", 3400)

    def test_insufficient_money_and_inventory_limit(self):
        pet = Pet(updated_at=1000, coins=0)
        with self.assertRaises(GameError):
            pet.act("buy_carrot", 1000)
        self.assertEqual(pet.inventory, {})
        pet.coins = 100
        pet.inventory["carrot"] = 99
        with self.assertRaises(GameError):
            pet.act("buy_carrot", 1000)
        self.assertEqual(pet.coins, 100)

    def test_walk_reward_only_on_completion_and_once(self):
        pet = Pet(updated_at=1000)
        pet.act("walk", 1000)
        self.assertEqual(pet.coins, 20)
        pet.refresh(2199)
        self.assertEqual(pet.coins, 20)
        with self.assertRaises(GameError):
            pet.act("play", 2199)
        pet.refresh(2200)
        self.assertEqual((pet.coins, pet.xp, pet.activity), (40, 16, None))
        pet.refresh(2200)
        self.assertEqual(pet.coins, 40)
        with self.assertRaises(GameError):
            pet.act("walk", 4599)
        pet.act("walk", 4600)

    def test_sleep_and_offline_refresh_match_regular_refresh(self):
        pet = Pet(updated_at=1000, energy=0)
        pet.act("sleep", 1000)
        self.assertEqual(pet.mood(1000)[0], "sleeping")
        pet.refresh(8199)
        self.assertLess(pet.energy, 20)
        pet.refresh(8200)
        self.assertAlmostEqual(pet.energy, 76)
        a = Pet(updated_at=1000)
        a.act("walk", 1000)
        b = Pet(**asdict(a))
        a.refresh(1000 + 86400)
        b.refresh(2200)
        b.refresh(1000 + 86400)
        self.assertEqual(asdict(a), asdict(b))

    def test_daily_reward_boundary(self):
        pet = Pet(updated_at=1000)
        pet.act("daily", 1000)
        self.assertEqual(pet.coins, 60)
        with self.assertRaises(GameError):
            pet.act("daily", 87399)
        pet.act("daily", 87400)
        self.assertEqual(pet.coins, 100)

    def test_sickness_threshold_and_recovery(self):
        pet = Pet(updated_at=1000, satiety=15, cleanliness=90, coins=50)
        pet.refresh(1000 + NEGLECT_LIMIT - 1)
        self.assertFalse(pet.sick)
        now = 1000 + NEGLECT_LIMIT
        pet.refresh(now)
        self.assertTrue(pet.sick)
        self.assertEqual(pet.mood(now)[0], "sick")
        for action in ["walk", "play", "heal"]:
            with self.assertRaises(GameError):
                pet.act(action, now)
        pet.act("feed", now)
        pet.act("wash", now)
        with self.assertRaises(GameError):
            pet.act("heal", now)
        pet.act("feed", now + 1200)
        pet.act("heal", now + 1200)
        self.assertFalse(pet.sick)
        self.assertGreaterEqual(pet.coins, 0)

    def test_neglect_counts_only_time_below_threshold(self):
        pet = Pet(updated_at=1000, satiety=75)
        pet.refresh(1000 + 26 * 3600)
        self.assertFalse(pet.sick)
        pet.refresh(1000 + 27 * 3600)
        self.assertTrue(pet.sick)

    def test_care_breaks_neglect_before_illness(self):
        pet = Pet(updated_at=1000, satiety=10)
        pet.refresh(1000 + 11 * 3600)
        pet.act("feed", 1000 + 11 * 3600)
        pet.act("feed", 2200 + 11 * 3600)
        pet.refresh(2200 + 12 * 3600)
        self.assertFalse(pet.sick)
        self.assertEqual(pet.neglected_for, 0)

    def test_emotions_and_achievement_reward_once(self):
        pet = Pet(updated_at=1000, joy=50)
        pet.act("pet", 1000)
        self.assertEqual((pet.joy, pet.coins, pet.mood(1000)[0]), (58, 30, "loved"))
        pet.act("pet", 1300)
        self.assertEqual(pet.coins, 30)
        self.assertEqual(pet.achievements, ["friend"])

    def test_old_save_defaults_and_new_state_persistence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "pets.db")
            store = Store(path)
            old = {"coins": 80, "updated_at": 1000}
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("INSERT INTO pets VALUES (?, ?)", ("old", json.dumps(old)))
            with patch("pig_tamagotchi.storage.time.time", return_value=1000):
                state = store.access("old")
                self.assertEqual(state["inventory"], {})
                self.assertEqual(state["owned_clothes"], ["bow"])
                self.assertEqual(state["outfit"], {"bow": "bow"})
                store.access("old", "buy_apple")
                store.access("old", "buy_clothing_hat")
                store.access("old", "walk")
            with patch("pig_tamagotchi.storage.time.time", return_value=2200):
                state = Store(path).access("old")
                self.assertEqual(state["inventory"], {"apple": 1})
                self.assertEqual(state["coins"], 49)
                self.assertEqual(state["owned_clothes"], ["bow", "hat"])
                self.assertEqual(state["outfit"], {"bow": "bow", "hat": "hat"})
                self.assertIsNone(state["activity"])
                self.assertEqual(store.access("new")["coins"], 20)

    def test_dressing_replaces_only_matching_slot_and_keeps_wardrobe(self):
        pet = Pet(updated_at=1000, coins=200)
        pet.act("sleep", 1000)
        for action in ["buy_clothing_sweater", "buy_clothing_overalls", "remove_sweater"]:
            pet.act(action, 1000)
        self.assertEqual(pet.outfit, {"bow": "bow", "body": "overalls"})
        pet.act("wear_sweater", 1000)
        pet.act("remove_bow", 1000)
        self.assertEqual(pet.outfit, {"body": "sweater"})
        self.assertEqual(pet.owned_clothes, ["bow", "sweater", "overalls"])
        self.assertEqual(pet.coins, 95)
        self.assertEqual(pet.activity, "sleep")

    def test_concurrent_clothing_purchase_charges_once(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(str(Path(folder) / "pets.db"))
            store.access("player", "daily")
            with ThreadPoolExecutor(max_workers=4) as pool:
                states = list(
                    pool.map(lambda _: store.access("player", "buy_clothing_hat"), range(4))
                )
            for state in states:
                self.assertEqual(state["coins"], 25)
                self.assertEqual(state["owned_clothes"], ["bow", "hat"])
            store.access("player", "remove_hat")
            retry = store.access("player", "buy_clothing_hat")
            self.assertEqual(retry["coins"], 25)
            self.assertEqual(retry["outfit"], {"bow": "bow"})

    def test_concurrent_purchases_cannot_overdraw(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(str(Path(folder) / "pets.db"))

            def buy(_):
                try:
                    store.access("alice", "buy_apple")
                    return True
                except GameError:
                    return False

            with ThreadPoolExecutor(max_workers=4) as pool:
                self.assertEqual(sum(pool.map(buy, range(4))), 1)
            state = store.access("alice")
            self.assertEqual((state["coins"], state["inventory"]), (4, {"apple": 1}))
