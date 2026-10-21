"""Тест планировщика: строит план по примеру экспорта и проверяет расписание по таблицам из coc_plan.py.

Проверки: нет наложений у строителей и лаборатории, ничего не стартует ночью, длительности как в вики,
уровни по порядку, исследования после нужной лабы и открывающего здания, всё до максимума ратуши.
Плюс: валидатор действительно ловит поломки, а пример в репозитории совпадает с тем, что генерирует код.

Запуск: python tests/test_planner.py
"""
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANNER = os.path.join(REPO, "planner", "coc_plan.py")
EXAMPLES = os.path.join(REPO, "planner", "examples")

# таблицы берём прямо из coc_plan.py (всё до разбора экспорта)
_ns = {}
exec(open(PLANNER, encoding="utf-8-sig").read().split("# ---------- разбор экспорта ----------")[0], _ns)
BUILD, COUNT, LAB, TH_UP = _ns["BUILD"], _ns["COUNT"], _ns["LAB"], _ns["TH_UP"]
WAKE, BED = _ns["WAKE_MIN"], _ns["BED_MIN"]
NAME_TO_BID = {v[0]: k for k, v in BUILD.items()}
ITEM = re.compile(r"^(.*?)(?: #\d+)?(?: → (\d+)| \(постройка\))$")


def validate(exp, plan):
    """Список нарушений (пустой — всё верно)."""
    errors = []
    for x in plan:
        x["s"], x["e"] = datetime.fromisoformat(x["start"]), datetime.fromisoformat(x["end"])
    start = min(x["s"] for x in plan)
    th = next(b["lvl"] for b in exp["buildings"] if b["data"] == 1000001)
    by_name = {x["name"]: x for x in plan}

    lanes = {}
    for x in plan:
        lanes.setdefault((x["kind"], x["who"]), []).append(x)
    for lane, xs in lanes.items():
        xs.sort(key=lambda x: x["s"])
        errors += [f"наложение {lane}: {a['name']} / {b['name']}" for a, b in zip(xs, xs[1:]) if b["s"] < a["e"]]
    if sum(1 for l in lanes if l[0] == "стройка") > 5:
        errors.append("больше 5 строителей")

    for x in plan:
        if x["s"] < start:
            errors.append(f"раньше экспорта: {x['name']}")
        if x["res"] == "-":
            continue  # уже шло на момент экспорта
        if BED < x["s"].hour * 60 + x["s"].minute < WAKE:
            errors.append(f"старт ночью: {x['name']}")
        base, lvl = ITEM.match(x["name"]).group(1), int(ITEM.match(x["name"]).group(2) or 1)
        if x["kind"] == "лаборатория":
            uid = next(k for k, v in LAB.items() if v[0] == base)
            want = LAB[uid][1][lvl][1]
        elif base == "Ратуша":
            want = TH_UP[lvl][1]
        else:
            want = BUILD[NAME_TO_BID[base]][2][lvl][1]
            if BUILD[NAME_TO_BID[base]][2][lvl][2] > th:
                errors.append(f"выше лимита ратуши: {x['name']}")
        if int((x["e"] - x["s"]).total_seconds() // 60) != want:
            errors.append(f"длительность: {x['name']}")
        m = re.match(r"^(.*) → (\d+)$", x["name"])
        if m:
            prev = by_name.get(f"{m.group(1)} → {int(m.group(2)) - 1}")
            if prev and x["s"] < prev["e"]:
                errors.append(f"не по порядку: {x['name']}")

    lab_now = next(b["lvl"] for b in exp["buildings"] if b["data"] == 1000007)
    for x in plan:
        if x["kind"] != "лаборатория" or x["res"] == "-":
            continue
        base, lvl = re.match(r"^(.*) → (\d+)$", x["name"]).groups()
        uid = next(k for k, v in LAB.items() if v[0] == base)
        need = LAB[uid][1][int(lvl)][2]
        if need > lab_now:
            up = by_name.get(f"Лаборатория → {need}")
            if not up or x["s"] < up["e"]:
                errors.append(f"{x['name']}: нужна лаборатория {need}")
        unlock = LAB[uid][2]
        if unlock:
            have = max([b["lvl"] for b in exp["buildings"] if b["data"] == unlock[0]] or [0])
            bname = BUILD[unlock[0]][0]
            up = by_name.get(f"{bname} → {unlock[1]}") or by_name.get(f"{bname} (постройка)")
            if have < unlock[1] and (not up or x["s"] < up["e"]):
                errors.append(f"{x['name']}: раньше, чем {bname} {unlock[1]}")

    levels = {}
    for b in exp["buildings"] + exp["traps"] + exp.get("heroes", []):
        if b["data"] in BUILD:
            levels.setdefault(b["data"], []).extend([b["lvl"]] * b.get("cnt", 1))
    for bid in COUNT[th]:
        name, top = BUILD[bid][0], max([l for l, v in BUILD[bid][2].items() if v[2] <= th] or [0])
        if BUILD[bid][2].get(top, (0, 1))[1] == 0 or min(levels.get(bid, [0]) or [0]) >= top:
            continue
        pat = rf"^{re.escape(name)}(?: #\d+)?(?: → {top}| \(постройка\))$" if top == 1 else \
            rf"^{re.escape(name)}(?: #\d+)? → {top}$"
        if not any(re.match(pat, x["name"]) for x in plan):
            errors.append(f"не доведено до максимума: {name} → {top}")
    if sum(1 for x in plan if x["name"].startswith("Ратуша →")) != 1:
        errors.append("улучшение ратуши должно быть ровно одно")
    return errors


def main():
    failed = []

    def check(cond, what, detail=""):
        print(("  ✔ " if cond else "  ✘ ") + what + (f" — {detail}" if detail and not cond else ""))
        if not cond:
            failed.append(what)

    exports = sorted(f for f in os.listdir(EXAMPLES) if f.startswith("export_") and f.endswith(".json"))
    check(bool(exports), "в planner/examples есть пример экспорта")
    for name in exports:
        print(f"{name}:")
        work = tempfile.mkdtemp()
        shutil.copy(os.path.join(EXAMPLES, name), work)
        r = subprocess.run([sys.executable, PLANNER, name], cwd=work, capture_output=True, text=True,
                           encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        check(r.returncode == 0, "coc_plan.py отработал без ошибок", r.stderr[-500:])
        if r.returncode:
            continue
        exp = json.load(open(os.path.join(work, name), encoding="utf-8-sig"))
        th = next(b["lvl"] for b in exp["buildings"] if b["data"] == 1000001)
        plan_file = os.path.join(work, f"plan_th{th}.json")
        plan = json.load(open(plan_file, encoding="utf-8"))
        errors = validate(exp, copy.deepcopy(plan))
        check(not errors, f"расписание корректно ({len(plan)} записей)", "; ".join(errors[:5]))

        html_text = open(os.path.join(work, f"plan_th{th}.html"), encoding="utf-8").read()
        check(html_text.count("class='task'") > 0 and "const D=" in html_text, "HTML-график сгенерирован")

        committed = os.path.join(EXAMPLES, f"plan_th{th}.json")
        if os.path.exists(committed):
            same = json.load(open(committed, encoding="utf-8")) == plan
            check(same, "пример в репозитории совпадает с тем, что генерирует код",
                  "перегенерируй: cd planner/examples && python ../coc_plan.py " + name)

        # валидатор должен ловить поломки
        broken = copy.deepcopy(plan)
        builds = [x for x in broken if x["kind"] == "стройка" and x["res"] != "-"]
        builds[0]["start"] = builds[0]["start"][:11] + "03:00:00"            # старт ночью
        builds[2].update(who=builds[1]["who"], start=builds[1]["start"], end=builds[1]["end"])  # наложение
        check(len(validate(exp, broken)) >= 2, "валидатор ловит поломанное расписание")

    print("\nИТОГ:", "всё работает ✅" if not failed else f"ОШИБКИ: {failed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
