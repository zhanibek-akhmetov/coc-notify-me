"""Telegram-бот: присылаешь экспорт деревни Clash of Clans — бот пишет, когда стройки и исследования завершатся.

Запуск:
    python coc_bot.py            (токен из переменной TELEGRAM_BOT_TOKEN или из файла bot_token.txt)
Проверка разбора без Telegram:
    python coc_bot.py --parse export.json

Кнопки: Что идёт, Ближайшее, Свободные, Тихие часы, язык (русский / English).
Данные хранятся в bot_data.json рядом со скриптом, переживают перезапуск.
Сообщения оформлены HTML-разметкой Telegram (жирный, моноширинный, цитаты) — Premium не нужен.
"""
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=5))  # часовой пояс для отображения (Кызылорда)
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "bot_data.json")
TOKEN_FILE = os.path.join(HERE, "bot_token.txt")
LOG_FILE = os.path.join(HERE, "bot.log")
LANGS = ("ru", "en")


def log(*parts):
    """Пишет в консоль (если есть) и в bot.log — при запуске через pythonw консоли нет."""
    line = datetime.now(TZ).strftime("%d.%m %H:%M:%S ") + " ".join(map(str, parts))
    if sys.stdout:
        print(line, flush=True)
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 1_000_000:
            os.replace(LOG_FILE, LOG_FILE + ".old")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_names():
    """Официальные названия из игры на двух языках (coc_names.json, собирается build_names.py)."""
    try:
        with open(os.path.join(HERE, "coc_names.json"), encoding="utf-8") as f:
            raw = json.load(f)
        return {lang: {int(k): v.get(lang) or v.get("ru") for k, v in raw.items()} for lang in LANGS}
    except (OSError, ValueError, KeyError):
        return {lang: {} for lang in LANGS}


NAMES = load_names()
HOME, BB = "home", "bb"
VILLAGE_ICON = {HOME: "🏠", BB: "🛠"}
# раздел экспорта -> (значок, деревня, очередь: builder — строители, lab — лаборатория, other — своя очередь)
SECTIONS = {
    "buildings": ("🔨", HOME, "builder"), "traps": ("🔨", HOME, "builder"), "heroes": ("👑", HOME, "builder"),
    "units": ("🧪", HOME, "lab"), "spells": ("🧪", HOME, "lab"), "siege_machines": ("🧪", HOME, "lab"),
    "pets": ("🐾", HOME, "other"), "equipment": ("⚒", HOME, "other"),
    "buildings2": ("🔨", BB, "builder"), "traps2": ("🔨", BB, "builder"), "heroes2": ("👑", BB, "builder"),
    "units2": ("🧪", BB, "lab"),
}
BUILD_SECTIONS = ("buildings", "traps", "buildings2", "traps2")
HOME_BUILDER_HUTS = (1000015, 1000064)       # хижины строителя + хижина Б.О.Б.
HOME_LAB, BB_LAB, BB_OTTO = 1000007, 1000046, 1000078
DEFAULT_CAPS = {HOME: {"builders": 5, "lab": True}, BB: {"builders": 1, "lab": True}}
QUIET_PRESETS = [("23:00", "07:00"), ("00:00", "08:00"), ("00:30", "08:00"), ("01:00", "09:00")]

# ---------- тексты ----------
T = {
    "ru": {
        "village": {HOME: "🏠 ОСНОВНАЯ ДЕРЕВНЯ", BB: "🛠 ДЕРЕВНЯ СТРОИТЕЛЯ"},
        "units": ("д", "ч", "м"),
        "new": "постройка",
        "busy": "занята", "free": "свободна",
        "btn": {"list": "📋 Что идёт", "next": "⏭ Ближайшее", "free": "👷 Свободные",
                "quiet": "🌙 Тихие часы", "plan": "📊 График", "menu": "🏠 Меню", "lang": "🌐 English"},
        "ibtn": {"menu": "🏠 Главное меню", "help": "❓ Как пользоваться", "tz": "🕐 Часовой пояс"},
        "commands": [("menu", "Главное меню"), ("list", "Что сейчас идёт"), ("next", "Что завершится ближайшим"),
                     ("free", "Когда освободятся строители"), ("plan", "График прокачки"), ("quiet", "Тихие часы"),
                     ("tz", "Часовой пояс"), ("help", "Как пользоваться"), ("lang", "Switch to English"),
                     ("clear", "Забыть все таймеры")],
        "plan_wait": "⏳ Строю план прокачки… это займёт несколько секунд.",
        "plan_none": ("📊 Для графика нужен экспорт деревни — пришли его, и я построю план "
                      "(какие улучшения и когда запускать, чтобы быстрее всего прокачать ратушу)."),
        "plan_fail": "❌ Не получилось построить план: {e}.",
        "plan_title": "📊 <b>План прокачки</b> · {tag}",
        "plan_body": ("Ратуша {th} на максимум → ратуша {th1}\n"
                      "🏁 Всё готово: <b>{end}</b>\n"
                      "🏰 Ратуша {th1}: <b>{th_end}</b>\n"
                      "{parts}\n"
                      "<i>Экспорт от {ts} · сон {bed}–{wake} · {tz}</i>\n\n"
                      "График открывается в браузере: весь план зашит в ссылку и нигде не сохраняется. "
                      "Нажимай на полоски — отмечай, что уже поставил."),
        "open": "📊 Открыть график",
        "po_title": "📊 <b>Что учитывать в графике?</b>\nОтметь нужное и нажми «Построить». Ратуша, армейские здания и замок клана учитываются всегда.",
        "po_parts": {"def": "🛡 Оборона", "lab": "🧪 Лаборатория", "heroes": "👑 Герои", "res": "💰 Ресурсные здания"},
        "po_go": "📊 Построить график",
        "plan_parts": "Учтено: {x}",
        "plan_parts_base": "ратуша и армейские здания",
        "tz_title": "🕐 <b>Часовой пояс:</b> {tz}\n\nВ нём показываю время, считаю тихие часы и строю график.",
        "tz_ans": "Часовой пояс: {tz}",
        "tz_names": {0: "Лондон (зима), Лиссабон", 1: "Лондон (лето), Берлин, Париж", 2: "Киев, Хельсинки",
                     3: "Москва, Стамбул", 4: "Дубай, Баку", 5: "Казахстан, Ташкент", 6: "Бишкек, Омск"},
        "no_data": ("📭 <b>Таймеров пока нет</b>\n\n"
                    "Пришли мне экспорт деревни — и я начну следить за стройками и исследованиями.\n\n"
                    "<b>Как сделать экспорт</b>\n"
                    "1. Открой Clash of Clans\n"
                    "2. ⚙️ Настройки → <b>Другие настройки</b>\n"
                    "3. Пролистай вниз: <b>Экспорт данных</b> → <b>Копировать</b>\n"
                    "4. Вернись сюда, вставь в поле сообщения и отправь 📥"),
        "menu_title": "🏠 <b>Главное меню</b>",
        "menu_next": "⏭ Ближайшее:",
        "menu_empty": "Таймеров пока нет — пришли экспорт деревни 📥",
        "menu_hint": "<i>Запустил новые улучшения — пришли свежий экспорт.</i>",
        "export": "экспорт {t}",
        "export_ok": "экспорт {t} принят",
        "old_export": "⚠️ Экспорт старый ({d} назад) — лучше скопируй свежий.",
        "already": "✅ <b>Уже завершено: {n}</b>",
        "all_free": "✨ Всё свободно — можно запускать!",
        "nothing": "✨ Ничего не идёт — всё свободно!",
        "free_some": "👷 <b>Свободно {f} из {n}</b> — можно запускать!",
        "free_none": "👷 Свободно 0 из {n}",
        "lab_busy": "🧪 Лаборатория:",
        "lab_free": "🧪 Лаборатория <b>свободна</b> — можно запускать!",
        "free_note": "<i>Учитываю только последний экспорт. Запустил новое — пришли свежий.</i>",
        "quiet_title": "🌙 <b>Тихие часы:</b> ",
        "quiet_off": "выключены",
        "quiet_text": "\n\nВ это время я молчу, а утром пришлю одно сообщение — что завершилось за ночь.",
        "quiet_btn_off": "Выключить",
        "quiet_ans_off": "Тихие часы выключены", "quiet_ans_on": "Тихие часы: {v}",
        "done": "✅ <b>Готово</b>",
        "morning": "🌅 <b>Доброе утро!</b>", "overnight": "За ночь завершилось: {n}",
        "next": "⏭ Дальше:",
        "all_done": "✨ <i>Всё из экспорта завершено — запусти новое и пришли свежий экспорт.</i>",
        "cleared": "🗑 Все таймеры удалены.",
        "too_big": "Файл слишком большой.",
        "not_understood": "🤔 Не понял. Пришли экспорт деревни из игры (текст начинается с <code>{</code>) "
                          "или нажми кнопку внизу.",
        "failed": "❌ Не получилось: {e}.",
        "not_export": "это не экспорт деревни (нет поля timestamp)",
        "lang_set": "🇷🇺 Язык: русский",
        "help": ("❓ <b>Как пользоваться</b>\n\n"
                 "Я напомню, когда в Clash of Clans закончится стройка, исследование или улучшение героя — "
                 "в основной деревне и в деревне строителя.\n\n"
                 "<b>1. Сделай экспорт</b>\n"
                 "⚙️ Настройки → Другие настройки → Экспорт данных → Копировать\n\n"
                 "<b>2. Отправь его мне</b>\n"
                 "Вставь в поле сообщения и отправь (можно и файлом .json/.txt).\n\n"
                 "<b>3. Жди уведомлений</b>\n"
                 "Напишу, как только что-то завершится. Запустил новые улучшения — пришли свежий экспорт, "
                 "я заменю таймеры.\n\n"
                 "<b>Кнопки</b>\n"
                 "📋 Что идёт — все таймеры\n⏭ Ближайшее — что завершится следующим\n"
                 "👷 Свободные — когда освободятся строители и лаборатория\n🌙 Тихие часы — не будить ночью\n"
                 "📊 График — план прокачки ратуши (откроется в браузере)\n🏠 Меню — главное меню, там же 🕐 часовой пояс\n🌐 English — switch to English\n/clear — забыть все таймеры"),
    },
    "en": {
        "village": {HOME: "🏠 HOME VILLAGE", BB: "🛠 BUILDER BASE"},
        "units": ("d", "h", "m"),
        "new": "new",
        "busy": "busy", "free": "free",
        "btn": {"list": "📋 Running", "next": "⏭ Next", "free": "👷 Builders",
                "quiet": "🌙 Quiet hours", "plan": "📊 Chart", "menu": "🏠 Menu", "lang": "🌐 Русский"},
        "ibtn": {"menu": "🏠 Main menu", "help": "❓ How to use", "tz": "🕐 Time zone"},
        "commands": [("menu", "Main menu"), ("list", "What's running now"), ("next", "What finishes next"),
                     ("free", "When builders get free"), ("plan", "Upgrade chart"), ("quiet", "Quiet hours"),
                     ("tz", "Time zone"), ("help", "How to use"), ("lang", "Переключить на русский"),
                     ("clear", "Forget all timers")],
        "plan_wait": "⏳ Building your upgrade plan… this takes a few seconds.",
        "plan_none": ("📊 The chart needs your village export — send it and I'll build a plan "
                      "(which upgrades to start and when, to max your Town Hall as fast as possible)."),
        "plan_fail": "❌ Couldn't build the plan: {e}.",
        "plan_title": "📊 <b>Upgrade plan</b> · {tag}",
        "plan_body": ("Max Town Hall {th} → Town Hall {th1}\n"
                      "🏁 All done: <b>{end}</b>\n"
                      "🏰 Town Hall {th1}: <b>{th_end}</b>\n"
                      "{parts}\n"
                      "<i>Export from {ts} · sleep {bed}–{wake} · {tz}</i>\n\n"
                      "The chart opens in your browser: the whole plan is inside the link and isn't stored anywhere. "
                      "Tap bars to mark what you've started."),
        "open": "📊 Open chart",
        "po_title": "📊 <b>What should the chart include?</b>\nTick what you need and tap «Build». The Town Hall, army buildings and the Clan Castle are always included.",
        "po_parts": {"def": "🛡 Defenses", "lab": "🧪 Laboratory", "heroes": "👑 Heroes", "res": "💰 Resource buildings"},
        "po_go": "📊 Build chart",
        "plan_parts": "Included: {x}",
        "plan_parts_base": "Town Hall & army buildings",
        "tz_title": "🕐 <b>Time zone:</b> {tz}\n\nUsed for times in messages, quiet hours and the chart.",
        "tz_ans": "Time zone: {tz}",
        "tz_names": {0: "London (winter), Lisbon", 1: "London (summer), Berlin, Paris", 2: "Kyiv, Helsinki",
                     3: "Moscow, Istanbul", 4: "Dubai, Baku", 5: "Kazakhstan, Tashkent", 6: "Bishkek, Omsk"},
        "no_data": ("📭 <b>No timers yet</b>\n\n"
                    "Send me your village export and I'll start tracking your upgrades and research.\n\n"
                    "<b>How to export</b>\n"
                    "1. Open Clash of Clans\n"
                    "2. ⚙️ Settings → <b>More Settings</b>\n"
                    "3. Scroll down: <b>Data Export</b> → <b>Copy</b>\n"
                    "4. Come back here, paste it into the message field and send 📥"),
        "menu_title": "🏠 <b>Main menu</b>",
        "menu_next": "⏭ Next:",
        "menu_empty": "No timers yet — send your village export 📥",
        "menu_hint": "<i>Started new upgrades — send a fresh export.</i>",
        "export": "export {t}",
        "export_ok": "export {t} received",
        "old_export": "⚠️ This export is old ({d} ago) — better copy a fresh one.",
        "already": "✅ <b>Already done: {n}</b>",
        "all_free": "✨ All free — start something!",
        "nothing": "✨ Nothing running — all free!",
        "free_some": "👷 <b>{f} of {n} free</b> — start something!",
        "free_none": "👷 0 of {n} free",
        "lab_busy": "🧪 Laboratory:",
        "lab_free": "🧪 Laboratory <b>free</b> — start something!",
        "free_note": "<i>Based on your last export only. Started something new — send a fresh one.</i>",
        "quiet_title": "🌙 <b>Quiet hours:</b> ",
        "quiet_off": "off",
        "quiet_text": "\n\nDuring this time I stay silent and send one message in the morning with everything that finished overnight.",
        "quiet_btn_off": "Turn off",
        "quiet_ans_off": "Quiet hours off", "quiet_ans_on": "Quiet hours: {v}",
        "done": "✅ <b>Done</b>",
        "morning": "🌅 <b>Good morning!</b>", "overnight": "Finished overnight: {n}",
        "next": "⏭ Next:",
        "all_done": "✨ <i>Everything from the export is done — start new upgrades and send a fresh export.</i>",
        "cleared": "🗑 All timers deleted.",
        "too_big": "The file is too big.",
        "not_understood": "🤔 I didn't get that. Send your village export from the game (text starting with "
                          "<code>{</code>) or tap a button below.",
        "failed": "❌ Couldn't read it: {e}.",
        "not_export": "this is not a village export (no timestamp field)",
        "lang_set": "🇬🇧 Language: English",
        "help": ("❓ <b>How to use</b>\n\n"
                 "I'll let you know when a Clash of Clans building, research or hero upgrade finishes — "
                 "in the Home Village and the Builder Base.\n\n"
                 "<b>1. Export your village</b>\n"
                 "⚙️ Settings → More Settings → Data Export → Copy\n\n"
                 "<b>2. Send it to me</b>\n"
                 "Paste it into the message field and send (a .json/.txt file works too).\n\n"
                 "<b>3. Wait for notifications</b>\n"
                 "I'll message you as soon as something finishes. Started new upgrades — send a fresh export "
                 "and I'll replace the timers.\n\n"
                 "<b>Buttons</b>\n"
                 "📋 Running — all timers\n⏭ Next — what finishes next\n"
                 "👷 Builders — when builders and the lab get free\n🌙 Quiet hours — don't wake me at night\n"
                 "📊 Chart — Town Hall upgrade plan (opens in your browser)\n🏠 Menu — main menu, with 🕐 time zone\n🌐 Русский — переключить на русский\n/clear — forget all timers"),
    },
}
BUTTONS = {lang: {v: k for k, v in T[lang]["btn"].items()} for lang in LANGS}  # текст кнопки -> действие


def keyboard(lang):
    b = T[lang]["btn"]
    return {"keyboard": [[b["list"], b["next"]], [b["free"], b["quiet"]], [b["plan"], b["menu"], b["lang"]]],
            "resize_keyboard": True, "is_persistent": True}


def inline_nav(lang, *which):
    """Кнопки под сообщением: главное меню / как пользоваться / часовой пояс."""
    return {"inline_keyboard": [[{"text": T[lang]["ibtn"][w], "callback_data": f"act:{w}"} for w in which]]}


# ---------- часовой пояс чата ----------
DEFAULT_TZ = 5          # Казахстан
TZ_PRESETS = (0, 1, 2, 3, 4, 5, 6)


def tz_label(hours):
    return "UTC" + (f"{hours:+g}" if hours else "")


def set_tz(chat):
    """Все форматтеры времени и тихие часы работают в часовом поясе текущего чата."""
    global TZ
    TZ = timezone(timedelta(hours=chat.get("tz", DEFAULT_TZ)))


def tz_view(chat):
    L, cur = T[chat["lang"]], chat.get("tz", DEFAULT_TZ)
    rows = [[{"text": ("✅ " if h == cur else "") + f"{tz_label(h)} · {L['tz_names'][h]}", "callback_data": f"tz:{h}"}]
            for h in TZ_PRESETS]
    return L["tz_title"].format(tz=f"{tz_label(cur)} ({L['tz_names'].get(cur, '')})"), {"inline_keyboard": rows}


esc = html.escape
fmt = lambda ts: datetime.fromtimestamp(ts, TZ).strftime("%d.%m %H:%M")
hm = lambda ts: datetime.fromtimestamp(ts, TZ).strftime("%H:%M")
when = lambda ts: hm(ts) if datetime.fromtimestamp(ts, TZ).date() == datetime.now(TZ).date() else fmt(ts)  # сегодня — только время


# ---------- оформление ----------
def dur(sec, lang="ru"):
    """Коротко: 45м, 2ч 42м, 1д 3ч (45m, 2h 42m, 1d 3h)."""
    du, hu, mu = T[lang]["units"]
    m = max(0, int(sec)) // 60
    if m < 1:
        return f"<1{mu}"
    d, h, m = m // 1440, m % 1440 // 60, m % 60
    if d:
        return f"{d}{du} {h}{hu}" if h else f"{d}{du}"
    if h:
        return f"{h}{hu} {m}{mu}" if m else f"{h}{hu}"
    return f"{m}{mu}"


def tcol(sec, lang, width=6):
    """Время моноширинным шрифтом, выровненное вправо — получается ровная колонка."""
    return f"<code>{esc(f'{dur(sec, lang):>{width}}')}</code>"  # esc: «<1м» иначе ломает HTML


def short(i, lang):
    """«Сборщик эликсира #1 → 9» / «Army Camp — new» на нужном языке."""
    if "did" in i:
        name = NAMES[lang].get(i["did"]) or NAMES["ru"].get(i["did"]) or f"#{i['did']}"
        if i.get("num"):
            name += f" #{i['num']}"
        name += f" — {T[lang]['new']}" if i.get("new") else f" → {i['lvl']}"
    else:  # старые записи без кода объекта
        name = i["name"]
        if name.endswith(" (постройка)"):
            name = name[:-len(" (постройка)")] + f" — {T[lang]['new']}"
    return esc(name)


def item_line(i, now, lang):
    return f"{tcol(i['end'] - now, lang)} {i['icon']} {short(i, lang)}"


def quote(lines, expandable=False):
    return f"<blockquote{' expandable' if expandable else ''}>" + "\n".join(lines) + "</blockquote>"


# ---------- разбор экспорта ----------
def parse_export(data, lang="ru"):
    """Возвращает (тег, время экспорта, [{did, lvl, new, num, icon, village, track, end}], мощности)."""
    if not isinstance(data, dict) or "timestamp" not in data:
        raise ValueError(T[lang]["not_export"])
    ts = int(data["timestamp"])
    items = []
    for section, (icon, village, track) in SECTIONS.items():
        for x in data.get(section) or []:
            if not isinstance(x, dict) or "timer" not in x:
                continue
            lvl = x.get("lvl", 0)
            new = section in BUILD_SECTIONS and lvl == 0
            items.append(dict(did=x.get("data"), lvl=lvl + 1, new=new, num=0, icon=icon,
                              village=village, track=track, end=ts + int(x["timer"])))
    # одинаковые объекты (в пределах деревни) различаем номерами
    key = lambda it: (it["village"], it["did"], it["new"], it["lvl"])
    seen = {}
    for it in items:
        seen[key(it)] = seen.get(key(it), 0) + 1
    num = {}
    for it in items:
        if seen[key(it)] > 1:
            it["num"] = num[key(it)] = num.get(key(it), 0) + 1

    def count(section, ids):
        return sum(x.get("cnt", 1) for x in data.get(section) or [] if isinstance(x, dict) and x.get("data") in ids)

    caps = {HOME: {"builders": count("buildings", HOME_BUILDER_HUTS) or 2,
                   "lab": count("buildings", (HOME_LAB,)) > 0}}
    if data.get("buildings2"):
        caps[BB] = {"builders": 1 + (count("buildings2", (BB_OTTO,)) > 0),
                    "lab": count("buildings2", (BB_LAB,)) > 0}
    return data.get("tag", "?"), ts, sort_items(items), caps


def sort_items(items):
    """Сначала основная деревня, потом деревня строителя; внутри — по времени окончания."""
    return sorted(items, key=lambda i: (i.get("village", HOME) != HOME, i["end"]))


# ---------- хранилище ----------
def migrate(db):
    """Старые записи: деревня/очередь по умолчанию."""
    for chat in db.get("chats", {}).values():
        chat.setdefault("lang", "ru")
        for acc in chat.get("accounts", {}).values():
            acc.pop("player", None)
            for i in acc.get("items", []):
                if "did" in i:
                    continue
                if "village" not in i:
                    i["village"] = HOME
                    if i["name"].startswith("Дом строителя: "):
                        i["name"], i["village"] = i["name"][len("Дом строителя: "):], BB
                if "track" not in i:
                    i["track"] = {"🧪": "lab", "🐾": "other", "⚒": "other"}.get(i.get("icon"), "builder")
                i["name"] = re.sub(r"Объект (\d+)", lambda m: NAMES["ru"].get(int(m.group(1)), m.group(0)), i["name"])
    return db


def load():
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            return migrate(json.load(f))
    except (OSError, ValueError):
        return {"offset": 0, "chats": {}}


def save(db):
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)
    os.replace(tmp, DATA_FILE)


# ---------- Telegram API ----------
class TG:
    def __init__(self, token):
        self.base = f"https://api.telegram.org/bot{token}/"
        self.file_base = f"https://api.telegram.org/file/bot{token}/"

    def call(self, method, _http=35, **params):
        data = urllib.parse.urlencode({k: json.dumps(v) if isinstance(v, (dict, list)) else v
                                       for k, v in params.items()}).encode()
        with urllib.request.urlopen(self.base + method, data=data, timeout=_http) as r:
            res = json.load(r)
        if not res.get("ok"):
            raise RuntimeError(res)
        return res["result"]

    def send(self, chat, text, markup=None):
        extra = {"reply_markup": markup} if markup else {}
        try:
            self.call("sendMessage", chat_id=chat, text=text[:4096], parse_mode="HTML",
                      disable_web_page_preview=True, **extra)
        except urllib.error.HTTPError as e:  # битая разметка — отправим как простой текст
            log("HTML не принят:", e.read().decode(errors="replace")[:200])
            plain = re.sub(r"<[^>]+>", "", text)
            self.call("sendMessage", chat_id=chat, text=html.unescape(plain)[:4096], **extra)

    def edit(self, chat, message_id, text, markup):
        self.call("editMessageText", chat_id=chat, message_id=message_id, text=text,
                  parse_mode="HTML", reply_markup=markup)

    def answer(self, callback_id, text=""):
        try:
            self.call("answerCallbackQuery", callback_query_id=callback_id, text=text)
        except urllib.error.HTTPError as e:  # нажата кнопка под старым сообщением — не страшно
            log("Ответ на кнопку не принят:", e.read().decode(errors="replace")[:200])

    def download(self, file_id):
        path = self.call("getFile", file_id=file_id)["file_path"]
        with urllib.request.urlopen(self.file_base + path, timeout=60) as r:
            return r.read().decode("utf-8-sig")


# ---------- сводки ----------
def active(acc, now):
    return [i for i in acc["items"] if not i.get("sent") and i["end"] > now]


def villages_of(acc):
    return [HOME] + ([BB] if BB in acc.get("caps", {}) or any(i.get("village") == BB for i in acc["items"]) else [])


def capacity(acc, v, items):
    """(свободно строителей, всего, есть ли лаба, лаба занята)."""
    cap = (acc.get("caps") or {}).get(v) or DEFAULT_CAPS[v]
    busy = sum(1 for i in items if i.get("village", HOME) == v and i.get("track") == "builder")
    lab_busy = any(i.get("village", HOME) == v and i.get("track") == "lab" for i in items)
    return max(0, cap["builders"] - busy), cap["builders"], cap.get("lab", True), lab_busy


def village_head(acc, v, items, lang):
    free, n, has_lab, lab_busy = capacity(acc, v, items)
    # сводка отдельной строкой — на телефоне не переносится; свободное выделяем жирным
    builders = f"{free}/{n}"
    s = f"<b>{T[lang]['village'][v]}</b>\n👷 " + (f"<b>{builders}</b>" if free else builders)
    if has_lab:
        s += "  ·  🧪 " + (T[lang]["busy"] if lab_busy else f"<b>{T[lang]['free']}</b>")
    return s


def villages_block(acc, now, lang):
    """Блоки деревень с таймерами (без заголовка аккаунта)."""
    items = active(acc, now)
    out = []
    for v in villages_of(acc):
        part = sort_items([i for i in items if i.get("village", HOME) == v])
        out.append("")
        out.append(village_head(acc, v, items, lang))
        out.append(quote([item_line(i, now, lang) for i in part] if part else [T[lang]["all_free"]]))
    return out


def list_text(chat):
    lang, now, out = chat["lang"], time.time(), []
    for tag, acc in sorted(chat.get("accounts", {}).items()):
        out.append(f"📋 <b>{esc(tag)}</b> · " + T[lang]["export"].format(t=when(acc["ts"])))
        out += villages_block(acc, now, lang)
        out.append("")
    return "\n".join(out).strip() or T[lang]["no_data"]


def next_text(chat):
    lang, now, out = chat["lang"], time.time(), []
    for tag, acc in sorted(chat.get("accounts", {}).items()):
        items = active(acc, now)
        lines = []
        for v in villages_of(acc):
            part = [i for i in items if i.get("village", HOME) == v]
            if part:
                i = min(part, key=lambda x: x["end"])
                lines.append(f"⏭ {item_line(i, now, lang)}  {VILLAGE_ICON[v]}")
        if len(chat.get("accounts", {})) > 1:
            out.append(f"<b>{esc(tag)}</b>")
        out += lines or [T[lang]["nothing"]]
    return "\n".join(out) or T[lang]["no_data"]


def free_text(chat):
    lang, now, out = chat["lang"], time.time(), []
    L = T[lang]
    for tag, acc in sorted(chat.get("accounts", {}).items()):
        items = active(acc, now)
        out.append(f"👷 <b>{esc(tag)}</b> · " + L["export"].format(t=when(acc["ts"])))
        for v in villages_of(acc):
            free, n, has_lab, _ = capacity(acc, v, items)
            busy = sorted((i for i in items if i.get("village", HOME) == v and i.get("track") == "builder"),
                          key=lambda i: i["end"])
            lines = [L["free_some"].format(f=free, n=n) if free else L["free_none"].format(n=n)]
            lines += [f"{tcol(i['end'] - now, lang)} {short(i, lang)}" for i in busy]
            if has_lab:
                lab = [i for i in items if i.get("village", HOME) == v and i.get("track") == "lab"]
                if lab:
                    i = min(lab, key=lambda x: x["end"])
                    lines.append(f"{L['lab_busy']} {tcol(i['end'] - now, lang, 0)} {short(i, lang)}")
                else:
                    lines.append(L["lab_free"])
            out += ["", f"<b>{L['village'][v]}</b>", quote(lines)]
        out.append("")
    if not out:
        return L["no_data"]
    out.append(L["free_note"])
    return "\n".join(out)


# ---------- тихие часы ----------
def to_min(s):
    h, m = map(int, s.split(":"))
    return h * 60 + m


def in_quiet(chat, ts=None):
    q = chat.get("quiet")
    if not q:
        return False
    m = datetime.fromtimestamp(ts or time.time(), TZ)
    m = m.hour * 60 + m.minute
    a, b = to_min(q[0]), to_min(q[1])
    return a <= m < b if a < b else (m >= a or m < b)


def quiet_view(chat):
    L, q = T[chat["lang"]], chat.get("quiet")
    text = L["quiet_title"] + (f"{q[0]}–{q[1]}" if q else L["quiet_off"]) + L["quiet_text"]
    rows = [[{"text": ("✅ " if q == [a, b] else "") + f"{a}–{b}", "callback_data": f"quiet:{a}-{b}"}]
            for a, b in QUIET_PRESETS]
    rows.append([{"text": ("✅ " if not q else "") + L["quiet_btn_off"], "callback_data": "quiet:off"}])
    return text, {"inline_keyboard": rows}


def get_chat(db, chat_id, user=None):
    chat = db["chats"].get(str(chat_id))
    if chat is None:
        code = ((user or {}).get("language_code") or "").lower()
        chat = db["chats"][str(chat_id)] = {"accounts": {}, "lang": "ru" if code.startswith(("ru", "kk", "uk", "be")) else "en"}
    chat.setdefault("lang", "ru")
    set_tz(chat)
    return chat


# ---------- график прокачки (планировщик из planner/coc_plan.py) ----------
EXPORT_KEYS = ("tag", "timestamp", "buildings", "traps", "heroes", "units", "spells")


def load_planner():
    """coc_plan.py лежит рядом с ботом (рабочая папка) или в ../planner (репозиторий)."""
    for d in (HERE, os.path.join(os.path.dirname(HERE), "planner")):
        if os.path.exists(os.path.join(d, "coc_plan.py")):
            if d not in sys.path:
                sys.path.insert(0, d)
            import coc_plan
            return coc_plan
    raise ValueError("не найден coc_plan.py")


PLAN_PARTS = ("def", "lab", "heroes", "res")


def plan_parts(chat):
    """Что брать в расчёт графика (запоминается для чата; по умолчанию — всё)."""
    return dict({p: True for p in PLAN_PARTS}, **chat.get("plan_opts", {}))


def plan_options_view(chat):
    L, parts = T[chat["lang"]], plan_parts(chat)
    rows = [[{"text": ("✅ " if parts[p] else "⬜ ") + L["po_parts"][p], "callback_data": f"po:{p}"}]
            for p in PLAN_PARTS]
    rows.append([{"text": L["po_go"], "callback_data": "po:go"}])
    return L["po_title"], {"inline_keyboard": rows}


def plan_message(chat, tag, acc):
    """(текст, кнопка-ссылка) для графика по последнему экспорту аккаунта."""
    L, lang = T[chat["lang"]], chat["lang"]
    planner = load_planner()
    q = chat.get("quiet")
    bed, wake = (to_min(q[0]), to_min(q[1])) if q else (planner.BED_MIN, planner.WAKE_MIN)
    tz = chat.get("tz", DEFAULT_TZ)
    parts = plan_parts(chat)
    plan = planner.make_plan(acc["export"], tz, bed, wake, parts=parts)
    th_end = next((x["end"] for x in plan["schedule"] if x["did"] == 1000001), None)
    d = lambda x: x.strftime("%d.%m %H:%M") if x else "—"
    included = [L["plan_parts_base"]] + [L["po_parts"][p].split(" ", 1)[1].lower() for p in PLAN_PARTS if parts[p]]
    text = L["plan_title"].format(tag=esc(tag)) + "\n" + L["plan_body"].format(
        th=plan["th"], th1=plan["th"] + 1, end=d(plan["end"]), th_end=d(th_end), ts=d(plan["start"]),
        bed=f"{bed // 60:02d}:{bed % 60:02d}", wake=f"{wake // 60:02d}:{wake % 60:02d}", tz=tz_label(tz),
        parts=L["plan_parts"].format(x=", ".join(included)))
    return text, {"inline_keyboard": [[{"text": L["open"], "url": planner.plan_link(plan, lang)}]]}


def build_plans(tg, chat, chat_id):
    """Строит и присылает график по каждому аккаунту чата, у которого есть экспорт."""
    lang = chat["lang"]
    send = lambda text, markup=None: tg.send(chat_id, text, markup or keyboard(lang))
    with_export = {t: a for t, a in chat.get("accounts", {}).items() if a.get("export")}
    if not with_export:
        return send(T[lang]["plan_none"], inline_nav(lang, "help"))
    send(T[lang]["plan_wait"])
    for tag, acc in sorted(with_export.items()):
        try:
            text, markup = plan_message(chat, tag, acc)
        except Exception as e:  # неподдерживаемая ратуша, битый экспорт и т.п.
            log("План не построен:", repr(e))
            send(T[lang]["plan_fail"].format(e=esc(str(e))))
            continue
        send(text, markup)


def on_callback(tg, db, cb):
    chat_id = cb["message"]["chat"]["id"]
    chat = get_chat(db, chat_id, cb.get("from"))
    L, data = T[chat["lang"]], cb.get("data", "")
    if data.startswith("po:"):
        part = data[3:]
        if part == "go":
            tg.answer(cb["id"])
            build_plans(tg, chat, chat_id)
            return
        if part in PLAN_PARTS:
            opts = plan_parts(chat)
            opts[part] = not opts[part]
            chat["plan_opts"] = opts
            save(db)
            text, markup = plan_options_view(chat)
            try:
                tg.edit(chat_id, cb["message"]["message_id"], text, markup)
            except (RuntimeError, urllib.error.HTTPError):
                pass
        tg.answer(cb["id"])
    elif data.startswith("tz:"):
        chat["tz"] = float(data[3:]) if "." in data[3:] else int(data[3:])
        set_tz(chat)
        save(db)
        text, markup = tz_view(chat)
        try:
            tg.edit(chat_id, cb["message"]["message_id"], text, markup)
        except (RuntimeError, urllib.error.HTTPError):
            pass
        tg.answer(cb["id"], L["tz_ans"].format(tz=tz_label(chat["tz"])))
    elif data.startswith("quiet:"):
        val = data[6:]
        chat["quiet"] = None if val == "off" else val.split("-")
        save(db)
        text, markup = quiet_view(chat)
        try:
            tg.edit(chat_id, cb["message"]["message_id"], text, markup)
        except (RuntimeError, urllib.error.HTTPError):
            pass  # текст не изменился
        tg.answer(cb["id"], L["quiet_ans_off"] if val == "off" else L["quiet_ans_on"].format(v=val.replace("-", "–")))
    elif data.startswith("act:"):
        tg.answer(cb["id"])
        do_action(tg, db, chat, chat_id, data[4:])
    else:
        tg.answer(cb["id"])


def menu_text(chat):
    """Главное меню: короткая сводка по каждому аккаунту."""
    lang, now = chat["lang"], time.time()
    L = T[lang]
    out = [L["menu_title"]]
    accounts = chat.get("accounts", {})
    if not accounts:
        return "\n\n".join([out[0], L["menu_empty"]])
    for tag, acc in sorted(accounts.items()):
        items = active(acc, now)
        out.append("")
        out.append(f"<b>{esc(tag)}</b> · " + L["export"].format(t=when(acc["ts"])))
        for v in villages_of(acc):
            free, n, has_lab, lab_busy = capacity(acc, v, items)
            b = f"{free}/{n}"
            s = f"{VILLAGE_ICON[v]} 👷 " + (f"<b>{b}</b>" if free else b)
            if has_lab:
                s += "  ·  🧪 " + (L["busy"] if lab_busy else f"<b>{L['free']}</b>")
            out.append(s)
        if items:
            i = min(items, key=lambda x: x["end"])
            out.append(f"{L['menu_next']} {tcol(i['end'] - now, lang, 0)} {i['icon']} {short(i, lang)}")
    out += ["", L["menu_hint"]]
    return "\n".join(out)


def do_action(tg, db, chat, chat_id, action):
    """Кнопки клавиатуры, команды и кнопки под сообщениями ведут сюда. False — действие неизвестно."""
    lang = chat["lang"]
    send = lambda text, markup=None: tg.send(chat_id, text, markup or keyboard(chat["lang"]))
    has_data = bool(chat.get("accounts"))
    if action in ("list", "next", "free") and not has_data:
        return send(T[lang]["no_data"], inline_nav(lang, "menu", "help")) or True
    if action == "start":
        return send(T[lang]["help"], inline_nav(lang, "menu")) or True
    if action == "help":
        return send(T[lang]["help"], inline_nav(lang, "menu")) or True
    if action == "menu":
        return send(menu_text(chat), inline_nav(lang, "help", "tz")) or True  # остальные действия — в клавиатуре внизу
    if action == "tz":
        t, markup = tz_view(chat)
        return send(t, markup) or True
    if action == "plan":
        if not any(a.get("export") for a in chat.get("accounts", {}).values()):
            return send(T[lang]["plan_none"], inline_nav(lang, "help")) or True
        t, markup = plan_options_view(chat)  # сначала — что учитывать, потом «Построить»
        return send(t, markup) or True
    if action == "list":
        return send(list_text(chat)) or True
    if action == "next":
        return send(next_text(chat)) or True
    if action == "free":
        return send(free_text(chat)) or True
    if action == "quiet":
        t, markup = quiet_view(chat)
        return send(t, markup) or True
    if action == "lang":
        chat["lang"] = "en" if lang == "ru" else "ru"
        save(db)
        return send(T[chat["lang"]]["lang_set"]) or True
    if action == "clear":
        chat["accounts"] = {}
        save(db)
        return send(T[lang]["cleared"]) or True
    return False


# ---------- сообщения ----------
def handle_export(tg, db, chat, chat_id, raw):
    lang = chat["lang"]
    data = json.loads(raw)
    tag, ts, items, caps = parse_export(data, lang)
    now = time.time()
    chat.pop("buffer", None)
    for i in items:
        i["sent"] = i["end"] <= now
    chat["accounts"][tag] = {"ts": ts, "items": items, "caps": caps,
                             "export": {k: data[k] for k in EXPORT_KEYS if k in data}}  # для графика
    save(db)
    done = [i for i in items if i["sent"]]
    out = [f"📥 <b>{esc(tag)}</b> · " + T[lang]["export_ok"].format(t=when(ts))]
    if now - ts > 6 * 3600:
        out.append(T[lang]["old_export"].format(d=esc(dur(now - ts, lang))))
    out += villages_block(chat["accounts"][tag], now, lang)
    if done:
        out.append("\n" + T[lang]["already"].format(n=len(done)))
        out.append(quote([f"{i['icon']} {short(i, lang)}  {VILLAGE_ICON[i.get('village', HOME)]}" for i in done],
                         expandable=len(done) > 3))
    tg.send(chat_id, "\n".join(out), keyboard(lang))


def on_message(tg, db, msg):
    chat_id = msg["chat"]["id"]
    chat = get_chat(db, chat_id, msg.get("from"))
    lang = chat["lang"]
    send = lambda text, markup=None: tg.send(chat_id, text, markup or keyboard(chat["lang"]))
    text = (msg.get("text") or "").strip()
    cmd = text.split("@")[0].lower()
    action = BUTTONS["ru"].get(text) or BUTTONS["en"].get(text) or (cmd[1:] if cmd.startswith("/") else None)
    if action and do_action(tg, db, chat, chat_id, action):
        return

    raw = None
    if msg.get("document"):
        if msg["document"].get("file_size", 0) > 2_000_000:
            return send(T[lang]["too_big"])
        raw = tg.download(msg["document"]["file_id"]).strip()
    elif text:
        # длинный экспорт Telegram режет на несколько сообщений — склеиваем
        buf = chat.get("buffer")
        if text.startswith("{"):
            buf = {"text": "", "at": time.time()}
        if buf and time.time() - buf["at"] < 300:
            buf["text"] += text
            buf["at"] = time.time()
            chat["buffer"] = buf
            raw = buf["text"]
    if not raw:
        return send(T[lang]["not_understood"], inline_nav(lang, "menu", "help"))
    try:
        handle_export(tg, db, chat, chat_id, raw)
    except json.JSONDecodeError:
        save(db)  # ждём продолжение в следующем сообщении
    except ValueError as e:
        chat.pop("buffer", None)
        save(db)
        send(T[lang]["failed"].format(e=esc(str(e))))


def done_message(chat, tag, acc, due, now, morning):
    """Текст уведомления о завершении — в том же стиле, что и ответ на экспорт."""
    lang = chat["lang"]
    L, rest = T[lang], active(acc, now)
    out = [f"{L['morning']} · {esc(tag)}", L["overnight"].format(n=len(due))] if morning else [f"{L['done']} · {esc(tag)}"]
    for v in villages_of(acc):
        part = sort_items([i for i in due if i.get("village", HOME) == v])
        if not part:
            continue
        lines = [(f"<code>{hm(i['end'])}</code> " if morning else "") + f"✅ {i['icon']} {short(i, lang)}" for i in part]
        out += ["", village_head(acc, v, rest, lang), quote(lines, expandable=len(lines) > 3)]
    out.append("")
    if rest:
        i = min(rest, key=lambda x: x["end"])
        out.append(f"{L['next']} {tcol(i['end'] - now, lang, 0)} {i['icon']} {short(i, lang)}  {VILLAGE_ICON[i.get('village', HOME)]}")
    else:
        out.append(L["all_done"])
    return "\n".join(out)


def notify_due(tg, db):
    now = time.time()
    changed = False
    for chat_id, chat in db["chats"].items():
        chat.setdefault("lang", "ru")
        set_tz(chat)  # время в уведомлении и тихие часы — в поясе этого чата
        if in_quiet(chat, now):
            continue  # ночью молчим — всё придёт одним сообщением после тихих часов
        for tag, acc in chat.get("accounts", {}).items():
            due = [i for i in acc["items"] if not i.get("sent") and i["end"] <= now]
            if not due:
                continue
            morning = bool(chat.get("quiet")) and any(now - i["end"] > 600 for i in due)
            try:
                tg.send(int(chat_id), done_message(chat, tag, acc, due, now, morning), keyboard(chat["lang"]))
            except Exception as e:  # сеть упала — попробуем в следующий раз
                log("Не отправилось:", e)
                continue
            for i in due:
                i["sent"] = True
            changed = True
    if changed:
        save(db)


def next_wakeup(db):
    """Через сколько секунд проверить уведомления (с учётом тихих часов)."""
    now = time.time()
    best = None
    for chat in db["chats"].values():
        ends = [i["end"] for a in chat.get("accounts", {}).values() for i in a["items"] if not i.get("sent")]
        if not ends:
            continue
        t = max(min(ends), now)
        set_tz(chat)
        if chat.get("quiet") and in_quiet(chat, t):
            t += 60  # внутри тихих часов просто перепроверяем раз в минуту
        best = t if best is None else min(best, t)
    return None if best is None else best - now


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--parse":
        with open(sys.argv[2], encoding="utf-8-sig") as f:
            tag, ts, items, caps = parse_export(json.load(f))
        print(f"{tag}, экспорт от {fmt(ts)}, мощности: {caps}")
        for i in items:
            print(f"  {VILLAGE_ICON[i['village']]} {i['icon']} {short(i, 'ru'):35} | {short(i, 'en'):35} "
                  f"{fmt(i['end'])}  [{i['track']}]")
        return

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token and os.path.exists(TOKEN_FILE):
        token = open(TOKEN_FILE, encoding="utf-8").read().strip()
    if not token:
        sys.exit("Нет токена: задай TELEGRAM_BOT_TOKEN или положи токен в bot_token.txt рядом со скриптом.")

    tg = TG(token)
    while True:  # после включения компьютера сеть может появиться не сразу
        try:
            me = tg.call("getMe")
            # меню команд: по умолчанию английское, для русскоязычного Telegram — русское
            tg.call("setMyCommands", commands=[{"command": c, "description": d} for c, d in T["en"]["commands"]])
            tg.call("setMyCommands", commands=[{"command": c, "description": d} for c, d in T["ru"]["commands"]],
                    language_code="ru")
            break
        except (urllib.error.URLError, OSError) as e:
            log("Нет связи с Telegram:", e, "— повтор через 30 с")
            time.sleep(30)
    log(f"Бот @{me['username']} запущен.")
    db = load()
    save(db)
    while True:
        try:
            notify_due(tg, db)
            nw = next_wakeup(db)
            wait = 25 if nw is None else max(1, min(25, int(nw) + 1))
            updates = tg.call("getUpdates", _http=wait + 10, offset=db["offset"], timeout=wait,
                              allowed_updates=["message", "callback_query"])
            for u in updates:
                db["offset"] = u["update_id"] + 1
                try:
                    if "message" in u:
                        on_message(tg, db, u["message"])
                    elif "callback_query" in u:
                        on_callback(tg, db, u["callback_query"])
                except Exception as e:
                    detail = e.read().decode(errors="replace")[:300] if isinstance(e, urllib.error.HTTPError) else ""
                    log("Ошибка обработки:", repr(e), detail)
                save(db)
        except KeyboardInterrupt:
            log("Остановлен.")
            return
        except (urllib.error.URLError, OSError, RuntimeError) as e:
            log("Сеть/Telegram:", e, "— повтор через 10 с")
            time.sleep(10)


if __name__ == "__main__":
    main()
