# CoC Notify Me

[![tests](https://github.com/zhanibek-akhmetov/coc-notify-me/actions/workflows/tests.yml/badge.svg)](https://github.com/zhanibek-akhmetov/coc-notify-me/actions/workflows/tests.yml)
![python](https://img.shields.io/badge/python-3.9%2B-blue)
![dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)

**A Telegram bot that pings you when your Clash of Clans upgrades finish, plus an upgrade planner that builds a Gantt chart of the fastest way to max your Town Hall.**

Pure Python 3.9+, zero dependencies (standard library only). No pip install.

[Русская версия ниже ↓](#-по-русски)

> Unofficial fan project, not affiliated with Supercell.

---

## ✨ What's inside

| Part | What it does |
|---|---|
| 🤖 [`bot/`](bot/) | Telegram bot: paste your in-game village export → get a message the moment each building, research or hero upgrade finishes. Home Village and Builder Base. |
| 📊 [`planner/`](planner/) | Reads the same export and simulates 5 builders + the laboratory to find the fastest order to max the current Town Hall and upgrade to the next one. Outputs an interactive HTML Gantt chart and an `.ics` calendar. |
| 🔎 [`api-tools/`](api-tools/) | Small scripts for the official Clash of Clans API: clan war log, current war, CWL, player/clan lookup by tag. |

**▶ Live demo of the planner: [zhanibek-akhmetov.github.io/coc-notify-me](https://zhanibek-akhmetov.github.io/coc-notify-me/)** — an interactive Gantt chart for a Town Hall 7 village (tap bars to mark upgrades as started).

---

## 🤖 Telegram bot

### Features
- **Notifications** when an upgrade finishes, grouped by village, with the next thing to finish.
- **📋 Running**: every timer in a clean aligned list (monospace time column, quote blocks).
- **⏭ Next**: what finishes next in each village.
- **👷 Builders**: how many builders are free, when busy ones free up, whether the lab is free.
- **📊 Chart**: first asks what to include — 🛡 defenses (incl. traps and walls), 🧪 laboratory research, 👑 heroes, 💰 resource buildings (mines, collectors, drills, storages) — then builds the fastest upgrade plan from your last export and sends a button that opens the interactive Gantt chart. The whole plan is packed into the link itself (after `#`), so it is never sent to a server or stored anywhere.
- **🌙 Quiet hours**: no pings at night, one "Good morning" summary instead. The chart treats them as your sleep time.
- **🕐 Time zone** (in the menu): times, quiet hours and the chart follow your zone.
- **🌐 Russian / English**: UI and official in-game object names in both languages.
- Accepts the export as text, as a file, or split across several messages (Telegram splits long texts).
- Survives restarts: timers are stored in `bot_data.json`; anything that finished while the bot was off is sent on startup.

### Example
```
📋 #EXAMPLE · export 18:14

🏠 HOME VILLAGE
👷 1/5  ·  🧪 busy
┃   10m 🔨 Cannon #1 → 8
┃2h 42m 🧪 Balloon → 4

🛠 BUILDER BASE
👷 0/1  ·  🧪 free
┃1h 58m 🔨 Army Camp — new
```

### Run it
1. Create a bot with [@BotFather](https://t.me/BotFather) (`/newbot`) and copy the token.
2. Put the token into `bot/bot_token.txt` (this file is git-ignored) or set `TELEGRAM_BOT_TOKEN`.
3. Start it:
   ```bash
   python bot/coc_bot.py
   ```
4. In the game: **Settings → More Settings → Data Export → Copy**, then paste it into the chat with your bot.

Check parsing without Telegram:
```bash
python bot/coc_bot.py --parse planner/examples/export_th7.json
```

**Run 24/7 on Windows:** create a Task Scheduler task that runs `pythonw.exe bot\coc_bot.py` at log on, with "restart on failure". The bot logs to `bot/bot.log` and waits for the network after boot.

---

## 📊 Upgrade planner

```bash
cd planner
python coc_plan.py examples/export_th8.json   # → plan_th8.html + plan_th8.json + a shareable link
python make_ics.py plan_th8.json               # → plan_th8.ics (import into iPhone / Google Calendar)
```

How it works:
- Parses the export: current levels, running timers, missing buildings, unlocked troops and spells.
- Builds upgrade chains from current level to the Town Hall cap (costs and times from the Clash of Clans Wiki), including research dependencies (e.g. Wizard needs Barracks 7 and Lab 3, Dragon needs Barracks 9).
- Simulates 5 builders and the laboratory with a sleep window (no new upgrades 00:30–08:00): long upgrades go overnight, short ones fill the day.
- Tries a few dozen scheduling strategies and hundreds of research orders, and keeps the one that finishes earliest.
- The HTML chart lets you tap any bar or list row to mark it as "started"; marks are saved in the browser.

Supported Town Halls: 5–8 (adding more = adding their tables to `coc_plan.py`).

Options: `--tz 1` (time zone, default UTC+5), `--lang en`, and `--no-def` / `--no-lab` / `--no-heroes` / `--no-res` to leave defenses (with traps and walls), research, heroes or resource buildings out of the plan (anything already running still occupies its builder or the lab). The chart page is one template ([`planner/chart_template.src.html`](planner/chart_template.src.html)) used three ways: the offline `plan_thN.html`, the demo on GitHub Pages, and the viewer for links from the bot (`…/coc-notify-me/#p=<compressed plan>`). After editing it, run `python planner/build_template.py`.

---

## 🔎 API tools

Need a free key from [developer.clashofclans.com](https://developer.clashofclans.com) (keys are bound to your IP).

Put the key into `api-tools/coc_api_key.txt` (git-ignored), or set the `COC_API_KEY` environment variable.

```bash
python api-tools/coc_war.py "#CLANTAG"            # current war, war log, CWL → clans/<tag>/
python api-tools/coc_warlog_year.py 2015 "#CLANTAG"  # full war log filtered by year
python api-tools/coc_tag.py "#TAG"                # is it a player or a clan?
python api-tools/coc_war_hunt.py                  # recover full old wars via opponents' currentwar
```

---

## ✅ Tests

No network or tokens needed — GitHub Actions runs them on every push (Linux + Windows, Python 3.9 and 3.12):

```bash
python tests/test_bot.py        # bot with a fake Telegram API: every button, RU/EN, notifications, quiet hours, bad input
python tests/test_planner.py    # builds the example plan and validates the schedule against the wiki tables
python tests/test_api_tools.py  # API scripts compile and fail politely without a key
```

The planner validator checks that no builder or the lab does two things at once, nothing starts while you sleep, every duration matches the wiki, levels go in order, research waits for the right lab level and unlocking building, and everything reaches the Town Hall cap. It is itself tested by feeding it a deliberately broken schedule.

---

## 🗂 Project structure
```
bot/          coc_bot.py, coc_names.json (RU/EN names), build_names.py
planner/      coc_plan.py, make_ics.py, examples/
api-tools/    coc_war.py, coc_war_hunt.py, coc_warlog_year.py, coc_tag.py
docs/         index.html (demo chart for GitHub Pages)
tests/        test_bot.py, test_planner.py, test_api_tools.py
.github/      workflows/tests.yml (CI)
```

Code comments are in Russian.

---

## 🇷🇺 По-русски

**CoC Notify Me** — Telegram-бот, который присылает уведомление, когда в Clash of Clans завершается стройка, исследование или улучшение героя, и планировщик, который строит диаграмму Ганта с самым быстрым порядком прокачки ратуши.

- **Бот:** пришли ему экспорт деревни (Настройки → Другие настройки → Экспорт данных → Копировать). Кнопки: 📋 Что идёт, ⏭ Ближайшее, 👷 Свободные, 🌙 Тихие часы, 🌐 English.
- **Планировщик:** `python planner/coc_plan.py export.json` → HTML-график с отметками «поставил в работу» и календарь `.ics` для айфона.
- **API-инструменты:** журнал клановых войн, текущая война, ЛВК, поиск по тегу.

Только стандартная библиотека Python, ничего устанавливать не нужно. Неофициальный фан-проект, не связан с Supercell.

## License
MIT — see [LICENSE](LICENSE).
