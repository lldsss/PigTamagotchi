import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pig_tamagotchi.game import GameError, Pet
from pig_tamagotchi.storage import Store


class GameTests(unittest.TestCase):
    def test_cooldown_cannot_be_bypassed(self):
        pet = Pet(updated_at=1000)
        pet.act("feed", 1000)
        with self.assertRaises(GameError):
            pet.act("feed", 1059)
        self.assertEqual(pet.coins, 28)
        pet.act("feed", 1060)
        self.assertEqual(pet.coins, 36)

    def test_offline_decay_and_recovery_are_bounded(self):
        pet = Pet(updated_at=1000, energy=10)
        pet.refresh(4600)
        self.assertEqual(pet.satiety, 71)
        self.assertEqual(pet.energy, 18)
        pet.refresh(4600 + 86400 * 365)
        self.assertEqual(pet.satiety, 0)
        self.assertEqual(pet.energy, 100)
        self.assertEqual(pet.joy, 0)

    def test_upgrade_requires_coins_and_time_and_has_limit(self):
        pet = Pet(updated_at=1000)
        with self.assertRaises(GameError):
            pet.act("upgrade", 1000)
        pet.coins = 200
        pet.act("upgrade", 1000)
        self.assertEqual((pet.coins, pet.room), (170, 1))
        with self.assertRaises(GameError):
            pet.act("upgrade", 1001)
        pet.act("upgrade", 22600)
        pet.act("upgrade", 44200)
        with self.assertRaises(GameError):
            pet.act("upgrade", 65800)
        self.assertEqual(pet.room, 3)

    def test_levels_and_energy_requirement(self):
        pet = Pet(xp=139, energy=0, updated_at=1000)
        with self.assertRaises(GameError):
            pet.act("walk", 1000)
        pet.act("feed", 1000)
        self.assertEqual(pet.snapshot(1000)["level"], 3)
        pet.xp = 10000
        self.assertIsNone(pet.snapshot(1000)["next_xp"])

    def test_persistence_and_player_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "pets.db")
            store = Store(path)
            store.access("alice", "feed")
            self.assertEqual(Store(path).access("alice")["coins"], 28)
            self.assertEqual(store.access("bob")["coins"], 20)

    def test_concurrent_requests_award_once(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(str(Path(folder) / "pets.db"))

            def feed(_):
                try:
                    store.access("alice", "feed")
                    return True
                except GameError:
                    return False

            with ThreadPoolExecutor(max_workers=4) as pool:
                self.assertEqual(sum(pool.map(feed, range(4))), 1)
            self.assertEqual(store.access("alice")["coins"], 28)
