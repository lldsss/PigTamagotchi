/* Прогресс и таймеры приходят с сервера. В браузере — только отображение. */
const tg = window.Telegram?.WebApp;
const $ = (id) => document.getElementById(id);
const buttons = [...document.querySelectorAll('[data-action]')];
const labels = {feed: 'Угостить →', walk: 'На прогулку →', play: 'Повеселиться →', wash: 'Плюх-плюх →'};
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
  speechTimer = setTimeout(() => { $('speech').textContent = 'Мне хорошо с тобой ♡'; }, 5500);
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

function updateButtons() {
  const now = Date.now() / 1000 + clockOffset;
  for (const button of buttons) {
    const action = button.dataset.action;
    const remaining = pet ? Math.max(0, (pet.ready_at[action] || 0) - now) : 0;
    let disabled = !pet || pending || refreshPending || remaining > 0;
    if (action === 'upgrade') {
      disabled ||= pet?.upgrade_cost == null || pet.coins < pet.upgrade_cost;
      $('upgrade-price').textContent = pet?.upgrade_cost == null && pet
        ? '♡ MAX' : remaining > 0 ? timeLeft(remaining) : `✦ ${pet?.upgrade_cost ?? 30}`;
    } else {
      disabled ||= ['walk', 'play'].includes(action) && pet?.energy < 12;
      button.querySelector('.action-status').textContent = remaining > 0
        ? `◷ ${timeLeft(remaining)}` : ['walk', 'play'].includes(action) && pet?.energy < 12
          ? 'Нужен отдых' : labels[action];
    }
    button.disabled = disabled;
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
  $('mood').textContent = pet.satiety < 30 ? 'Мечтает о чём-нибудь вкусном' : pet.energy < 20
    ? 'Немного устала, отдыхает' : pet.cleanliness < 30 ? 'Пора устроить плюх-плюх' : pet.joy < 30
      ? 'Скучает по тебе' : 'Счастлива быть рядом';
  $('scene').className = `scene room-${pet.room}`;
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

for (const button of buttons) {
  button.addEventListener('click', async () => {
    if (pending || !pet) return;
    pending = true;
    updateButtons();
    try {
      const oldLevel = pet.level;
      const data = await request('/api/action', button.dataset.action);
      render(data);
      react(data.message);
      if (data.pet.level > oldLevel) notify(`Новый уровень! ${data.pet.level_name} ✦`);
    } catch (error) {
      notify(error.message);
      // Обновление состояния также восстанавливает таймер после потери ответа.
      pending = false;
      await load();
    } finally {
      pending = false;
      updateButtons();
    }
  });
}
$('pig').addEventListener('click', () => react('Хрю! Обнимаю тебя ♡'));
$('retry').addEventListener('click', load);
$('help').addEventListener('click', () => $('help-dialog').showModal());
for (const id of ['close-help', 'help-ok']) $(id).addEventListener('click', () => $('help-dialog').close());
document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
setInterval(updateButtons, 1000);
setInterval(() => { if (!document.hidden) load(); }, 30000);
updateButtons();
load();
