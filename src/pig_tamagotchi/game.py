"""Правила игры. Время и награды определяет только сервер."""

from dataclasses import asdict, dataclass, field

LEVELS = [(0, "Крошка"), (50, "Непоседа"), (140, "Дружочек"), (300, "Звёздочка"), (550, "Легенда")]
COOLDOWNS = {
    "feed": 1200,
    "walk": 3600,
    "play": 1800,
    "wash": 3600,
    "upgrade": 21600,
    "pet": 300,
    "sleep": 7200,
    "daily": 86400,
    "heal": 3600,
}
WALK_DURATION = 1200
SLEEP_DURATION = 7200
NEGLECT_LIMIT = 12 * 3600
FOODS = {
    "carrot": {"name": "Морковка", "icon": "🥕", "price": 10, "satiety": 30, "joy": 3},
    "apple": {"name": "Яблоко", "icon": "🍎", "price": 16, "satiety": 40, "joy": 8},
    "porridge": {"name": "Каша", "icon": "🥣", "price": 22, "satiety": 60, "joy": 5},
    "berry": {"name": "Ягодки", "icon": "🫐", "price": 28, "satiety": 25, "joy": 25},
}
ACHIEVEMENTS = {
    "friend": ("Первые объятия", "pet", 1, 10),
    "explorer": ("Следопыт", "walk", 3, 30),
    "chef": ("Гурман", "food", 3, 25),
    "player": ("Душа компании", "play", 5, 30),
    "clean": ("Чистюля", "wash", 3, 20),
}
UPGRADE_COSTS = [30, 60, 100]
MESSAGES = {
    "heal": "Лекарство помогло! Пуня снова здорова ♡",
    "pet": "Хрю! Спасибо за обнимашки ♡",
    "sleep": "Укрывай одеялком. Скоро вернусь бодрой!",
    "daily": "Твой ежедневный подарок: 40 пятачков ♡",
    "feed": "Хрум-хрум! Очень вкусно ♡",
    "walk": "Вперёд в парк! Вернусь через 20 минут с пятачками ♡",
    "play": "С тобой так весело!",
    "wash": "Чистая свинка — счастливая свинка!",
    "upgrade": "Дома стало ещё уютнее ♡",
}

for food_id, food in FOODS.items():
    MESSAGES[f"buy_{food_id}"] = f"{food['name']} теперь в кладовой!"
    MESSAGES[f"eat_{food_id}"] = f"М-м-м, {food['name'].lower()}! Спасибо ♡"


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

    inventory: dict[str, int] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    achievements: list[str] = field(default_factory=list)
    neglected_for: float = 0
    sick: bool = False
    activity: str | None = None
    activity_until: float = 0
    emotion: str = "happy"
    emotion_until: float = 0

    def refresh(self, now: float) -> None:
        if self.activity and now > self.activity_until:
            self.refresh(self.activity_until)
            self.refresh(now)
            return
        elapsed = max(0, now - self.updated_at)
        # Считаем только время после пересечения порога, включая отсутствие игрока.
        until_low = min(
            max(0, (self.satiety - 15) / 4 * 3600),
            max(0, (self.cleanliness - 15) / 2 * 3600),
        )
        if elapsed > until_low:
            self.neglected_for += elapsed - until_low
        elif self.satiety >= 15 and self.cleanliness >= 15:
            self.neglected_for = 0
        if self.neglected_for >= NEGLECT_LIMIT:
            self.sick = True
        hours = elapsed / 3600
        self.satiety = max(0, self.satiety - hours * 4)
        self.joy = max(0, self.joy - hours * 3)
        self.cleanliness = max(0, self.cleanliness - hours * 2)
        self.energy = min(100, self.energy + hours * 8)
        self.updated_at = max(now, self.updated_at)
        if self.activity and now >= self.activity_until:
            if self.activity == "walk":
                self.joy = min(100, self.joy + 22)
                self.coins += 20
                self.xp += 16
                self.counts["walk"] = self.counts.get("walk", 0) + 1
                self.emotion = "excited"
            else:
                self.energy = min(100, self.energy + 60)
                self.emotion = "happy"
            self.emotion_until = self.activity_until + 60
            self.activity = None
            self.check_achievements()

    def check_achievements(self) -> None:
        for key, (_, counter, target, reward) in ACHIEVEMENTS.items():
            if key not in self.achievements and self.counts.get(counter, 0) >= target:
                self.achievements.append(key)
                self.coins += reward

    def mood(self, now: float) -> tuple[str, str]:
        if self.activity == "sleep":
            return "sleeping", "Тихонько сопит… Сон восстанавливает энергию"
        if self.activity == "walk":
            return "walking", "Исследует парк. Принесёт 20 пятачков!"
        if self.sick:
            return "sick", "Заболела от недостатка заботы. Нужны еда, чистота и лекарство"
        if self.satiety < 30:
            return "hungry", "Урчит животик — пора перекусить"
        if self.energy < 20:
            return "tired", "Зевает и мечтает об одеялке"
        if self.cleanliness < 30:
            return "dirty", "Нашла лужу! Теперь пора купаться"
        if self.joy < 30:
            return "sad", "Скучает. Погладь или поиграй с ней"
        if now < self.emotion_until:
            texts = {
                "loved": "Тает от твоих объятий ♡",
                "excited": "Прыгает от восторга!",
                "yummy": "Облизывается после угощения",
                "fresh": "Блестит чистотой!",
                "happy": "Выспалась и готова к приключениям",
            }
            return self.emotion, texts.get(self.emotion, "Счастлива быть рядом")
        return "happy", "Счастлива быть рядом"

    def act(self, action: str, now: float) -> None:
        if action not in MESSAGES:
            raise GameError("Такого действия нет.")
        self.refresh(now)
        if self.activity and action != "daily" and not action.startswith("buy_"):
            raise GameError("Пуня спит или гуляет. Дождись её возвращения ♡")
        if self.ready_at.get(action, 0) > now:
            raise GameError("Пуня немного отдыхает. Подожди таймер ♡")
        if action.startswith("buy_"):
            food_id = action[4:]
            food = FOODS[food_id]
            if self.inventory.get(food_id, 0) >= 99:
                raise GameError("В кладовой уже 99 порций этого угощения.")
            if self.coins < food["price"]:
                raise GameError("Не хватает пятачков. Получи подарок или погуляй!")
            self.coins -= food["price"]
            self.inventory[food_id] = self.inventory.get(food_id, 0) + 1
            return
        if action.startswith("eat_"):
            food_id = action[4:]
            if self.ready_at.get("feed", 0) > now:
                raise GameError("Пуня ещё жуёт. Подожди таймер кормления ♡")
            if self.inventory.get(food_id, 0) < 1:
                raise GameError("Сначала купи это угощение в лавке.")
            food = FOODS[food_id]
            self.inventory[food_id] -= 1
            self.satiety = min(100, self.satiety + food["satiety"])
            self.joy = min(100, self.joy + food["joy"])
            self.xp += 10
            self.counts["food"] = self.counts.get("food", 0) + 1
            self.ready_at["feed"] = now + COOLDOWNS["feed"]
            self.emotion, self.emotion_until = "yummy", now + 60
            if self.satiety >= 15 and self.cleanliness >= 15:
                self.neglected_for = 0
            self.check_achievements()
            return
        if action == "heal":
            if not self.sick:
                raise GameError("Пуня здорова — лекарство ей не нужно ♡")
            if self.satiety < 30 or self.cleanliness < 30:
                raise GameError(
                    "Сначала покорми и искупай Пуню: нужно хотя бы 30% сытости и чистоты."
                )
            if self.coins < 30:
                raise GameError("Лекарство стоит 30 пятачков. Получи ежедневный подарок.")
            self.coins -= 30
            self.sick = False
            self.neglected_for = 0
        elif action == "daily":
            self.coins += 40
        elif action == "pet":
            self.joy = min(100, self.joy + 8)
            self.xp += 2
            self.emotion, self.emotion_until = "loved", now + 30
        elif action == "sleep":
            self.activity, self.activity_until = "sleep", now + SLEEP_DURATION
        elif action == "walk":
            if self.sick:
                raise GameError("Сначала вылечи Пуню. Сейчас ей нужен домашний уход.")
            if self.energy < 12:
                raise GameError("Для прогулки нужно 12 энергии. Уложи Пуню спать ♡")
            self.energy -= 12
            self.satiety = max(0, self.satiety - 8)
            self.cleanliness = max(0, self.cleanliness - 8)
            self.activity, self.activity_until = "walk", now + WALK_DURATION
        elif action == "upgrade":
            if self.room >= len(UPGRADE_COSTS):
                raise GameError("Домик уже самый уютный!")
            cost = UPGRADE_COSTS[self.room]
            if self.coins < cost:
                raise GameError(f"Для улучшения нужно {cost} монет.")
            self.coins -= cost
            self.room += 1
            self.xp += 25
        else:
            if action == "play" and self.sick:
                raise GameError("Пуня заболела. Игры подождут до выздоровления.")
            if action == "play" and self.energy < 12:
                raise GameError("Пуня устала. Энергия восстанавливается сама ♡")
            if action == "feed":
                self.satiety = min(100, self.satiety + 25)
            elif action == "play":
                self.joy = min(100, self.joy + 18)
                self.energy -= 12
            elif action == "wash":
                self.cleanliness = min(100, self.cleanliness + 35)
                self.joy = min(100, self.joy + 5)
            self.xp += {"feed": 10, "play": 12, "wash": 10}[action]
            self.coins += {"feed": 8, "play": 10, "wash": 8}[action]
            self.emotion = {"feed": "yummy", "play": "excited", "wash": "fresh"}.get(
                action, "happy"
            )
            self.emotion_until = now + 60
        if self.satiety >= 15 and self.cleanliness >= 15:
            self.neglected_for = 0
        if action != "walk":
            self.counts[action] = self.counts.get(action, 0) + 1
        self.check_achievements()
        self.ready_at[action] = now + COOLDOWNS[action]

    def snapshot(self, now: float) -> dict:
        self.refresh(now)
        level = max(i for i, (threshold, _) in enumerate(LEVELS) if self.xp >= threshold)
        next_xp = LEVELS[level + 1][0] if level + 1 < len(LEVELS) else None
        mood, mood_text = self.mood(now)
        return {
            **asdict(self),
            "mood": mood,
            "mood_text": mood_text,
            "foods": FOODS,
            "achievement_catalog": {
                key: {
                    "name": name,
                    "progress": min(self.counts.get(counter, 0), target),
                    "target": target,
                    "reward": reward,
                }
                for key, (name, counter, target, reward) in ACHIEVEMENTS.items()
            },
            "level": level + 1,
            "level_name": LEVELS[level][1],
            "level_start": LEVELS[level][0],
            "next_xp": next_xp,
            "upgrade_cost": UPGRADE_COSTS[self.room] if self.room < 3 else None,
            "server_time": now,
        }
