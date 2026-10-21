"""Выкачивает ПОЛНЫЙ журнал войн (со всеми страницами) и показывает войны за нужный год.

Запуск: python coc_warlog_year.py 2015 #ТЕГ1 #ТЕГ2 ...   (ключ в переменной COC_API_KEY)
Полный журнал сохраняется в clans/<ТЕГ>/warlog_full.json, войны за год — в warlog_<год>.json.
"""
import json, os, sys, urllib.request, urllib.parse, urllib.error

API_KEY = os.environ.get("COC_API_KEY")
if not API_KEY:
    sys.exit("Задай ключ в переменной COC_API_KEY (ключ: developer.clashofclans.com)")
if len(sys.argv) < 3:
    sys.exit('Запуск: python coc_warlog_year.py 2015 "#ТЕГ1" "#ТЕГ2"')
BASE = "https://api.clashofclans.com/v1"


def get(path):
    req = urllib.request.Request(BASE + path, headers={"Authorization": f"Bearer {API_KEY}"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r), 200
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode() or "{}"), e.code


def full_warlog(tag):
    items, after = [], None
    while True:
        path = f"/clans/{urllib.parse.quote(tag)}/warlog?limit=100"
        if after:
            path += "&after=" + after
        data, code = get(path)
        if code != 200:
            return None, code
        items += data["items"]
        after = data.get("paging", {}).get("cursors", {}).get("after")
        if not after:
            return items, 200


year = sys.argv[1]
for t in sys.argv[2:]:
    tag = (t if t.startswith("#") else "#" + t).upper()
    folder = os.path.join("clans", tag.lstrip("#"))
    os.makedirs(folder, exist_ok=True)
    items, code = full_warlog(tag)
    print(f"\n========== {tag} ==========")
    if items is None:
        print(f"  Ошибка {code}")
        continue
    with open(os.path.join(folder, "warlog_full.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    dates = sorted(w["endTime"][:8] for w in items)
    print(f"  Всего войн в журнале: {len(items)}" + (f", с {dates[0]} по {dates[-1]}" if dates else ""))
    picked = [w for w in items if w["endTime"].startswith(year)]
    with open(os.path.join(folder, f"warlog_{year}.json"), "w", encoding="utf-8") as f:
        json.dump(picked, f, ensure_ascii=False, indent=2)
    print(f"  Войн за {year}: {len(picked)}")
    for w in picked:
        c, o = w["clan"], w["opponent"]
        print(f"  {w['endTime'][:8]}  {w.get('result') or '-':5} {w['teamSize']}x{w['teamSize']}  "
              f"{c['stars']}★ (атак {c.get('attacks')}, опыт {c.get('expEarned')}) vs "
              f"{o.get('name') or '(ЛВК)'} {o.get('tag', '')} {o['stars']}★")
