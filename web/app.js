/* Прогресс и таймеры приходят с сервера. В браузере — только отображение. */
const tg = window.Telegram?.WebApp;
const $ = (id) => document.getElementById(id);
let buttons = [...document.querySelectorAll('[data-action]')];
const labels = {feed: 'Угостить →', walk: 'На прогулку →', play: 'Повеселиться →', wash: 'Плюх-плюх →', pet: 'Обнимашки →', sleep: 'Баю-бай →', daily: 'Забрать →', heal: 'Лекарство →'};
let pet = null;
let clockOffset = 0;
let pending = false;
let noticeTimer;
let speechTimer;
let refreshPending = false;

tg?.ready();
tg?.expand();
tg?.setHeaderColor?.('#fff7f8');
tg?.setBackgroundColor?.('#fff7f8');
document.body.classList.add('loading');

function notify(text) {
  $('notice').textContent = text;
  $('notice').hidden = false;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => { $('notice').hidden = true; }, 3500);
}

function react(text) {
  $('speech').textContent = text;
  clearTimeout(speechTimer);
  speechTimer = setTimeout(() => { $('speech').textContent = pet?.mood_text || 'Мне хорошо с тобой ♡'; speechTimer = null; }, 5500);
  $('pig').classList.remove('bounce');
  requestAnimationFrame(() => requestAnimationFrame(() => $('pig').classList.add('bounce')));
  for (let i = 0; i < 5; i++) {
    const heart = document.createElement('span');
    heart.className = 'floating-heart';
    heart.textContent = i % 2 ? '♡' : '✦';
    heart.style.left = `${35 + Math.random() * 30}%`;
    heart.style.top = `${100 + Math.random() * 70}px`;
    heart.style.animationDelay = `${i * 0.09}s`;
    $('scene').append(heart);
    setTimeout(() => heart.remove(), 1800);
  }
  tg?.HapticFeedback?.impactOccurred('light');
}

function timeLeft(seconds) {
  const total = Math.max(0, Math.ceil(seconds));
  if (total >= 3600) return `${Math.floor(total / 3600)}ч ${Math.ceil((total % 3600) / 60)}м`;
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

function buttonStatus(action, remaining) {
  if (!pet) return 'Загружаем…';
  if (pending || refreshPending) return 'Подожди…';
  if (remaining > 0) return `◷ ${timeLeft(remaining)}`;
  if (pet.activity && action !== 'daily' && !action.startsWith('buy_')) return 'После отдыха';
  if (['walk', 'play'].includes(action)) {
    if (pet.sick) return 'Сначала лечение';
    if (pet.energy < 12) return 'Нужен отдых';
  }
  if (action === 'heal') {
    if (!pet.sick) return 'Здорова ♡';
    if (pet.satiety < 30 || pet.cleanliness < 30) return 'Нужен уход';
    if (pet.coins < 30) return 'Нужно 30 ✦';
  }
  if (action.startsWith('buy_')) {
    if (pet.coins < pet.foods[action.slice(4)].price) return 'Не хватает ✦';
    if ((pet.inventory[action.slice(4)] || 0) >= 99) return 'Кладовая полна';
    return 'Купить →';
  }
  if (action.startsWith('eat_')) return pet.inventory[action.slice(4)] > 0 ? 'Угостить →' : 'Нет в кладовой';
  return labels[action];
}

function updateButtons() {
  const now = Date.now() / 1000 + clockOffset;
  for (const button of buttons) {
    const action = button.dataset.action;
    const timer = action.startsWith('eat_') ? 'feed' : action;
    const remaining = pet ? Math.max(0, (pet.ready_at[timer] || 0) - now) : 0;
    let disabled = !pet || pending || refreshPending || remaining > 0;
    disabled ||= Boolean(pet?.activity) && action !== 'daily' && !action.startsWith('buy_');
    if (action === 'upgrade') {
      disabled ||= pet?.upgrade_cost == null || pet.coins < pet.upgrade_cost;
      $('upgrade-price').textContent = pet?.upgrade_cost == null && pet
        ? '♡ MAX' : remaining > 0 ? timeLeft(remaining) : `✦ ${pet?.upgrade_cost ?? 30}`;
    } else {
      if (pet) {
        disabled ||= ['walk', 'play'].includes(action) && (pet.energy < 12 || pet.sick);
        disabled ||= action === 'heal' && (!pet.sick || pet.coins < 30 || pet.satiety < 30 || pet.cleanliness < 30);
        if (action.startsWith('buy_')) {
          const id = action.slice(4);
          disabled ||= pet.coins < pet.foods[id].price || (pet.inventory[id] || 0) >= 99;
        }
        if (action.startsWith('eat_')) disabled ||= !(pet.inventory[action.slice(4)] > 0);
      }
      button.querySelector('.action-status').textContent = buttonStatus(action, remaining);
    }
    button.disabled = disabled;
  }
  $('pig').disabled = !pet || pending || refreshPending || Boolean(pet.activity) || (pet.ready_at.pet || 0) > now;
  if (pet?.activity) {
    const activity = pet.activity === 'walk' ? '🌿 Прогулка' : '🌙 Сон';
    const remaining = pet.activity_until - now;
    $('activity-status').textContent = remaining > 0
      ? `${activity} · ещё ${timeLeft(remaining)}` : 'Проверяем возвращение…';
  }
}

function render(data) {
  pet = data.pet;
  clockOffset = pet.server_time - Date.now() / 1000;
  $('coins').textContent = pet.coins;
  $('level').textContent = `Уровень ${pet.level}`;
  $('level-name').textContent = pet.level_name;
  $('xp').textContent = pet.next_xp ? `${pet.xp} / ${pet.next_xp} XP` : `${pet.xp} XP · максимум`;
  const progress = pet.next_xp ? 100 * (pet.xp - pet.level_start) / (pet.next_xp - pet.level_start) : 100;
  $('xp-bar').style.width = `${progress}%`;
  for (const stat of ['satiety', 'joy', 'energy', 'cleanliness']) {
    $(stat + '-value').textContent = `${Math.round(pet[stat])}%`;
    $(stat + '-bar').style.width = `${pet[stat]}%`;
  }
  $('mood').textContent = pet.mood_text;
  if (!speechTimer) $('speech').textContent = pet.mood_text;
  $('scene').className = `scene room-${pet.room} mood-${pet.mood}`;
  $('emotion-icon').textContent = {sleeping: 'Zzz', walking: '🌿', sick: '🌡️', hungry: '🥕', tired: '💤', dirty: '🫧', sad: '💧', loved: '💕', excited: '✨', yummy: '😋', fresh: '🫧', happy: '♡'}[pet.mood];
  $('activity-status').hidden = !pet.activity;
  renderShop();
  $('achievements').replaceChildren(...Object.entries(pet.achievement_catalog).map(([id, item]) => {
    const row = document.createElement('p');
    row.className = pet.achievements.includes(id) ? 'earned' : '';
    row.textContent = `${pet.achievements.includes(id) ? '🏅' : '○'} ${item.name} · ${item.progress}/${item.target} · +${item.reward} ✦`;
    return row;
  }));
  $('room-name').textContent = ['Уютный уголок', 'Мягкие облачка', 'Цветочное настроение', 'Домик мечты'][pet.room];
  $('upgrade-title').textContent = pet.room === 3 ? 'Домик мечты' : 'Ещё уютнее';
  $('upgrade-description').textContent = [
    'Мягкая подушка · улучшение 1/3', 'Милые цветы · улучшение 2/3',
    'Гирлянда любви · улучшение 3/3', 'Все улучшения открыты ♡',
  ][pet.room];
  $('demo-badge').hidden = !data.demo;
  $('connection').hidden = true;
  document.body.classList.remove('loading');
  updateButtons();
}

async function request(path, action) {
  const response = await fetch(path, {
    method: action ? 'POST' : 'GET',
    headers: {'Content-Type': 'application/json', 'X-Telegram-Init-Data': tg?.initData || ''},
    body: action ? JSON.stringify({action}) : undefined,
    signal: AbortSignal.timeout(12000),
    credentials: 'same-origin',
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Не удалось выполнить действие.');
  return data;
}

async function load() {
  if (refreshPending || pending) return;
  refreshPending = true;
  updateButtons();
  try {
    render(await request('/api/pet'));
  } catch (error) {
    $('connection-text').textContent = error.message === 'Failed to fetch'
      ? 'Нет связи. Пуня подождёт ♡' : error.message;
    $('connection').hidden = false;
  } finally {
    refreshPending = false;
    updateButtons();
  }
}

function renderShop() {
  if (!$('food-list').children.length) {
    for (const [id, food] of Object.entries(pet.foods)) {
      const row = document.createElement('article');
      row.className = 'food-card';
      const title = document.createElement('h3');
      title.textContent = `${food.icon} ${food.name}`;
      const detail = document.createElement('p');
      detail.textContent = `+${food.satiety} сытости · +${food.joy} счастья`;
      const stock = document.createElement('p');
      stock.id = `stock-${id}`;
      row.append(title, detail, stock);
      for (const kind of ['buy', 'eat']) {
        const button = document.createElement('button');
        button.dataset.action = `${kind}_${id}`;
        const caption = document.createElement('span');
        caption.textContent = kind === 'buy' ? `Купить · ${food.price} ✦` : 'Угостить';
        const status = document.createElement('span');
        status.className = 'action-status';
        button.append(caption, status);
        row.append(button);
      }
      $('food-list').append(row);
    }
    buttons = [...document.querySelectorAll('[data-action]')];
  }
  for (const id of Object.keys(pet.foods)) $('stock-' + id).textContent = `В кладовой: ${pet.inventory[id] || 0}`;
}

async function perform(action) {
  if (pending || refreshPending || !pet) return;
  pending = true;
  updateButtons();
  try {
    const oldLevel = pet.level;
    const oldAchievements = pet.achievements.length;
    const data = await request('/api/action', action);
    render(data);
    react(data.message);
    if (data.pet.level > oldLevel) notify(`Новый уровень! ${data.pet.level_name} ✦`);
    else if (data.pet.achievements.length > oldAchievements) notify('Новое достижение! Пятачки уже в кошельке 🏅');
  } catch (error) {
    notify(error.message);
    pending = false;
    await load();
  } finally {
    pending = false;
    updateButtons();
  }
}
document.addEventListener('click', (event) => {
  const button = event.target.closest('[data-action]');
  if (button && !button.disabled) perform(button.dataset.action);
});
$('pig').addEventListener('click', () => perform('pet'));
$('retry').addEventListener('click', load);
$('help').addEventListener('click', () => $('help-dialog').showModal());
for (const id of ['close-help', 'help-ok']) $(id).addEventListener('click', () => $('help-dialog').close());
document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
setInterval(() => {
  updateButtons();
  if (pet?.activity && pet.activity_until <= Date.now() / 1000 + clockOffset) load();
}, 1000);
setInterval(() => { if (!document.hidden) load(); }, 30000);
updateButtons();
load();
