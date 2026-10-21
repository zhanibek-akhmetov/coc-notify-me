"""План прокачки текущей ратуши до максимума + улучшение до следующей, по экспорту деревни.

Запуск: python coc_plan.py export.json
Результат: plan_th<N>.json и plan_th<N>.html (N — текущий уровень ратуши).
Поддерживаются ратуши 5, 6 и 7.

Цены и время — Clash of Clans Wiki (fandom), октябрь 2026.
Симуляция: 5 строителей + лаборатория; игрок не спит с 08:00 до 00:30,
ночью новые улучшения не запускаются. Ресурсы считаются доступными.
"""
import html
import json
import random
import sys
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=5))   # Кызылорда
WAKE_MIN, BED_MIN = 8 * 60, 30      # бодрствование 08:00 – 00:30
H = lambda h=0, m=0: h * 60 + m
G, E, D = "золото", "эликсир", "тёмный эликсир"

# id: (название, ресурс, {уровень: (цена, минуты, нужная ратуша)}); минуты 0 = мгновенно, без строителя
BUILD = {
    1000000: ("Военный лагерь", E, {1: (200, 1, 1), 2: (2_000, 5, 2), 3: (10_000, 30, 3), 4: (100_000, H(2), 4),
                                     5: (250_000, H(6), 5), 6: (500_000, H(12), 6), 7: (1_500_000, H(48), 9)}),
    1000006: ("Казармы", E, {6: (120_000, H(4), 4), 7: (270_000, H(6), 5), 8: (600_000, H(12), 6), 9: (1_000_000, H(24), 7),
                             10: (1_400_000, H(36), 8)}),
    1000007: ("Лаборатория", E, {3: (50_000, H(2), 5), 4: (100_000, H(4), 6), 5: (200_000, H(8), 7), 6: (400_000, H(16), 8)}),
    1000020: ("Фабрика заклинаний", E, {1: (150_000, H(6), 5), 2: (300_000, H(12), 6), 3: (600_000, H(24), 7)}),
    1000014: ("Замок клана", G, {2: (50_000, H(2), 4), 3: (600_000, H(12), 6), 4: (1_200_000, H(24), 8)}),
    1000005: ("Хранилище золота", E, {7: (25_000, H(2), 4), 8: (50_000, H(3), 4), 9: (100_000, H(4), 5),
                                      10: (250_000, H(5), 6), 11: (500_000, H(6), 7)}),
    1000003: ("Хранилище эликсира", G, {7: (25_000, H(2), 4), 8: (50_000, H(3), 4), 9: (100_000, H(4), 5),
                                        10: (250_000, H(5), 6), 11: (500_000, H(6), 7)}),
    1000004: ("Золотая шахта", E, {}),     # уровни ниже, одинаковые со сборщиком
    1000002: ("Сборщик эликсира", G, {}),
    1000008: ("Пушка", G, {1: (250, 1, 1), 2: (1_000, 1, 1), 3: (4_000, 2, 2), 4: (16_000, 20, 3), 5: (50_000, 30, 4),
                           6: (60_000, H(1), 5), 7: (100_000, H(2), 6), 8: (160_000, H(3), 7),
                           9: (250_000, H(3, 30), 8), 10: (330_000, H(4), 8)}),
    1000009: ("Башня лучниц", G, {1: (1_000, 1, 2), 2: (2_000, 2, 2), 3: (5_000, 20, 3), 4: (20_000, H(1), 4),
                                  5: (70_000, H(1, 30), 5), 6: (80_000, H(2), 5), 7: (150_000, H(3), 6), 8: (200_000, H(4), 7),
                                  9: (400_000, H(5), 8), 10: (460_000, H(6), 8)}),
    1000013: ("Мортира", G, {1: (5_000, 30, 3), 2: (25_000, H(1), 4), 3: (90_000, H(2), 5), 4: (180_000, H(3), 6),
                             5: (300_000, H(6), 7), 6: (500_000, H(8), 8)}),
    1000012: ("ПВО", G, {1: (22_000, H(1), 4), 2: (90_000, H(2), 4), 3: (210_000, H(6), 5), 4: (500_000, H(12), 6),
                         5: (800_000, H(18), 7), 6: (1_000_000, H(24), 8)}),
    1000011: ("Башня колдуна", G, {1: (100_000, H(1), 5), 2: (150_000, H(1, 30), 5), 3: (250_000, H(4), 6),
                                   4: (400_000, H(8), 7), 5: (550_000, H(10), 8), 6: (660_000, H(12), 8)}),
    1000028: ("Воздушная метла", G, {1: (200_000, H(4), 6), 2: (300_000, H(6), 6), 3: (450_000, H(8), 7),
                                     4: (800_000, H(12), 8)}),
    1000019: ("Потайная тесла", G, {1: (250_000, H(2), 7), 2: (350_000, H(3), 7), 3: (500_000, H(4), 7)}),
    1000023: ("Скважина тёмного эликсира", E, {1: (180_000, H(4), 7), 2: (270_000, H(6), 7), 3: (540_000, H(12), 7)}),
    1000024: ("Хранилище тёмного эликсира", E, {1: (250_000, H(8), 7), 2: (500_000, H(16), 7)}),
    1000026: ("Тёмная казарма", E, {1: (200_000, H(8), 7), 2: (600_000, H(24), 7)}),
    12000000: ("Бомба", G, {1: (400, 0, 3), 2: (1_000, 1, 3), 3: (10_000, 5, 5), 4: (40_000, 40, 7), 5: (100_000, H(1), 8)}),
    12000001: ("Пружинная ловушка", G, {1: (2_000, 0, 4), 2: (130_000, H(1), 7), 3: (240_000, H(2), 8)}),
    12000005: ("Воздушная бомба", G, {1: (4_000, 0, 5), 2: (20_000, 30, 5), 3: (75_000, H(1), 7)}),
    12000002: ("Гигантская бомба", G, {1: (12_500, 0, 6), 2: (75_000, H(1), 6), 3: (220_000, H(3), 8)}),
    12000006: ("Мина воздушного поиска", G, {1: (12_000, 0, 7)}),
    # герои: улучшение занимает строителя, платится тёмным эликсиром
    28000000: ("Король варваров", D, {2: (5_000, H(2), 7), 3: (5_500, H(4), 7), 4: (6_000, H(8), 7), 5: (6_500, H(10), 7),
                                      6: (7_000, H(12), 7), 7: (7_500, H(14), 7), 8: (8_000, H(16), 7),
                                      9: (8_500, H(18), 7), 10: (10_000, H(20), 7), 11: (10_500, H(22), 8)}),
}
MINE = {1: (150, 1, 1), 2: (300, 1, 1), 3: (700, 1, 2), 4: (1_400, 2, 2), 5: (3_000, 5, 3), 6: (7_000, 15, 3),
        7: (14_000, 30, 4), 8: (28_000, H(1), 4), 9: (56_000, H(1, 30), 5), 10: (75_000, H(2), 5), 11: (85_000, H(3), 7),
        12: (170_000, H(4), 8)}
BUILD[1000004][2].update(MINE)
BUILD[1000002][2].update(MINE)

COUNT = {  # сколько штук доступно на ратуше
    5: {1000000: 3, 1000006: 1, 1000007: 1, 1000020: 1, 1000014: 1, 1000005: 2, 1000003: 2, 1000004: 5, 1000002: 5,
        1000008: 3, 1000009: 3, 1000013: 1, 1000012: 1, 1000011: 1, 12000000: 4, 12000001: 2, 12000005: 2},
    6: {1000000: 3, 1000006: 1, 1000007: 1, 1000020: 1, 1000014: 1, 1000005: 2, 1000003: 2, 1000004: 6, 1000002: 6,
        1000008: 3, 1000009: 3, 1000013: 2, 1000012: 2, 1000011: 2, 1000028: 1,
        12000000: 4, 12000001: 4, 12000005: 2, 12000002: 1},
    7: {1000000: 4, 1000006: 1, 1000007: 1, 1000020: 1, 1000014: 1, 1000005: 2, 1000003: 2, 1000004: 6, 1000002: 6,
        1000008: 5, 1000009: 4, 1000013: 3, 1000012: 3, 1000011: 2, 1000028: 1, 1000019: 2,
        1000023: 1, 1000024: 1, 1000026: 1,
        12000000: 6, 12000001: 4, 12000005: 2, 12000002: 2, 12000006: 1},
}
WALLS = {5: 100, 6: 125, 7: 175}
WALL_COST = {1: 0, 2: 1_000, 3: 5_000, 4: 10_000, 5: 20_000, 6: 30_000, 7: 50_000}  # с 5 ур. — золото или эликсир
WALL_MAX = {5: 5, 6: 6, 7: 7}
TH_UP = {6: (500_000, H(12)), 7: (1_000_000, H(18)), 8: (2_000_000, H(24))}

# id: (название, {уровень: (эликсир, минуты, уровень лабы)}, (id здания, уровень) для открытия)
LAB = {
    4000000: ("Варвар", {2: (10_000, 30, 1), 3: (50_000, H(1), 3), 4: (130_000, H(2), 5)}, None),
    4000001: ("Лучница", {2: (20_000, H(1), 1), 3: (80_000, H(2), 3), 4: (200_000, H(3), 5)}, None),
    4000002: ("Гоблин", {2: (45_000, H(2), 1), 3: (100_000, H(3), 3), 4: (500_000, H(6), 5)}, None),
    4000003: ("Гигант", {2: (40_000, H(2), 2), 3: (150_000, H(4), 4), 4: (400_000, H(6), 5)}, None),
    4000004: ("Стенобой", {2: (80_000, H(3), 2), 3: (200_000, H(4), 4), 4: (450_000, H(12), 5)}, None),
    4000005: ("Шар", {2: (100_000, H(4), 2), 3: (400_000, H(6), 4), 4: (720_000, H(18), 5)}, None),
    4000006: ("Колдун", {2: (120_000, H(4), 3), 3: (300_000, H(5), 4), 4: (600_000, H(12), 5)}, (1000006, 7)),
    4000007: ("Целительница", {2: (450_000, H(12), 5)}, (1000006, 8)),
    26000000: ("Молния", {2: (50_000, H(2), 1), 3: (100_000, H(4), 2), 4: (200_000, H(6), 3), 5: (600_000, H(24), 6)},
               (1000020, 1)),
    26000001: ("Лечение", {2: (75_000, H(3), 2), 3: (150_000, H(6), 4), 4: (300_000, H(12), 5)}, (1000020, 2)),
    26000002: ("Ярость", {2: (400_000, H(6), 3), 3: (800_000, H(12), 4), 4: (1_000_000, H(24), 5)}, (1000020, 3)),
    4000008: ("Дракон", {2: (1_000_000, H(18), 5)}, (1000006, 9)),
    4000010: ("Миньон", {2: (1_000, H(6), 5)}, (1000026, 1)),
    4000011: ("Всадник на кабане", {2: (2_000, H(10), 5)}, (1000026, 2)),
}
LAB_RES = {4000010: D, 4000011: D}  # остальное — за эликсир

# ---------- разбор экспорта ----------
exp = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "export.json", encoding="utf-8-sig"))
START = datetime.fromtimestamp(exp["timestamp"], TZ).replace(tzinfo=None, second=0)
TH = next(b["lvl"] for b in exp["buildings"] if b["data"] == 1000001)
if TH not in COUNT:
    sys.exit(f"Ратуша {TH} не поддерживается (есть данные для {sorted(COUNT)})")
NEXT_TH = f"Ратуша → {TH + 1}"

busy, tasks, instant = [], [], []
final_level = {}   # (id здания) -> уровень первого экземпляра после всех улучшений / сейчас
level_task = {}    # (id, уровень) -> id задачи, после которой первый экземпляр достигнет уровня
cur_level = {}


def add_chain(bid, inst, lvl, prev, first):
    name, res, ups = BUILD[bid]
    for target in sorted(ups):
        cost, dur, th_req = ups[target]
        if target <= lvl or th_req > TH:
            continue
        tid = f"{inst} → {target}"
        if dur == 0:
            instant.append(dict(name=label(tid), res=res, cost=cost))
            continue
        tasks.append(dict(id=tid, dur=dur, res=res, cost=cost, dep=prev))
        if first:
            level_task[(bid, target)] = tid
        prev = tid


def label(tid):
    return tid[:-4] + " (постройка)" if tid.endswith(" → 1") else tid


seen = {}
for b in exp["buildings"] + exp["traps"] + exp.get("heroes", []):
    bid = b["data"]
    if bid not in BUILD:
        continue
    need = COUNT[TH].get(bid, 0)
    for _ in range(b.get("cnt", 1)):
        k = seen[bid] = seen.get(bid, 0) + 1
        inst = f"{BUILD[bid][0]} #{k}" if need > 1 else BUILD[bid][0]
        lvl, prev = b["lvl"], None
        if k == 1:
            cur_level[bid] = lvl
        if "timer" in b:
            prev = f"{inst} → {lvl + 1}"
            busy.append((prev, b["timer"] // 60))
            if k == 1:
                level_task[(bid, lvl + 1)] = prev
            lvl += 1
        add_chain(bid, inst, lvl, prev, k == 1)
for bid, need in COUNT[TH].items():
    for k in range(seen.get(bid, 0) + 1, need + 1):
        inst = f"{BUILD[bid][0]} #{k}" if need > 1 else BUILD[bid][0]
        if k == 1:
            cur_level[bid] = 0
        add_chain(bid, inst, 0, None, k == 1)
if TH + 1 in TH_UP:
    cost, dur = TH_UP[TH + 1]
    tasks.append(dict(id=NEXT_TH, dur=dur, res=G, cost=cost, dep=None))


def ready_dep(bid, level):
    """Задача, после которой здание bid будет уровня level (None — уже есть)."""
    if cur_level.get(bid, 0) >= level:
        return None
    return level_task.get((bid, level), "НЕДОСТИЖИМО")


# стены
walls = {}
for b in exp["buildings"]:
    if b["data"] == 1000010:
        walls[b["lvl"]] = walls.get(b["lvl"], 0) + b.get("cnt", 1)
walls[0] = WALLS[TH] - sum(walls.values())
wall_gold = wall_any = 0
for lvl, n in walls.items():
    for t in range(lvl + 1, WALL_MAX[TH] + 1):
        if t <= 4:
            wall_gold += WALL_COST[t] * n
        else:
            wall_any += WALL_COST[t] * n

# исследования
lab_max = max([lv for lv, (_, _, th) in BUILD[1000007][2].items() if th <= TH] + [cur_level.get(1000007, 1)])
units = {u["data"]: u for u in exp.get("units", []) + exp.get("spells", [])}
lab_busy_until, research = START, []
for uid, (name, ups, unlock) in LAB.items():
    lvl = units[uid]["lvl"] if uid in units else 1
    prev = None
    if uid in units and "timer" in units[uid]:
        prev = f"{name} → {lvl + 1}"
        lab_busy_until = START + timedelta(minutes=units[uid]["timer"] // 60)
        busy_research = (prev, units[uid]["timer"] // 60)
        lvl += 1
    for target in sorted(ups):
        cost, dur, need_lab = ups[target]
        if target <= lvl or need_lab > lab_max:
            continue
        deps = [d for d in (prev, ready_dep(1000007, need_lab), unlock and ready_dep(*unlock)) if d]
        if "НЕДОСТИЖИМО" in deps:
            continue
        tid = f"{name} → {target}"
        research.append(dict(id=tid, dur=dur, cost=cost, deps=deps, res=LAB_RES.get(uid, E)))
        prev = tid
lab_running = [busy_research] if lab_busy_until > START else []


# ---------- время бодрствования ----------
def awake(t):
    m = t.hour * 60 + t.minute
    return m >= WAKE_MIN or m <= BED_MIN

def next_wake(t):
    return t if awake(t) else t.replace(hour=WAKE_MIN // 60, minute=WAKE_MIN % 60)

def bedtime(t):
    b = t.replace(hour=BED_MIN // 60, minute=BED_MIN % 60)
    return b if b >= t else b + timedelta(days=1)


# ---------- строители ----------
succ = {t["dep"]: t["id"] for t in tasks if t["dep"]}
by_id = {t["id"]: t for t in tasks}
FORCE = {d for r in research for d in r["deps"] if d in by_id}  # то, что открывает исследования


def chain_len(tid):
    n = 0
    while tid in by_id:
        n += by_id[tid]["dur"]
        tid = succ.get(tid)
    return n


def simulate_builders(reserve, th_after, key):
    done, sched, builders = {}, [], []
    for name, m in busy:
        end = START + timedelta(minutes=m)
        done[name] = end
        builders.append(end)
        sched.append(dict(kind="стройка", who=len(builders), name=label(name), start=START, end=end, res="-", cost=0))
    builders += [START] * (5 - len(builders))
    pending = dict(by_id)

    def ready(t, now):
        return t["dep"] is None or (t["dep"] in done and done[t["dep"]] <= now)

    def pick(now):
        avail = [t for t in pending.values() if ready(t, now)]
        others = [t for t in avail if t["id"] != NEXT_TH]
        forced = [t for t in others if t["id"] in FORCE]
        if forced:
            return max(forced, key=lambda t: t["dur"])
        left = bedtime(now) - now
        fits = [t for t in others if timedelta(minutes=t["dur"]) <= left]
        short = [t for t in fits if reserve is None or t["dur"] < reserve]
        if short or fits:
            pool = short or fits
            return max(pool, key=lambda t: chain_len(t["id"]) if key == "chain" else t["dur"])
        pool = list(others)
        if NEXT_TH in pending and (len(pending) - 1 <= th_after or not pool):
            pool.append(pending[NEXT_TH])
        return max(pool, key=lambda t: t["dur"]) if pool else None

    while pending:
        i = min(range(5), key=lambda k: builders[k])
        now = next_wake(builders[i])
        t = pick(now)
        if t is None:
            future = sorted(e for e in done.values() if e > now)
            builders[i] = future[0] if future else now + timedelta(minutes=5)
            continue
        end = now + timedelta(minutes=t["dur"])
        del pending[t["id"]]
        done[t["id"]] = end
        builders[i] = end
        sched.append(dict(kind="стройка", who=i + 1, name=label(t["id"]), start=now, end=end, res=t["res"], cost=t["cost"]))
    return done, sched


# ---------- лаборатория: перебор приоритетов + «длинное на ночь» ----------
def simulate_lab(done, prio):
    rank = {r["id"]: i for i, r in enumerate(prio)}
    fin = {n: START + timedelta(minutes=m) for n, m in lab_running}
    sched = [dict(kind="лаборатория", who=0, name=n, start=START, end=e, res="-", cost=0) for n, e in fin.items()]
    t, left = lab_busy_until, list(research)
    research_ids = {r["id"] for r in research}
    far = START + timedelta(days=3650)
    # исследование, которое ещё не запланировано, не считается сделанным
    when = lambda d: fin.get(d) or done.get(d) or (far if d in research_ids else START)
    while left:
        now = next_wake(t)
        avail = [r for r in left if all(when(d) <= now for d in r["deps"])]
        if not avail:
            t = max(t, min(max(when(d) for d in r["deps"]) for r in left))
            if not awake(t) or t == now:
                t = max(t, now) + timedelta(minutes=1) if t <= now else t
            continue
        room = bedtime(now) - now
        fits = [r for r in avail if timedelta(minutes=r["dur"]) <= room]
        r = min(fits, key=lambda r: rank[r["id"]]) if fits else max(avail, key=lambda r: r["dur"])
        e = now + timedelta(minutes=r["dur"])
        fin[r["id"]] = e
        t = e
        left.remove(r)
        sched.append(dict(kind="лаборатория", who=0, name=r["id"], start=now, end=e, res=r["res"], cost=r["cost"]))
    return sched


random.seed(1)
prios = [sorted(research, key=lambda r: -r["dur"]), sorted(research, key=lambda r: r["dur"])]
prios += [random.sample(research, len(research)) for _ in range(300)]

best = None
for reserve in (None, H(6), H(12)):
    for th_after in (0, 3, 6, 10, 20, 40, 99):
        for key in ("chain", "dur"):
            done, s = simulate_builders(reserve, th_after, key)
            b_end = max(x["end"] for x in s)
            lab_best = min((simulate_lab(done, p) for p in prios),
                           key=lambda ls: max([x["end"] for x in ls] or [START]))
            finish = max([b_end] + [x["end"] for x in lab_best])
            if best is None or (finish, b_end) < best[0]:
                best = ((finish, b_end), s + lab_best)
schedule = sorted(best[1], key=lambda x: (x["start"], x["who"]))

# ---------- вывод ----------
fmt = lambda d: d.strftime("%d.%m %H:%M")
for x in schedule:
    w = "Лаб" if x["kind"] == "лаборатория" else f"С{x['who']}"
    print(f"{fmt(x['start'])} → {fmt(x['end'])}  {w:4} {x['name']:38} {x['cost']:>10,} {x['res']}")
END = max(x["end"] for x in schedule)
gold = sum(x["cost"] for x in schedule if x["res"] == G) + sum(i["cost"] for i in instant if i["res"] == G)
elix = sum(x["cost"] for x in schedule if x["res"] == E) + sum(i["cost"] for i in instant if i["res"] == E)
dark = sum(x["cost"] for x in schedule if x["res"] == D)
print(f"\nРатуша {TH}. Экспорт: {fmt(START)}   Всё готово: {fmt(END)}")
print(f"Золото: {gold:,}  Эликсир: {elix:,}  Тёмный: {dark:,}  Стены: {wall_gold:,} золота + {wall_any:,} золота/эликсира")
print("Без строителя:", "; ".join(f"{i['name']} ({i['cost']:,})" for i in instant))

base = f"plan_th{TH}"
json.dump([dict(x, start=x["start"].isoformat(), end=x["end"].isoformat()) for x in schedule],
          open(base + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------- HTML ----------
num = lambda n: f"{n:,}".replace(",", " ")
t0 = START.replace(minute=0)
total = int((END - t0).total_seconds() // 60) + 60
key_of = lambda x: x["name"] + "|" + x["start"].isoformat()
bars = [[5 if x["kind"] == "лаборатория" else x["who"] - 1, int((x["start"] - t0).total_seconds() // 60),
         int((x["end"] - x["start"]).total_seconds() // 60), x["name"], {G: "g", E: "e", D: "d"}.get(x["res"], "c"),
         x["cost"], key_of(x)] for x in schedule]
nights, d = [], t0.replace(hour=0, minute=0) - timedelta(days=1)
while d < END + timedelta(days=1):
    a, b = max(d + timedelta(minutes=BED_MIN), t0), min(d + timedelta(minutes=WAKE_MIN), t0 + timedelta(minutes=total))
    if a < b:
        nights.append([int((a - t0).total_seconds() // 60), int((b - t0).total_seconds() // 60)])
    d += timedelta(days=1)

groups = {}
for x in schedule:
    if x["res"] != "-":
        groups.setdefault(x["start"], []).append(x)
task_div = lambda k, body: f"<div class='task' data-k='{html.escape(k, quote=True)}'><span class='box'></span>{body}</div>"
rows_html = "".join(
    f"<tr><td class='tm'>{fmt(s)}</td><td>" + "".join(
        task_div(key_of(x), f"{'🧪 ' if x['kind'] == 'лаборатория' else ''}{html.escape(x['name'])} "
                            f"<span class='mu'>· {num(x['cost'])} {x['res']} · до {fmt(x['end'])}</span>")
        for x in items) + "</td></tr>"
    for s, items in sorted(groups.items()))
extra = [task_div("instant|" + i["name"], f"{html.escape(i['name'])} <span class='mu'>· {num(i['cost'])} {i['res']} · мгновенно</span>")
         for i in instant]
wall_lines = ", ".join(f"{n} шт. {lv} ур." if lv else f"{n} новых" for lv, n in sorted(walls.items()) if n and lv < WALL_MAX[TH])
if wall_lines:
    extra.append(task_div("walls", f"Стены до {WALL_MAX[TH]} ур. ({wall_lines}) <span class='mu'>· {num(wall_gold)} только золотом + "
                                   f"{num(wall_any)} золотом или эликсиром</span>"))
extra_html = "<h2>Без строителя — в любое время</h2><table><tr><td>" + "".join(extra) + "</td></tr></table>" if extra else ""
th_end = next((x["end"] for x in schedule if x["name"] == NEXT_TH), None)
dark_kpi = f"<div><span>Тёмный эликсир</span><b>{num(dark)}</b></div>" if dark else ""
walls_kpi = f"<div><span>Стены</span><b>{num(wall_gold + wall_any)}</b></div>" if wall_gold + wall_any else ""

page = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>План ТХ{TH} → ТХ{TH + 1}</title>
<style>
:root{{--bg:#fbfaf7;--card:#f1efe8;--ink:#1d1d1b;--mu:#6b6a64;--line:#e1e0d9;--night:rgba(0,0,0,.07);--gold:#eda100;--goldt:#412402;--el:#e87ba4;--elt:#4b1528;--de:#534ab7;--det:#eeedfe;--cur:#85b7eb;--curt:#0c447c;--done:#b4b2a9;--donet:#2c2c2a}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1a1a19;--card:#262624;--ink:#f0efec;--mu:#a8a79f;--line:#33332f;--night:rgba(255,255,255,.06)}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,system-ui,Segoe UI,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px 48px}}h1{{font-size:22px;font-weight:600;margin:0 0 4px}}
.sub{{color:var(--mu);margin:0 0 20px}}.kpi{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:20px}}
.kpi div{{background:var(--card);border-radius:10px;padding:10px 14px}}.kpi b{{display:block;font-size:20px;font-weight:600}}.kpi span{{color:var(--mu);font-size:13px}}
.leg{{display:flex;flex-wrap:wrap;gap:14px;font-size:13px;color:var(--mu);margin-bottom:8px}}.leg i{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}}
.wrap{{overflow-x:auto;padding-bottom:6px}}.gantt{{min-width:{max(900, total // 3)}px}}
.row{{display:flex;align-items:center;height:32px;margin-bottom:4px}}.rl{{width:56px;flex:none;font-size:12px;color:var(--mu);position:sticky;left:0;background:var(--bg);z-index:2}}
.tr{{position:relative;flex:1;height:100%;background:var(--card);border-radius:5px;overflow:hidden}}
.bar{{position:absolute;top:3px;bottom:3px;border-radius:3px;font-size:11px;line-height:26px;padding:0 4px;white-space:nowrap;overflow:hidden;border-right:2px solid var(--bg);cursor:pointer}}
.bar.done{{background:var(--done)!important;color:var(--donet)!important;text-decoration:line-through}}
.n{{position:absolute;top:0;bottom:0;background:var(--night)}}.ax{{position:relative;height:20px;margin-left:56px;font-size:11px;color:var(--mu)}}
.ax span{{position:absolute;transform:translateX(-50%);white-space:nowrap}}#info{{min-height:22px;color:var(--mu);font-size:14px;margin:8px 0 24px}}
table{{width:100%;border-collapse:collapse;margin-bottom:24px}}td{{padding:8px 6px;border-top:1px solid var(--line);vertical-align:top}}.tm{{white-space:nowrap;font-variant-numeric:tabular-nums;width:1%;font-weight:600}}.mu{{color:var(--mu);font-size:13px}}
h2{{font-size:18px;font-weight:600;margin:8px 0}}
.task{{cursor:pointer;padding:3px 0;user-select:none}}.task .box{{display:inline-block;width:14px;height:14px;border:1.5px solid var(--mu);border-radius:3px;margin-right:8px;vertical-align:-2px}}
.task.done{{color:var(--mu);text-decoration:line-through}}.task.done .box{{background:var(--done);border-color:var(--done)}}
.top{{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}}
button{{font:inherit;font-size:13px;background:transparent;color:var(--mu);border:1px solid var(--line);border-radius:8px;padding:5px 12px;cursor:pointer}}
</style></head><body><main>
<h1>План: ратуша {TH} на максимум → ратуша {TH + 1}</h1>
<p class="sub">{html.escape(exp.get("tag", ""))} · по экспорту от {fmt(START)} · сон 00:30–08:00 · ресурсы считаются доступными</p>
<div class="kpi"><div><span>Всё готово</span><b>{fmt(END)}</b></div>
<div><span>Ратуша {TH + 1}</span><b>{fmt(th_end) if th_end else "—"}</b></div>
<div><span>Золото</span><b>{num(gold)}</b></div><div><span>Эликсир</span><b>{num(elix)}</b></div>{dark_kpi}
{walls_kpi}</div>
<div class="leg"><span><i style="background:var(--gold)"></i>за золото</span><span><i style="background:var(--el)"></i>за эликсир</span><span><i style="background:var(--de)"></i>за тёмный эликсир</span><span><i style="background:var(--cur)"></i>уже идут</span><span><i style="background:var(--done)"></i>поставил в работу</span><span><i style="background:var(--night);outline:1px solid var(--line)"></i>сон</span></div>
<div class="wrap"><div class="gantt" id="g"></div></div>
<div id="info">Нажми на полоску или на строку в списке, чтобы отметить «поставил в работу». Повторное нажатие снимает отметку.</div>
<div class="top"><h2>Что и когда запускать</h2><span><span id="cnt" class="mu"></span> <button id="reset">Сбросить отметки</button></span></div>
<table>{rows_html}</table>
{extra_html}
</main>
<script>
const D={json.dumps(bars, ensure_ascii=False)},N={json.dumps(nights)},T={total},t0=new Date({t0.year},{t0.month - 1},{t0.day},{t0.hour},0);
const C={{g:["var(--gold)","var(--goldt)"],e:["var(--el)","var(--elt)"],d:["var(--de)","var(--det)"],c:["var(--cur)","var(--curt)"]}};
const f=m=>{{const d=new Date(t0.getTime()+m*6e4);return String(d.getDate()).padStart(2,"0")+"."+String(d.getMonth()+1).padStart(2,"0")+" "+String(d.getHours()).padStart(2,"0")+":"+String(d.getMinutes()).padStart(2,"0")}};
const g=document.getElementById("g"),info=document.getElementById("info");
["Стр. 1","Стр. 2","Стр. 3","Стр. 4","Стр. 5","Лаб."].forEach((nm,r)=>{{const row=document.createElement("div");row.className="row";row.innerHTML='<div class="rl">'+nm+'</div>';const tr=document.createElement("div");tr.className="tr";
N.forEach(([a,b])=>{{const n=document.createElement("div");n.className="n";n.style.left=a/T*100+"%";n.style.width=(b-a)/T*100+"%";tr.appendChild(n)}});
D.filter(x=>x[0]===r).forEach(([_,s,d,n,k,c,key])=>{{const b=document.createElement("div");b.className="bar";b.dataset.k=key;b.style.left=s/T*100+"%";b.style.width=d/T*100+"%";b.style.background=C[k][0];b.style.color=C[k][1];if(d/T*{max(900, total // 3)}>=90)b.textContent=n;
const show=()=>{{info.textContent=n+" — "+f(s)+" → "+f(s+d)+(c?" · "+c.toLocaleString("ru")+({{g:" золота",e:" эликсира",d:" тёмного эликсира"}}[k]):"")}};b.onmouseenter=show;if(k!=="c")b.onclick=()=>{{show();toggle(key)}};tr.appendChild(b)}});
row.appendChild(tr);g.appendChild(row)}});
const ax=document.createElement("div");ax.className="ax";for(let m=60;m<T;m+=240){{const s=document.createElement("span");s.style.left=m/T*100+"%";s.textContent=f(m);ax.appendChild(s)}}g.appendChild(ax);
const SK="coc-plan-done-{html.escape(exp.get("tag", ""))}-{exp["timestamp"]}";
let done={{}};try{{done=JSON.parse(localStorage.getItem(SK))||{{}}}}catch(e){{}}
const total=document.querySelectorAll(".task").length;
function paint(){{document.querySelectorAll("[data-k]").forEach(el=>el.classList.toggle("done",!!done[el.dataset.k]));
document.getElementById("cnt").textContent="Отмечено: "+document.querySelectorAll(".task.done").length+" из "+total}}
function toggle(key){{if(done[key])delete done[key];else done[key]=1;try{{localStorage.setItem(SK,JSON.stringify(done))}}catch(e){{}}paint()}}
document.querySelectorAll(".task").forEach(el=>el.onclick=()=>toggle(el.dataset.k));
document.getElementById("reset").onclick=()=>{{if(confirm("Снять все отметки?")){{done={{}};try{{localStorage.removeItem(SK)}}catch(e){{}}paint()}}}};
paint();
</script></body></html>"""
open(base + ".html", "w", encoding="utf-8").write(page)
print(f"Сохранено: {base}.json, {base}.html")


