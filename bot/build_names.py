"""Собирает coc_names.json (код объекта -> официальное русское название) из данных библиотеки coc.py.

Источник: https://github.com/mathsman5133/coc.py/tree/master/coc/static
Запуск: python build_names.py <static_data.json> <translations.json>
"""
import json
import sys

static = json.load(open(sys.argv[1], encoding="utf-8"))
tr = json.load(open(sys.argv[2], encoding="utf-8"))

names = {}
for section in ("buildings", "traps", "troops", "guardians", "spells", "heroes", "pets", "equipment", "helpers"):
    for x in static.get(section, []):
        if not isinstance(x, dict) or "_id" not in x:
            continue
        tid = (x.get("TID") or {}).get("name", "")
        t = tr.get(tid) or {}
        names[str(x["_id"])] = {"ru": t.get("RU") or x.get("name"), "en": t.get("EN") or x.get("name"),
                                "village": x.get("village", "home"), "section": section}

with open("coc_names.json", "w", encoding="utf-8") as f:
    json.dump(names, f, ensure_ascii=False, indent=1, sort_keys=True)
print(f"Сохранено названий: {len(names)}")
