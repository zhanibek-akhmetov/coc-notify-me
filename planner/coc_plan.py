"""План прокачки текущей ратуши до максимума + улучшение до следующей, по экспорту деревни.

Запуск:  python coc_plan.py export.json [--tz 5] [--lang ru|en] [--no-lab] [--no-heroes] [--no-res]
Результат: plan_th<N>.json и plan_th<N>.html (N — текущий уровень ратуши).
Как модуль (так его вызывает бот): make_plan(export, tz_hours, bed, wake) → plan_link(plan, lang).
Поддерживаются ратуши 5–8.

Цены и время — Clash of Clans Wiki (fandom), октябрь 2026.
Симуляция: 5 строителей + лаборатория; ночью (по умолчанию 00:30–08:00) новые улучшения
не запускаются. Ресурсы считаются доступными.
"""
import base64
import json
import os
import random
import sys
import zlib
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
WAKE_MIN, BED_MIN = 8 * 60, 30      # по умолчанию: бодрствование 08:00 – 00:30
DEFAULT_TZ = 5                      # Казахстан
VIEWER_URL = "https://zhanibek-akhmetov.github.io/coc-notify-me/"
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
    1000014: ("Замок клана", G, {2: (50_000, H(2), 4), 3: (600_000, H(12), 6), 4: (1_200_000, H(24), 8),
                                 5: (2_000_000, H(36), 9)}),
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
    1000019: ("Потайная тесла", G, {1: (250_000, H(2), 7), 2: (350_000, H(3), 7), 3: (500_000, H(4), 7),
                                    4: (600_000, H(6), 8), 5: (800_000, H(12), 8), 6: (1_200_000, H(24), 8)}),
    1000023: ("Скважина тёмного эликсира", E, {1: (180_000, H(4), 7), 2: (270_000, H(6), 7), 3: (540_000, H(12), 7)}),
    1000024: ("Хранилище тёмного эликсира", E, {1: (250_000, H(8), 7), 2: (500_000, H(16), 7),
                                                3: (1_000_000, H(24), 8), 4: (1_500_000, H(36), 8)}),
    1000026: ("Тёмная казарма", E, {1: (200_000, H(8), 7), 2: (600_000, H(24), 7), 3: (1_000_000, H(36), 8),
                                    4: (1_600_000, H(48), 8)}),
    1000029: ("Фабрика тёмных заклинаний", E, {1: (130_000, H(6), 8), 2: (260_000, H(12), 8)}),
    1000032: ("Бомбовая башня", G, {1: (700_000, H(12), 8), 2: (1_000_000, H(18), 8)}),
    12000000: ("Бомба", G, {1: (400, 0, 3), 2: (1_000, 1, 3), 3: (10_000, 5, 5), 4: (40_000, 40, 7), 5: (100_000, H(1), 8)}),
    12000001: ("Пружинная ловушка", G, {1: (2_000, 0, 4), 2: (130_000, H(1), 7), 3: (240_000, H(2), 8)}),
    12000005: ("Воздушная бомба", G, {1: (4_000, 0, 5), 2: (20_000, 30, 5), 3: (75_000, H(1), 7)}),
    12000002: ("Гигантская бомба", G, {1: (12_500, 0, 6), 2: (75_000, H(1), 6), 3: (220_000, H(3), 8)}),
    12000006: ("Мина воздушного поиска", G, {1: (12_000, 0, 7)}),
    12000008: ("Скелет в шкафу", G, {1: (6_000, 0, 8), 2: (250_000, H(5), 8)}),
    # герои: улучшение занимает строителя, платится тёмным эликсиром
    28000000: ("Король варваров", D, {2: (5_000, H(2), 7), 3: (5_500, H(4), 7), 4: (6_000, H(8), 7), 5: (6_500, H(10), 7),
                                      6: (7_000, H(12), 7), 7: (7_500, H(14), 7), 8: (8_000, H(16), 7),
                                      9: (8_500, H(18), 7), 10: (10_000, H(20), 7), 11: (10_500, H(22), 8),
                                      12: (11_000, H(24), 8), 13: (11_500, H(24), 8), 14: (12_000, H(24), 8),
                                      15: (12_500, H(24), 8), 16: (13_000, H(24), 8), 17: (13_500, H(24), 8),
                                      18: (14_000, H(24), 8), 19: (14_500, H(24), 8), 20: (15_000, H(24), 8)}),
    28000001: ("Королева лучниц", D, {2: (5_000, H(2), 8), 3: (5_500, H(4), 8), 4: (6_000, H(8), 8), 5: (6_500, H(10), 8),
                                      6: (7_000, H(12), 8), 7: (7_500, H(14), 8), 8: (8_000, H(16), 8),
                                      9: (8_500, H(18), 8), 10: (10_000, H(20), 8)}),
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
    8: {1000000: 4, 1000006: 1, 1000007: 1, 1000020: 1, 1000014: 1, 1000005: 3, 1000003: 3, 1000004: 6, 1000002: 6,
        1000008: 5, 1000009: 5, 1000013: 4, 1000012: 3, 1000011: 3, 1000028: 1, 1000019: 3,
        1000023: 2, 1000024: 1, 1000026: 1, 1000029: 1, 1000032: 1,
        12000000: 6, 12000001: 6, 12000005: 4, 12000002: 3, 12000006: 2, 12000008: 2},
}
WALLS = {5: 100, 6: 125, 7: 175, 8: 225}
WALL_COST = {1: 0, 2: 1_000, 3: 5_000, 4: 10_000, 5: 20_000, 6: 30_000, 7: 50_000, 8: 75_000}  # с 5 ур. — золото или эликсир
WALL_MAX = {5: 5, 6: 6, 7: 7, 8: 8}
TH_UP = {6: (500_000, H(12)), 7: (1_000_000, H(18)), 8: (2_000_000, H(24)), 9: (2_500_000, H(48))}

# id: (название, {уровень: (цена, минуты, уровень лабы)}, (id здания, уровень) для открытия)
LAB = {
    4000000: ("Варвар", {2: (10_000, 30, 1), 3: (50_000, H(1), 3), 4: (130_000, H(2), 5), 5: (300_000, H(4), 6)}, None),
    4000001: ("Лучница", {2: (20_000, H(1), 1), 3: (80_000, H(2), 3), 4: (200_000, H(3), 5), 5: (500_000, H(8), 6)}, None),
    4000002: ("Гоблин", {2: (45_000, H(2), 1), 3: (100_000, H(3), 3), 4: (500_000, H(6), 5), 5: (700_000, H(12), 6)}, None),
    4000003: ("Гигант", {2: (40_000, H(2), 2), 3: (150_000, H(4), 4), 4: (400_000, H(6), 5), 5: (800_000, H(12), 6)}, None),
    4000004: ("Стенобой", {2: (80_000, H(3), 2), 3: (200_000, H(4), 4), 4: (450_000, H(12), 5),
                           5: (1_000_000, H(16), 6)}, None),
    4000005: ("Шар", {2: (100_000, H(4), 2), 3: (400_000, H(6), 4), 4: (720_000, H(18), 5), 5: (1_300_000, H(24), 6)}, None),
    4000006: ("Колдун", {2: (120_000, H(4), 3), 3: (300_000, H(5), 4), 4: (600_000, H(12), 5),
                         5: (1_200_000, H(18), 6)}, (1000006, 7)),
    4000007: ("Целительница", {2: (450_000, H(12), 5), 3: (900_000, H(24), 6)}, (1000006, 8)),
    4000008: ("Дракон", {2: (1_000_000, H(18), 5), 3: (2_000_000, H(36), 6)}, (1000006, 9)),
    4000009: ("П.Е.К.К.А", {2: (600_000, H(12), 6), 3: (1_300_000, H(18), 6)}, (1000006, 10)),
    26000000: ("Молния", {2: (50_000, H(2), 1), 3: (100_000, H(4), 2), 4: (200_000, H(6), 3), 5: (600_000, H(24), 6)},
               (1000020, 1)),
    26000001: ("Лечение", {2: (75_000, H(3), 2), 3: (150_000, H(6), 4), 4: (300_000, H(12), 5),
                           5: (900_000, H(24), 6)}, (1000020, 2)),
    26000002: ("Ярость", {2: (400_000, H(6), 3), 3: (800_000, H(12), 4), 4: (1_000_000, H(24), 5),
                          5: (2_000_000, H(48), 6)}, (1000020, 3)),
    4000010: ("Миньон", {2: (1_000, H(6), 5), 3: (2_500, H(8), 6), 4: (5_000, H(12), 6)}, (1000026, 1)),
    4000011: ("Всадник на кабане", {2: (2_000, H(10), 5), 3: (3_500, H(18), 6), 4: (5_000, H(24), 6)}, (1000026, 2)),
    4000012: ("Валькирия", {2: (3_000, H(8), 6)}, (1000026, 3)),
    4000013: ("Голем", {2: (4_000, H(16), 6)}, (1000026, 4)),
    26000009: ("Яд", {2: (5_000, H(6), 6)}, (1000029, 1)),
    26000010: ("Землетрясение", {2: (6_000, H(12), 6)}, (1000029, 2)),
}
LAB_RES = {4000010: D, 4000011: D, 4000012: D, 4000013: D, 26000009: D, 26000010: D}  # остальное — за эликсир

HEROES = {28000000, 28000001}
RESOURCE_BUILDINGS = {1000002, 1000003, 1000004, 1000005, 1000023, 1000024}  # шахты, сборщики, скважины, хранилища
ALL_PARTS = {"lab": True, "heroes": True, "res": True}

# ---------- разбор экспорта ----------


def make_plan(exp, tz_hours=DEFAULT_TZ, bed_min=BED_MIN, wake_min=WAKE_MIN, parts=None):
    """Расписание по экспорту. Время — в часовом поясе tz_hours, ночь — с bed_min до wake_min (минуты от полуночи).

    parts — что брать в расчёт: {"lab": исследования, "heroes": герои, "res": ресурсные здания}.
    Исключённое не планируется, но то, что уже идёт, по-прежнему занимает строителя / лабораторию.
    """
    parts = dict(ALL_PARTS, **(parts or {}))
    skip = (HEROES if not parts["heroes"] else set()) | (RESOURCE_BUILDINGS if not parts["res"] else set())
    tz = timezone(timedelta(hours=tz_hours))
    start = datetime.fromtimestamp(int(exp["timestamp"]), tz).replace(tzinfo=None, second=0)
    th = next(b["lvl"] for b in exp["buildings"] if b["data"] == 1000001)
    if th not in COUNT:
        raise ValueError(f"ратуша {th} пока не поддерживается (есть данные для {min(COUNT)}–{max(COUNT)})")
    next_th = f"Ратуша → {th + 1}"
    busy, tasks, instant = [], [], []
    level_task, cur_level, meta = {}, {}, {}  # meta: id задачи -> (did, уровень, номер, постройка)

    def label(tid):
        return tid[:-4] + " (постройка)" if tid.endswith(" → 1") else tid

    def add_chain(bid, inst, num, lvl, prev, first):
        name, res, ups = BUILD[bid]
        if bid in skip:
            return  # не в расчёте (уже идущее улучшение при этом остаётся в busy)
        for target in sorted(ups):
            cost, dur, th_req = ups[target]
            if target <= lvl or th_req > th:
                continue
            tid = f"{inst} → {target}"
            meta[tid] = (bid, target, num, target == 1)
            if dur == 0:
                instant.append(dict(name=label(tid), res=res, cost=cost, did=bid, lvl=target))
                continue
            tasks.append(dict(id=tid, dur=dur, res=res, cost=cost, dep=prev))
            if first:
                level_task[(bid, target)] = tid
            prev = tid

    seen = {}
    for b in exp["buildings"] + exp.get("traps", []) + exp.get("heroes", []):
        bid = b["data"]
        if bid not in BUILD:
            continue
        need = COUNT[th].get(bid, 0)
        for _ in range(b.get("cnt", 1)):
            k = seen[bid] = seen.get(bid, 0) + 1
            num = k if need > 1 else 0
            inst = f"{BUILD[bid][0]} #{k}" if need > 1 else BUILD[bid][0]
            lvl, prev = b["lvl"], None
            if k == 1:
                cur_level[bid] = lvl
            if "timer" in b:
                prev = f"{inst} → {lvl + 1}"
                meta[prev] = (bid, lvl + 1, num, lvl == 0)
                busy.append((prev, int(b["timer"]) // 60))
                if k == 1:
                    level_task[(bid, lvl + 1)] = prev
                lvl += 1
            add_chain(bid, inst, num, lvl, prev, k == 1)
    for bid, need in COUNT[th].items():
        for k in range(seen.get(bid, 0) + 1, need + 1):
            num = k if need > 1 else 0
            inst = f"{BUILD[bid][0]} #{k}" if need > 1 else BUILD[bid][0]
            if k == 1:
                cur_level[bid] = 0
            add_chain(bid, inst, num, 0, None, k == 1)
    if th + 1 in TH_UP:
        cost, dur = TH_UP[th + 1]
        tasks.append(dict(id=next_th, dur=dur, res=G, cost=cost, dep=None))
        meta[next_th] = (1000001, th + 1, 0, False)
    if len(busy) > 5:
        raise ValueError("в экспорте больше 5 строек одновременно")

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
    walls[0] = max(0, WALLS[th] - sum(walls.values()))
    wall_gold = wall_any = 0
    for lvl, n in walls.items():
        for t in range(lvl + 1, WALL_MAX[th] + 1):
            if t <= 4:
                wall_gold += WALL_COST[t] * n
            else:
                wall_any += WALL_COST[t] * n

    # исследования
    lab_max = max([lv for lv, (_, _, r) in BUILD[1000007][2].items() if r <= th] + [cur_level.get(1000007, 1)])
    units = {u["data"]: u for u in exp.get("units", []) + exp.get("spells", [])}
    lab_busy_until, research, lab_running = start, [], []
    for uid, (name, ups, unlock) in LAB.items():
        lvl = units[uid]["lvl"] if uid in units else 1
        prev = None
        if uid in units and "timer" in units[uid]:
            prev = f"{name} → {lvl + 1}"
            meta[prev] = (uid, lvl + 1, 0, False)
            lab_busy_until = start + timedelta(minutes=int(units[uid]["timer"]) // 60)
            lab_running = [(prev, int(units[uid]["timer"]) // 60)]
            lvl += 1
        if not parts["lab"]:
            continue  # исследования не в расчёте — показываем только то, что уже идёт
        for target in sorted(ups):
            cost, dur, need_lab = ups[target]
            if target <= lvl or need_lab > lab_max:
                continue
            deps = [d for d in (prev, ready_dep(1000007, need_lab), unlock and ready_dep(*unlock)) if d]
            if "НЕДОСТИЖИМО" in deps:
                continue
            tid = f"{name} → {target}"
            meta[tid] = (uid, target, 0, False)
            research.append(dict(id=tid, dur=dur, cost=cost, deps=deps, res=LAB_RES.get(uid, E)))
            prev = tid

    # ---------- время бодрствования (ночь может переходить через полночь или нет) ----------
    def m_of(t):
        return t.hour * 60 + t.minute

    def awake(t):
        m = m_of(t)
        return not (bed_min <= m < wake_min) if bed_min < wake_min else (wake_min <= m < bed_min)

    def next_at(t, minute):
        x = t.replace(hour=minute // 60, minute=minute % 60)
        return x if x >= t else x + timedelta(days=1)

    def next_wake(t):
        return t if awake(t) else next_at(t, wake_min)

    def bedtime(t):
        return next_at(t, bed_min)

    # ---------- строители ----------
    succ = {t["dep"]: t["id"] for t in tasks if t["dep"]}
    by_id = {t["id"]: t for t in tasks}
    force = {d for r in research for d in r["deps"] if d in by_id}  # то, что открывает исследования

    def chain_len(tid):
        n = 0
        while tid in by_id:
            n += by_id[tid]["dur"]
            tid = succ.get(tid)
        return n

    def simulate_builders(reserve, th_after, key):
        done, sched, builders = {}, [], []
        for name, m in busy:
            end = start + timedelta(minutes=m)
            done[name] = end
            builders.append(end)
            sched.append(dict(kind="стройка", who=len(builders), id=name, start=start, end=end, res="-", cost=0))
        builders += [start] * (5 - len(builders))
        pending = dict(by_id)

        def ready(t, now):
            return t["dep"] is None or (t["dep"] in done and done[t["dep"]] <= now)

        def pick(now):
            avail = [t for t in pending.values() if ready(t, now)]
            others = [t for t in avail if t["id"] != next_th]
            forced = [t for t in others if t["id"] in force]
            if forced:
                return max(forced, key=lambda t: t["dur"])
            left = bedtime(now) - now
            fits = [t for t in others if timedelta(minutes=t["dur"]) <= left]
            short = [t for t in fits if reserve is None or t["dur"] < reserve]
            if short or fits:
                pool = short or fits
                return max(pool, key=lambda t: chain_len(t["id"]) if key == "chain" else t["dur"])
            pool = list(others)
            if next_th in pending and (len(pending) - 1 <= th_after or not pool):
                pool.append(pending[next_th])
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
            sched.append(dict(kind="стройка", who=i + 1, id=t["id"], start=now, end=end, res=t["res"], cost=t["cost"]))
        return done, sched

    # ---------- лаборатория: перебор приоритетов + «длинное на ночь» ----------
    research_ids = {r["id"] for r in research}
    far = start + timedelta(days=3650)

    def simulate_lab(done, prio):
        rank = {r["id"]: i for i, r in enumerate(prio)}
        fin = {n: start + timedelta(minutes=m) for n, m in lab_running}
        sched = [dict(kind="лаборатория", who=0, id=n, start=start, end=e, res="-", cost=0) for n, e in fin.items()]
        t, left = lab_busy_until, list(research)
        # исследование, которое ещё не запланировано, не считается сделанным
        when = lambda d: fin.get(d) or done.get(d) or (far if d in research_ids else start)
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
            sched.append(dict(kind="лаборатория", who=0, id=r["id"], start=now, end=e, res=r["res"], cost=r["cost"]))
        return sched

    rnd = random.Random(1)
    prios = [sorted(research, key=lambda r: -r["dur"]), sorted(research, key=lambda r: r["dur"])]
    prios += [rnd.sample(research, len(research)) for _ in range(300)]

    best = None
    for reserve in (None, H(6), H(12)):
        for th_after in (0, 3, 6, 10, 20, 40, 99):
            for key in ("chain", "dur"):
                done, s = simulate_builders(reserve, th_after, key)
                b_end = max(x["end"] for x in s)
                lab_best = min((simulate_lab(done, p) for p in prios),
                               key=lambda ls: max([x["end"] for x in ls] or [start]))
                finish = max([b_end] + [x["end"] for x in lab_best])
                if best is None or (finish, b_end) < best[0]:
                    best = ((finish, b_end), s + lab_best)
    schedule = sorted(best[1], key=lambda x: (x["start"], x["who"]))
    for x in schedule:
        x["name"] = label(x.pop("id")) if x["kind"] == "стройка" else x.pop("id")
        tid = x["name"].replace(" (постройка)", " → 1")
        x["did"], x["lvl"], x["num"], x["new"] = meta.get(tid, (0, 0, 0, False))

    total = lambda r: sum(x["cost"] for x in schedule if x["res"] == r) + sum(i["cost"] for i in instant if i["res"] == r)
    return dict(tag=exp.get("tag", "?"), th=th, tz=tz_hours, bed=bed_min, wake=wake_min, start=start, parts=parts,
                end=max(x["end"] for x in schedule), schedule=schedule, instant=instant, walls=walls,
                wall_gold=wall_gold, wall_any=wall_any, gold=total(G), elixir=total(E), dark=total(D))


# ---------- вывод: JSON, компактные данные для графика, HTML, ссылка ----------
RES_CODE = {G: "g", E: "e", D: "d"}


def plan_json(plan):
    """Расписание для файла plan_thN.json (его читают make_ics.py и тесты)."""
    return [dict(x, start=x["start"].isoformat(), end=x["end"].isoformat()) for x in plan["schedule"]]


def payload(plan, lang="ru"):
    """Компактные данные для графика: всё, что нужно странице, без названий (их она знает по коду объекта)."""
    t0 = plan["start"]
    mins = lambda d: int((d - t0).total_seconds() // 60)
    items = [[5 if x["kind"] == "лаборатория" else x["who"] - 1, mins(x["start"]), mins(x["end"]) - mins(x["start"]),
              x["did"], x["lvl"], int(x["new"]), x["num"], RES_CODE.get(x["res"], "c"), x["cost"]]
             for x in plan["schedule"]]
    epoch = int((t0 - datetime(1970, 1, 1)).total_seconds() - plan["tz"] * 3600)
    return {"v": 1, "l": lang, "tag": plan["tag"], "th": plan["th"], "t0": epoch, "tz": int(plan["tz"] * 60),
            "bed": plan["bed"], "wake": plan["wake"], "i": items,
            "k": [plan["gold"], plan["elixir"], plan["dark"], plan["wall_gold"], plan["wall_any"]],
            "x": [[i["did"], i["lvl"], RES_CODE.get(i["res"], "g"), i["cost"]] for i in plan["instant"]],
            "w": [[lvl, n] for lvl, n in sorted(plan["walls"].items()) if n], "wm": WALL_MAX[plan["th"]],
            "o": [int(plan["parts"][p]) for p in ("lab", "heroes", "res")]}


def encode(data):
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode().rstrip("=")


def plan_link(plan, lang="ru"):
    """Ссылка на график: данные целиком во фрагменте (#…) — на сервер не уходят и нигде не хранятся."""
    return f"{VIEWER_URL}#p={encode(payload(plan, lang))}"


def render_html(plan, lang="ru"):
    """Самодостаточный HTML: шаблон графика + встроенные данные."""
    tpl = open(os.path.join(HERE, "chart_template.html"), encoding="utf-8").read()
    data = json.dumps(payload(plan, lang), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return tpl.replace("/*EMBEDDED_PLAN*/null", data)


def main():
    args = [a for a in sys.argv[1:]]
    opt = lambda name, default: args[args.index(name) + 1] if name in args else default
    tz_hours = float(opt("--tz", DEFAULT_TZ))
    lang = opt("--lang", "ru")
    path = next((a for a in args if not a.startswith("--") and a not in (opt("--tz", ""), opt("--lang", ""))),
                "export.json")
    exp = json.load(open(path, encoding="utf-8-sig"))
    parts = {"lab": "--no-lab" not in args, "heroes": "--no-heroes" not in args, "res": "--no-res" not in args}
    try:
        plan = make_plan(exp, tz_hours, parts=parts)
    except ValueError as e:
        sys.exit(f"Ошибка: {e}")
    fmt = lambda d: d.strftime("%d.%m %H:%M")
    for x in plan["schedule"]:
        w = "Лаб" if x["kind"] == "лаборатория" else f"С{x['who']}"
        print(f"{fmt(x['start'])} → {fmt(x['end'])}  {w:4} {x['name']:38} {x['cost']:>10,} {x['res']}")
    print(f"\nРатуша {plan['th']}. Экспорт: {fmt(plan['start'])}   Всё готово: {fmt(plan['end'])}")
    print(f"Золото: {plan['gold']:,}  Эликсир: {plan['elixir']:,}  Тёмный: {plan['dark']:,}  "
          f"Стены: {plan['wall_gold']:,} золота + {plan['wall_any']:,} золота/эликсира")
    print("Без строителя:", "; ".join(f"{i['name']} ({i['cost']:,})" for i in plan["instant"]))
    base = f"plan_th{plan['th']}"
    json.dump(plan_json(plan), open(base + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(base + ".html", "w", encoding="utf-8").write(render_html(plan, lang))
    print(f"Сохранено: {base}.json, {base}.html")
    print(f"Ссылка на график ({len(plan_link(plan, lang))} символов): {plan_link(plan, lang)[:80]}…")


if __name__ == "__main__":
    main()
