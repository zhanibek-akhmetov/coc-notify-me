"""Офлайн-тест Telegram-бота: имитация Telegram API, все кнопки, оба языка, уведомления, тихие часы, ошибки ввода.

Запуск: python tests/test_bot.py   (сеть и токен не нужны)
"""
import json, os, sys, time, tempfile
from html.parser import HTMLParser

repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(repo, "bot"))
import coc_bot

coc_bot.DATA_FILE = os.path.join(tempfile.mkdtemp(), "db.json")
fails = []


def check(cond, what):
    print(("  ✔ " if cond else "  ✘ ") + what)
    if not cond:
        fails.append(what)


class Html(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack = []; self.bad = None
    def handle_starttag(self, tag, attrs):
        if tag not in {"b", "i", "code", "blockquote"}: self.bad = tag
        self.stack.append(tag)
    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag: self.bad = "close " + tag


class FakeTG:
    def __init__(self): self.out = []; self.edits = []; self.answers = []
    def send(self, chat, text, markup=None):
        p = Html(); p.feed(text)
        if p.bad or p.stack or len(text) > 4096:
            fails.append(f"битый HTML/длина: {p.bad} {p.stack} {len(text)}")
        self.out.append((chat, text, markup))
    def edit(self, chat, mid, text, markup): self.edits.append(text)
    def answer(self, cid, text=""): self.answers.append(text)
    def download(self, fid): return self.files[fid].encode("utf-8").decode("utf-8-sig")  # как настоящий TG.download


tg, db = FakeTG(), coc_bot.load()
last = lambda: tg.out[-1]
M = lambda chat, t, lang="ru": {"chat": {"id": chat}, "text": t, "from": {"language_code": lang}}
CB = lambda chat, d: {"id": "q", "data": d, "message": {"chat": {"id": chat}, "message_id": 1}, "from": {}}
now = int(time.time())

print("1. Новый пользователь, нет данных")
coc_bot.on_message(tg, db, M(1, "/start"))
check("Как пользоваться" in last()[1], "/start → инструкция")
check(last()[2]["inline_keyboard"][0][0]["callback_data"] == "act:menu", "под инструкцией кнопка «Главное меню»")
coc_bot.on_message(tg, db, M(1, "📋 Что идёт"))
check("Таймеров пока нет" in last()[1] and "Экспорт данных" in last()[1], "пустой список → инструкция по экспорту")
check(len(last()[2]["inline_keyboard"][0]) == 2, "под ней 2 кнопки (меню + как пользоваться)")
coc_bot.on_callback(tg, db, CB(1, "act:menu"))
check("Главное меню" in last()[1], "кнопка «Главное меню» работает")
check([b["callback_data"] for b in last()[2]["inline_keyboard"][0]] == ["act:help", "act:tz"], "в меню «Как пользоваться» и «Часовой пояс»")
coc_bot.on_message(tg, db, M(1, "привет"))
check("Не понял" in last()[1], "мусорный текст → «Не понял»")
coc_bot.on_message(tg, db, M(1, '{"a": 1}'))
check("не экспорт" in last()[1], "чужой JSON → понятная ошибка")

print("2. Экспорт (разрезанный на 2 сообщения)")
exp = {"tag": "#T", "timestamp": now - 60,
       "buildings": [{"data": 1000015, "lvl": 1, "cnt": 5}, {"data": 1000007, "lvl": 4, "cnt": 1},
                     {"data": 1000008, "lvl": 6, "timer": 600}, {"data": 1000008, "lvl": 6, "timer": 4000},
                     {"data": 1000028, "lvl": 0, "timer": 30}],
       "units": [{"data": 4000004, "lvl": 2, "timer": 9000}],
       "heroes": [{"data": 28000000, "lvl": 3, "timer": 20000}],
       "buildings2": [{"data": 1000034, "lvl": 2, "cnt": 1}, {"data": 1000046, "lvl": 1, "cnt": 1},
                      {"data": 1000042, "lvl": 0, "timer": 7200}],
       "units2": [{"data": 4000032, "lvl": 3, "timer": 3000}]}
raw = json.dumps(exp, ensure_ascii=False)
n = len(tg.out)
coc_bot.on_message(tg, db, M(1, raw[:400]))
check(len(tg.out) == n, "первая половина — бот молча ждёт продолжения")
coc_bot.on_message(tg, db, M(1, raw[400:]))
t = last()[1]
check("принят" in t and "Пушка #1 → 7" in t, "склеил и принял экспорт")
check(t.index("ОСНОВНАЯ") < t.index("ДЕРЕВНЯ СТРОИТЕЛЯ"), "основная деревня выше деревни строителя")
check("Уже завершено: 1" in t, "уже завершённое показано отдельно")
check("👷 <b>2/5</b>" in t, "2 свободных строителя из 5 выделены жирным (заняты: 2 пушки + король)")
check("Король варваров → 4" in t, "герой распознан")

print("2b. Меньше минуты до конца (символ «<» в HTML)")
acc0 = db["chats"]["1"]["accounts"]["#T"]
saved = [i["end"] for i in acc0["items"]]
for i in acc0["items"]:
    if not i["sent"]: i["end"] = now + 20
n_fail = len(fails)
coc_bot.on_message(tg, db, M(1, "📋 Что идёт"))
check("&lt;1м" in last()[1] and len(fails) == n_fail, "«<1м» экранирован, HTML валиден")
coc_bot.on_message(tg, db, M(1, "⏭ Ближайшее"))
check(len(fails) == n_fail, "«Ближайшее» с <1м — HTML валиден")
for i, e in zip(acc0["items"], saved): i["end"] = e

print("3. Кнопки на русском")
for btn, must in [("⏭ Ближайшее", "⏭"), ("👷 Свободные", "Свободно"), ("🌙 Тихие часы", "Тихие часы"),
                  ("🏠 Меню", "Главное меню"), ("/list", "ОСНОВНАЯ")]:
    coc_bot.on_message(tg, db, M(1, btn))
    check(must in last()[1], f"{btn}")
coc_bot.on_callback(tg, db, CB(1, "quiet:23:00-07:00"))
check(db["chats"]["1"]["quiet"] == ["23:00", "07:00"] and "23:00–07:00" in tg.answers[-1], "выбор тихих часов сохраняется")
coc_bot.on_callback(tg, db, CB(1, "quiet:off"))
check(db["chats"]["1"]["quiet"] is None, "тихие часы выключаются")

print("3b. График и часовой пояс")
coc_bot.on_message(tg, db, M(7, "📊 График"))
check("нужен экспорт" in last()[1], "без экспорта — подсказка прислать экспорт")
th8 = json.load(open(os.path.join(repo, "planner", "examples", "export_th8.json"), encoding="utf-8-sig"))
th8["timestamp"] = now - 60
coc_bot.on_message(tg, db, M(7, json.dumps(th8)))
check("export" in db["chats"]["7"]["accounts"]["#EXAMPLE"], "экспорт сохранён для графика")
coc_bot.on_message(tg, db, M(7, "📊 График"))
opts = [b[0]["callback_data"] for b in last()[2]["inline_keyboard"]]
check("Что учитывать" in last()[1] and opts == ["po:lab", "po:heroes", "po:res", "po:go"],
      "сначала выбор: лаборатория, герои, ресурсные здания + «Построить»")
check(all(b[0]["text"].startswith("✅") for b in last()[2]["inline_keyboard"][:3]), "по умолчанию всё отмечено")
n = len(tg.out)
coc_bot.on_callback(tg, db, CB(7, "po:go"))
check(len(tg.out) == n + 2 and "Строю план" in tg.out[n][1], "«Построить»: сначала «строю план», потом результат")
btn = last()[2]["inline_keyboard"][0][0]
check(btn["url"].startswith("https://zhanibek-akhmetov.github.io/coc-notify-me/#p=") and len(btn["url"]) < 4000,
      f"кнопка-ссылка на график ({len(btn['url'])} симв.)")
check("Ратуша 8 на максимум → ратуша 9" in last()[1] and "UTC+5" in last()[1], "в сообщении план и часовой пояс")
coc_bot.on_callback(tg, db, CB(7, "act:tz"))
check("Часовой пояс" in last()[1] and len(last()[2]["inline_keyboard"]) == 7, "выбор часового пояса: 7 вариантов")
t_before = db["chats"]["7"]["accounts"]["#EXAMPLE"]["ts"]
coc_bot.on_callback(tg, db, CB(7, "tz:1"))
check(db["chats"]["7"]["tz"] == 1 and "UTC+1" in tg.answers[-1], "часовой пояс сохраняется")
coc_bot.on_message(tg, db, M(7, "📋 Что идёт"))
coc_bot.set_tz(db["chats"]["7"])
check(coc_bot.when(t_before) in last()[1], "время в списке — в выбранном поясе")
coc_bot.on_message(tg, db, M(7, "/plan"))
coc_bot.on_callback(tg, db, CB(7, "po:go"))
check("UTC+1" in last()[1], "график строится в выбранном поясе")
import base64, zlib  # noqa: E402
unpack = lambda url: json.loads(zlib.decompress(base64.urlsafe_b64decode(url.split("#p=")[1] + "==")).decode())
coc_bot.on_callback(tg, db, CB(7, "po:heroes"))
check(db["chats"]["7"]["plan_opts"]["heroes"] is False, "галочка «Герои» снимается и запоминается")
coc_bot.on_callback(tg, db, CB(7, "po:go"))
P = unpack(last()[2]["inline_keyboard"][0][0]["url"])
heroes_planned = [x for x in P["i"] if x[3] in (28000000, 28000001) and x[7] != "c"]
check(P["o"] == [1, 0, 1] and not heroes_planned and "герои" not in last()[1].split("Учтено:")[1].split("\n")[0],
      "без героев: в плане нет улучшений героев, в сообщении «Учтено» без героев")
coc_bot.on_callback(tg, db, CB(7, "po:heroes"))
coc_bot.on_callback(tg, db, CB(7, "tz:5"))
coc_bot.on_message(tg, db, M(7, "🏠 Меню"))
check([b["callback_data"] for b in last()[2]["inline_keyboard"][0]] == ["act:help", "act:tz"],
      "в меню: «Как пользоваться» и «Часовой пояс»")

print("4. Уведомления")
acc = db["chats"]["1"]["accounts"]["#T"]
for i in acc["items"]:
    if i.get("did") == 1000008 and i.get("num") == 1: i["end"] = now - 1
n = len(tg.out); coc_bot.notify_due(tg, db)
check(len(tg.out) == n + 1 and "Готово" in last()[1] and "Пушка #1 → 7" in last()[1], "«Готово» по одной стройке")
n = len(tg.out); coc_bot.notify_due(tg, db)
check(len(tg.out) == n, "повторно не присылает")
db["chats"]["1"]["quiet"] = ["00:00", "23:59"] if not coc_bot.in_quiet({"quiet": ["00:00", "23:59"]}) else ["23:59", "23:58"]
for i in acc["items"]:
    if not i["sent"] and i["village"] == "bb": i["end"] = now - 3600
n = len(tg.out); coc_bot.notify_due(tg, db)
check(len(tg.out) == n, "в тихие часы молчит")
db["chats"]["1"]["quiet"] = ["03:00", "03:01"] if not coc_bot.in_quiet({"quiet": ["03:00", "03:01"]}) else ["05:00", "05:01"]
coc_bot.notify_due(tg, db)
check("Доброе утро" in last()[1] and "ДЕРЕВНЯ СТРОИТЕЛЯ" in last()[1], "после тихих часов — утренняя сводка")
db["chats"]["1"]["quiet"] = None

print("5. English")
coc_bot.on_message(tg, db, M(1, "🌐 English"))
check("Language: English" in last()[1] and last()[2]["keyboard"][2] == ["📊 Chart", "🏠 Menu", "🌐 Русский"], "переключение + английская клавиатура")
coc_bot.on_message(tg, db, M(1, "📋 Running"))
check("HOME VILLAGE" in last()[1] and "Cannon #2 → 7" in last()[1] and "Barbarian King → 4" in last()[1], "список на английском, названия переведены")
coc_bot.on_message(tg, db, M(1, "👷 Builders"))
check("free" in last()[1], "Builders на английском")
coc_bot.on_message(tg, db, M(1, "🌐 Русский"))
check("Язык: русский" in last()[1], "обратно на русский")
coc_bot.on_message(tg, db, M(2, "/start", "en"))
check("How to use" in last()[1], "новый пользователь с английским Telegram получает английский")

print("6. Файл, /clear, перезапуск")
tg.files = {"f1": "﻿" + raw}
coc_bot.on_message(tg, db, {"chat": {"id": 3}, "document": {"file_id": "f1", "file_size": 3000}, "from": {}})
check("принят" in last()[1] or "received" in last()[1], "экспорт файлом (с BOM)")
coc_bot.save(db)
db2 = coc_bot.load()
check(db2["chats"]["1"]["accounts"]["#T"]["items"][0]["did"] == db["chats"]["1"]["accounts"]["#T"]["items"][0]["did"],
      "данные переживают перезапуск")
coc_bot.on_message(tg, db, M(1, "/clear"))
check(db["chats"]["1"]["accounts"] == {}, "/clear очищает")

print("\nИТОГ:", "всё работает ✅" if not fails else f"ОШИБКИ ({len(fails)}): {fails}")
sys.exit(1 if fails else 0)
