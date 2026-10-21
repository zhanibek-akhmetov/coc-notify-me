"""Проверяет тег как игрока и как клан, сохраняет найденное в JSON.

Запуск: python coc_tag.py #ТЕГ   (ключ в переменной COC_API_KEY)
"""
import json, os, sys, urllib.request, urllib.parse, urllib.error

API_KEY = os.environ.get("COC_API_KEY")
if not API_KEY:
    sys.exit("Задай ключ в переменной COC_API_KEY (ключ: developer.clashofclans.com)")
if len(sys.argv) < 2:
    sys.exit('Запуск: python coc_tag.py "#ТЕГ"')
tag = sys.argv[1] if sys.argv[1].startswith("#") else "#" + sys.argv[1]

for kind in ("players", "clans"):
    url = f"https://api.clashofclans.com/v1/{kind}/{urllib.parse.quote(tag)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {API_KEY}"})
    try:
        with urllib.request.urlopen(req) as r:
            data = json.load(r)
        fname = f"{kind}_{tag.lstrip('#')}.json"
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(kind, "OK ->", fname)
    except urllib.error.HTTPError as e:
        print(kind, e.code, e.read().decode())
