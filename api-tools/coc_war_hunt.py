"""Ищет полные данные прошлых войн клана через currentwar его бывших противников.

Если противник после войны с нашим кланом больше не воевал, его currentwar
всё ещё показывает ту войну (state = warEnded) со всеми атаками.

Запуск: python coc_war_hunt.py ТВОЙ_API_КЛЮЧ   (или переменная COC_API_KEY)
"""
import json, os, sys, time, urllib.request, urllib.parse, urllib.error

CLAN_TAG = "#8UYGYPL"
API_KEY = os.environ.get("COC_API_KEY") or (sys.argv[1] if len(sys.argv) > 1 else None)
BASE = "https://api.clashofclans.com/v1"
OUT_DIR = "found_wars"


def get(path):
    req = urllib.request.Request(BASE + path, headers={"Authorization": f"Bearer {API_KEY}"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r), 200
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode() or "{}"), e.code


def q(tag):
    return urllib.parse.quote(tag)


if not API_KEY:
    sys.exit("Укажи ключ: python coc_war_hunt.py ТВОЙ_КЛЮЧ  (или переменная COC_API_KEY)")

log, code = get(f"/clans/{q(CLAN_TAG)}/warlog")
if code != 200:
    sys.exit(f"Не удалось получить журнал войн ({code}): {log}")

os.makedirs(OUT_DIR, exist_ok=True)
wars = [w for w in log["items"] if w["opponent"].get("tag")]  # ЛВК без тега пропускаем
print(f"В журнале {len(log['items'])} войн, с тегом противника: {len(wars)}\n")

found = 0
for w in wars:
    opp_tag, opp_name, end = w["opponent"]["tag"], w["opponent"].get("name"), w["endTime"]
    data, code = get(f"/clans/{q(opp_tag)}/currentwar")

    if code == 403:
        status = "журнал закрыт"
    elif code != 200:
        status = f"ошибка {code}"
    elif data.get("opponent", {}).get("tag") != CLAN_TAG:
        status = f"уже воюет дальше (state={data.get('state')})"
    elif data.get("endTime") != end:
        status = f"война с нами, но другая (endTime {data.get('endTime')})"
    else:
        found += 1
        fname = os.path.join(OUT_DIR, f"{end[:8]}_{opp_tag.lstrip('#')}.json")
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        status = f"НАЙДЕНА -> {fname}"

    print(f"{end[:8]}  {w.get('result', '?'):5}  {opp_tag:12} {opp_name}: {status}")
    time.sleep(0.2)  # не упираться в rate limit

print(f"\nНайдено полных войн: {found} из {len(wars)}")
