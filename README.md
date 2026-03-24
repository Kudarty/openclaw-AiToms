# openclaw-AiToms

Полезные скрипты, кроны и инструменты для [OpenClaw](https://openclaw.ai) от сообщества.

## 📁 Структура

```
scripts/    — утилиты и скрипты
crons/      — примеры кронов
docs/       — документация и решения типичных проблем
```

---

## 🧹 Скрипт-чистильщик сессий от base64 изображений

**Проблема:** изображения из Telegram встраиваются в `.jsonl` файл сессии как base64. Сессия раздувается до 2MB+ и агент перестаёт отвечать с ошибкой:
```
429 rate_limit_error: Extra usage is required for long context requests
```

**Решение:** скрипт убирает base64 из сессий, оставляя текстовый placeholder. Оригинал уже лежит в `~/.openclaw/media/inbound/` — данные не теряются.

> P.S. Это known issue, разработчики планируют нативный фикс.

---

## ⚡ Быстрая установка — скинь это своему агенту

Скопируй сообщение ниже и отправь своему агенту:

---

> Установи скрипт-чистильщик сессий от base64 изображений:
>
> 1. Скачай скрипт: `curl -o ~/scripts/clean_sessions.py https://raw.githubusercontent.com/Kudarty/openclaw-AiToms/main/scripts/clean_sessions.py`
> 2. Создай папку если нет: `mkdir -p ~/scripts`
> 3. Проверь что скрипт работает: `python3 ~/scripts/clean_sessions.py`
> 4. Добавь крон который будет запускать скрипт каждые 2 часа автоматически (sessionTarget: isolated, NO_REPLY если всё ок, сообщи если ошибка)
>
> Скрипт убирает base64 изображения из файлов сессий OpenClaw — уменьшает размер сессий и предотвращает ошибку 429.

---

## Ручная установка

```bash
# Скачать скрипт
curl -o ~/scripts/clean_sessions.py \
  https://raw.githubusercontent.com/Kudarty/openclaw-AiToms/main/scripts/clean_sessions.py

# Запустить вручную
python3 ~/scripts/clean_sessions.py
```

Пример крона (добавить в OpenClaw):
```json
{
  "name": "Session Image Cleaner",
  "schedule": { "kind": "cron", "expr": "0 */2 * * *", "tz": "Europe/Moscow" },
  "sessionTarget": "isolated",
  "payload": {
    "kind": "agentTurn",
    "message": "Запусти: python3 ~/scripts/clean_sessions.py\nЕсли ошибка — сообщи. Иначе NO_REPLY."
  }
}
```

---

## 🔍 scripts/rennerveit.py — диагностика после потери сознания

**«Реннервейт»** (Rennervate) — заклинание из Гарри Поттера, пробуждающее потерявшего сознание.

Запускается когда агент долго молчал и нужно понять что произошло.

**Что делает:**
- Читает лог OpenClaw за сегодня
- Находит момент сбоя и восстановления
- Вычисляет время простоя
- Определяет причину (rate limit, секреты, crash loop, сеть и др.)
- Выводит структурированный отчёт

**Запуск:**
```bash
python3 scripts/rennerveit.py
```

**Пример отчёта:**
```
🔍 Rennervate — диагностика агента OpenClaw
==================================================
📅 Дата:               24.03.2026
⏱  Начало сбоя:        22:25:21
🔄 Восстановление:     23:57:05
⏳ Время простоя:      91 мин
🔍 Причина:            Ошибка секретов — переменные окружения недоступны
📊 Статус:             ✅ Восстановлен
```

**Как добавить в OpenClaw как команду `/rennerveit`:**

Скопируй это своему агенту:

> Добавь команду `/rennerveit` в моё меню Telegram.
> При вызове — запускай `python3 ~/scripts/rennerveit.py` и отправляй мне результат.
> Скачай скрипт: `curl -o ~/scripts/rennerveit.py https://raw.githubusercontent.com/Kudarty/openclaw-AiToms/main/scripts/rennerveit.py`

---

## Контрибьютинг

Есть полезный скрипт или решение? Делай PR — поможем сообществу.
