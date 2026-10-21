"""Собирает chart_template.html (шаблон графика) и docs/index.html (демо + просмотрщик ссылок из бота).

В шаблон встраиваются официальные названия объектов на русском и английском из bot/coc_names.json,
поэтому график работает без интернета и без дополнительных запросов.

Запуск (после правок chart_template.src.html или coc_names.json):
    python planner/build_template.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

names = json.load(open(os.path.join(REPO, "bot", "coc_names.json"), encoding="utf-8"))
compact = {k: [v["ru"], v["en"]] for k, v in names.items()}
src = open(os.path.join(HERE, "chart_template.src.html"), encoding="utf-8").read()
tpl = src.replace("/*NAMES*/{}", json.dumps(compact, ensure_ascii=False, separators=(",", ":")))
open(os.path.join(HERE, "chart_template.html"), "w", encoding="utf-8").write(tpl)
print(f"chart_template.html: {len(compact)} названий")

# демо для GitHub Pages: пример из planner/examples, открывается и по ссылке из бота (#p=…)
import coc_plan  # noqa: E402  (нужен собранный шаблон)

example = os.path.join(HERE, "examples", "export_th7.json")
plan = coc_plan.make_plan(json.load(open(example, encoding="utf-8-sig")))
os.makedirs(os.path.join(REPO, "docs"), exist_ok=True)
open(os.path.join(REPO, "docs", "index.html"), "w", encoding="utf-8").write(coc_plan.render_html(plan))
print("docs/index.html: демо ратуши", plan["th"])
