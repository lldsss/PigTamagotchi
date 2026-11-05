"""Правила игры. Время и награды определяет только сервер."""

from dataclasses import asdict, dataclass, field

LEVELS = [(0, "Крошка"), (50, "Непоседа"), (140, "Дружочек"), (300, "Звёздочка"), (550, "Легенда")]
COOLDOWNS = {"feed": 60, "walk": 300, "play": 120, "wash": 180, "upgrade": 21600}
UPGRADE_COSTS = [30, 60, 100]
MESSAGES = {
    "feed": "Хрум-хрум! Очень вкусно ♡",
    "walk": "Маленькое приключение удалось!",
    "play": "С тобой так весело!",
    "wash": "Чистая свинка — счастливая свинка!",
    "upgrade": "Дома стало ещё уютнее ♡",
}


class GameError(ValueError):
    """Действие пока недоступно."""


@dataclass
class Pet:
    satiety: float = 75
    joy: float = 80
    energy: float = 85
    cleanliness: float = 90
    xp: int = 0
    coins: int = 20
    room: int = 0
    updated_at: float = 0
    ready_at: dict[str, float] = field(default_factory=dict)

    def refresh(self, now: float) -> None:
        hours = max(0, now - self.updated_at) / 3600
        self.satiety = max(0, self.satiety - hours * 4)
        self.joy = max(0, self.joy - hours * 3)
        self.cleanliness = max(0, self.cleanliness - hours * 2)
        self.energy = min(100, self.energy + hours * 8)
        self.updated_at = now

    def act(self, action: str, now: float) -> None:
        if action not in COOLDOWNS:
            raise GameError("Такого действия нет.")
        self.refresh(now)
        if self.ready_at.get(action, 0) > now:
            raise GameError("Пуня немного отдыхает. Подожди таймер ♡")
        if action == "upgrade":
            if self.room >= len(UPGRADE_COSTS):
                raise GameError("Домик уже самый уютный!")
            cost = UPGRADE_COSTS[self.room]
            if self.coins < cost:
                raise GameError(f"Для улучшения нужно {cost} монет.")
            self.coins -= cost
            self.room += 1
            self.xp += 25
        else:
            if action in {"walk", "play"} and self.energy < 12:
                raise GameError("Пуня устала. Энергия восстанавливается сама ♡")
            if action == "feed":
                self.satiety = min(100, self.satiety + 25)
            elif action == "walk":
                self.joy = min(100, self.joy + 22)
                self.energy -= 12
                self.satiety = max(0, self.satiety - 8)
                self.cleanliness = max(0, self.cleanliness - 8)
            elif action == "play":
                self.joy = min(100, self.joy + 18)
                self.energy -= 12
            elif action == "wash":
                self.cleanliness = min(100, self.cleanliness + 35)
                self.joy = min(100, self.joy + 5)
            self.xp += {"feed": 10, "walk": 16, "play": 12, "wash": 10}[action]
            self.coins += {"feed": 8, "walk": 12, "play": 10, "wash": 8}[action]
        self.ready_at[action] = now + COOLDOWNS[action]

    def snapshot(self, now: float) -> dict:
        self.refresh(now)
        level = max(i for i, (threshold, _) in enumerate(LEVELS) if self.xp >= threshold)
        next_xp = LEVELS[level + 1][0] if level + 1 < len(LEVELS) else None
        return {
            **asdict(self),
            "level": level + 1,
            "level_name": LEVELS[level][1],
            "level_start": LEVELS[level][0],
            "next_xp": next_xp,
            "upgrade_cost": UPGRADE_COSTS[self.room] if self.room < 3 else None,
            "server_time": now,
        }
