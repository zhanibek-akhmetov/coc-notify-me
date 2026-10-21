"""Делает календарь .ics из плана coc_plan.py: одно событие на каждый момент, когда надо что-то запустить.

Запуск: python make_ics.py plan_th7.json  ->  plan_th7.ics
Импорт: открой .ics на телефоне (Почта / Файлы) → «Добавить все».
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=5))  # часовой пояс, в котором считался план (как в coc_plan.py)
src = sys.argv[1] if len(sys.argv) > 1 else "plan.json"
out_file = os.path.splitext(src)[0] + ".ics"
plan = json.load(open(src, encoding="utf-8"))

starts = defaultdict(list)
for x in plan:
    if x["res"] == "-":  # стройки, которые уже шли на момент экспорта
        continue
    starts[x["start"]].append(x)


def esc(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line):
    """Перенос строк длиннее 75 байт по RFC 5545."""
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > 75:
            out.append(cur.decode("utf-8"))
            cur = b" "
        cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n".join(out)


utc = lambda d: d.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
now = utc(datetime.now(TZ))
lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//coc-notify-me//plan//RU", "CALSCALE:GREGORIAN",
         "METHOD:PUBLISH", "X-WR-CALNAME:Clash of Clans: план улучшений"]

for i, (start, items) in enumerate(sorted(starts.items())):
    s = datetime.fromisoformat(start).replace(tzinfo=TZ)
    names = [x["name"] for x in items]
    title = "CoC: " + (names[0] if len(names) == 1 else f"{names[0]} + ещё {len(names) - 1}")
    desc = "\n".join(
        f"{'Лаборатория' if x['kind'] == 'лаборатория' else 'Строитель'}: {x['name']} — "
        + f"{x['cost']:,}".replace(",", " ")
        + f" {x['res']}, готово {datetime.fromisoformat(x['end']):%d.%m %H:%M}"
        for x in items)
    lines += ["BEGIN:VEVENT", f"UID:coc-plan-{i}-{s:%Y%m%d%H%M}@coc-notify-me", f"DTSTAMP:{now}",
              f"DTSTART:{utc(s)}", f"DTEND:{utc(s + timedelta(minutes=10))}",
              fold("SUMMARY:" + esc(title)), fold("DESCRIPTION:" + esc(desc)),
              "BEGIN:VALARM", "ACTION:DISPLAY", fold("DESCRIPTION:" + esc(title)),
              "TRIGGER:PT0M", "END:VALARM", "END:VEVENT"]

end = max(datetime.fromisoformat(x["end"]) for x in plan).replace(tzinfo=TZ)
lines += ["BEGIN:VEVENT", "UID:coc-plan-done@coc-notify-me", f"DTSTAMP:{now}",
          f"DTSTART:{utc(end)}", f"DTEND:{utc(end + timedelta(minutes=10))}",
          fold("SUMMARY:" + esc("CoC: всё готово!")),
          "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:CoC: всё готово", "TRIGGER:PT0M",
          "END:VALARM", "END:VEVENT", "END:VCALENDAR"]

with open(out_file, "w", encoding="utf-8", newline="") as f:
    f.write("\r\n".join(lines) + "\r\n")
print(f"Событий: {len(starts) + 1} -> {out_file}")
