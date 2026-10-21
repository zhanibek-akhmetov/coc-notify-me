"""Текущая война, журнал войн и ЛВК для одного или нескольких кланов.

Запуск: python coc_war.py #ТЕГ1 #ТЕГ2 ...   (ключ в переменной COC_API_KEY)
Результаты каждого клана сохраняются в папку clans/<ТЕГ>/.
"""
import json, os, sys, urllib.request, urllib.parse, urllib.error


def _key_from_file():
    """Ключ из coc_api_key.txt рядом со скриптом (файл не попадает в git)."""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "coc_api_key.txt")
    try:
        return open(p, encoding="utf-8").read().strip() or None
    except OSError:
        return None

API_KEY = (os.environ.get("COC_API_KEY") or _key_from_file())
BASE = "https://api.clashofclans.com/v1"

def get(path):
    req = urllib.request.Request(BASE + path, headers={"Authorization": f"Bearer {API_KEY}"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        print(f"  Ошибка {e.code} на {path}: {e.read().decode()}")
        return None

def save(folder, name, data):
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  -> сохранено в {path}")

def check_clan(clan_tag):
    tag = urllib.parse.quote(clan_tag)
    folder = os.path.join("clans", clan_tag.lstrip("#"))
    os.makedirs(folder, exist_ok=True)

    info = get(f"/clans/{tag}")
    if not info:
        return
    save(folder, "clan.json", info)
    print(f"  {info['name']} | уровень {info['clanLevel']} | участников {info['members']} | "
          f"журнал {'открыт' if info.get('isWarLogPublic') else 'закрыт'} | "
          f"побед {info.get('warWins')} / пораж. {info.get('warLosses')} / ничьих {info.get('warTies')} | "
          f"серия {info.get('warWinStreak')} | лига ЛВК {info.get('warLeague', {}).get('name')}")

    print("  --- Текущая война ---")
    war = get(f"/clans/{tag}/currentwar")
    if war:
        save(folder, "currentwar.json", war)
        print("  state:", war.get("state"))
        if war.get("state") != "notInWar":
            c, o = war["clan"], war["opponent"]
            print(f"  {c['name']} {c['stars']}★ {c['destructionPercentage']:.1f}%  vs  "
                  f"{o['name']} {o['stars']}★ {o['destructionPercentage']:.1f}%")

    print("  --- Журнал войн (последние 10) ---")
    log = get(f"/clans/{tag}/warlog?limit=10")
    if log:
        save(folder, "warlog.json", log)
        for w in log["items"]:
            print(f"  {w['endTime'][:8]}  {w.get('result') or '-':5} {w['clan']['stars']}★ vs "
                  f"{w['opponent'].get('name') or '(ЛВК)'} {w['opponent']['stars']}★")

    print("  --- ЛВК ---")
    group = get(f"/clans/{tag}/currentwar/leaguegroup")
    if group:
        save(folder, "cwl_group.json", group)
        for i, rnd in enumerate(group["rounds"], 1):
            for wt in rnd["warTags"]:
                if wt == "#0":
                    continue
                w = get(f"/clanwarleagues/wars/{urllib.parse.quote(wt)}")
                if w and clan_tag in (w["clan"]["tag"], w["opponent"]["tag"]):
                    save(folder, f"cwl_round{i}.json", w)

if not API_KEY:
    sys.exit("Положи ключ в coc_api_key.txt рядом со скриптом или задай COC_API_KEY")
if len(sys.argv) < 2:
    sys.exit("Укажи теги: python coc_war.py #ТЕГ1 #ТЕГ2 ...")

for t in sys.argv[1:]:
    t = t if t.startswith("#") else "#" + t
    print(f"\n========== {t} ==========")
    check_clan(t.upper())
