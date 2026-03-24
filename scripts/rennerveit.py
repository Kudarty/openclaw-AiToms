#!/usr/bin/env python3
"""
rennerveit.py — диагностика после потери сознания агента OpenClaw.

Название: «Реннервейт» (Rennervate) — заклинание из Гарри Поттера,
пробуждающее потерявшего сознание. Запускается когда агент долго молчал.

Что делает:
- Читает лог OpenClaw за сегодня
- Находит последнюю активность агента до сбоя
- Вычисляет время простоя
- Определяет причину
- Выводит структурированный отчёт

Запуск: python3 rennerveit.py
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Конфиг ───────────────────────────────────────────────────────────────────
LOG_DIR = Path("/tmp/openclaw")
NOW = datetime.now().astimezone()

# Паттерны для определения причин
CAUSES = {
    "rate_limit":     ["429", "rate_limit", "Extra usage"],
    "secrets":        ["SecretRefResolutionError", "missing or empty", "secrets unavailable", "required secrets"],
    "token_mismatch": ["token mismatch", "unauthorized: gateway"],
    "crash_loop":     ["Gateway failed to start", "Startup failed"],
    "session_bloat":  ["2.1M", "2.3M", "long context", "context request"],
    "network":        ["ETIMEDOUT", "ENETUNREACH", "fetch fallback"],
    "telegram":       ["botToken: unresolved", "telegram.*error"],
}

def find_log_file():
    """Находит лог за сегодня или вчера."""
    for delta in [0, 1]:
        date_str = (NOW.date().__class__(NOW.year, NOW.month, NOW.day - delta) 
                    if delta == 0 else None)
        if delta == 0:
            date_str = NOW.strftime("%Y-%m-%d")
        else:
            from datetime import timedelta
            date_str = (NOW - timedelta(days=1)).strftime("%Y-%m-%d")
        
        log_file = LOG_DIR / f"openclaw-{date_str}.log"
        if log_file.exists():
            return log_file
    return None

def parse_log(log_file, limit=500):
    """Читает последние N строк лога, возвращает события с временными метками."""
    events = []
    try:
        with open(log_file, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-limit:]
        
        for line in lines:
            try:
                obj = json.loads(line)
                time_str = obj.get("time", "")
                if not time_str:
                    continue
                t = datetime.fromisoformat(time_str)
                level = obj.get("_meta", {}).get("logLevelName", "")
                msg = str(obj.get("0", ""))
                subsystem = str(obj.get("_meta", {}).get("name", ""))
                events.append({
                    "time": t,
                    "level": level,
                    "msg": msg,
                    "subsystem": subsystem,
                    "raw": line.strip()
                })
            except:
                pass
    except Exception as e:
        print(f"Ошибка чтения лога: {e}")
    
    return events

def find_last_agent_activity(events):
    """Находит время последней активности агента (INFO без ошибок)."""
    for event in reversed(events):
        if event["level"] == "INFO" and "cron" not in event["subsystem"].lower():
            return event["time"]
    return None

def find_first_error(events, after=None):
    """Находит первую ошибку после указанного времени."""
    for event in events:
        if after and event["time"] <= after:
            continue
        if event["level"] == "ERROR":
            return event
    return None

def find_recovery(events, after=None):
    """Находит момент восстановления gateway."""
    for event in events:
        if after and event["time"] <= after:
            continue
        if "listening on" in event["msg"] or "bonjour: advertised" in event["msg"]:
            return event["time"]
    return None

def detect_cause(events, start=None, end=None):
    """Определяет причину сбоя по ключевым словам в логах."""
    relevant = [e for e in events 
                if (start is None or e["time"] >= start) 
                and (end is None or e["time"] <= end)]
    
    all_text = " ".join([e["msg"] for e in relevant]).lower()
    
    detected = []
    for cause, keywords in CAUSES.items():
        for kw in keywords:
            if kw.lower() in all_text:
                detected.append(cause)
                break
    
    if not detected:
        return "unknown"
    
    # Приоритет причин
    priority = ["crash_loop", "secrets", "token_mismatch", "rate_limit", 
                "session_bloat", "telegram", "network"]
    for p in priority:
        if p in detected:
            return p
    return detected[0]

CAUSE_DESCRIPTIONS = {
    "rate_limit":     "Rate limit Anthropic (429) — превышен лимит API",
    "secrets":        "Ошибка секретов — переменные окружения недоступны",
    "token_mismatch": "Несовпадение токена gateway",
    "crash_loop":     "Crash loop gateway — не мог стартовать",
    "session_bloat":  "Раздутая сессия — слишком большой контекст",
    "network":        "Сетевая ошибка (timeout/unreachable)",
    "telegram":       "Ошибка Telegram канала",
    "unknown":        "Причина не определена — проверьте лог вручную",
}

def format_duration(seconds):
    if seconds < 60:
        return f"{int(seconds)} сек"
    elif seconds < 3600:
        return f"{int(seconds // 60)} мин"
    else:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h} ч {m} мин"

def run():
    print("🔍 Rennervate — диагностика агента OpenClaw")
    print("=" * 50)
    
    # Находим лог
    log_file = find_log_file()
    if not log_file:
        print("❌ Лог не найден в /tmp/openclaw/")
        print("   Убедитесь что OpenClaw запущен и путь к логам корректный.")
        sys.exit(1)
    
    print(f"📄 Лог: {log_file}")
    print(f"🕐 Сейчас: {NOW.strftime('%H:%M:%S %d.%m.%Y')}")
    print()
    
    # Парсим
    events = parse_log(log_file)
    if not events:
        print("❌ Лог пустой или нечитаемый.")
        sys.exit(1)
    
    # Последняя активность
    last_active = find_last_agent_activity(events)
    if not last_active:
        print("⚠️  Активность агента не найдена в логе.")
        sys.exit(0)
    
    downtime_seconds = (NOW - last_active).total_seconds()
    
    # Если простой меньше 5 минут — всё нормально
    if downtime_seconds < 300:
        print(f"✅ Агент активен. Последняя активность: {last_active.strftime('%H:%M:%S')}")
        print(f"   Время с последней активности: {format_duration(downtime_seconds)}")
        print("\nПотери сознания не обнаружено.")
        return
    
    # Находим первую ошибку
    first_error = find_first_error(events)
    error_time = first_error["time"] if first_error else last_active
    
    # Находим восстановление
    recovery_time = find_recovery(events, after=error_time)
    
    # Определяем причину
    cause_key = detect_cause(events, start=error_time, end=recovery_time)
    cause_desc = CAUSE_DESCRIPTIONS.get(cause_key, "Неизвестно")
    
    # Считаем реальное время простоя
    if recovery_time:
        actual_downtime = (recovery_time - error_time).total_seconds()
        status = "✅ Восстановлен"
        recovery_str = recovery_time.strftime('%H:%M:%S')
    else:
        actual_downtime = downtime_seconds
        status = "🔴 Не восстановлен"
        recovery_str = "не восстановлен"
    
    # Отчёт
    print("⚠️  ОБНАРУЖЕНА ПОТЕРЯ СОЗНАНИЯ")
    print("-" * 50)
    print(f"📅 Дата:               {error_time.strftime('%d.%m.%Y')}")
    print(f"⏱  Начало сбоя:        {error_time.strftime('%H:%M:%S')}")
    print(f"🔄 Восстановление:     {recovery_str}")
    print(f"⏳ Время простоя:      {format_duration(actual_downtime)}")
    print(f"🔍 Причина:            {cause_desc}")
    print(f"📊 Статус:             {status}")
    print()
    
    if first_error:
        print(f"💬 Первая ошибка:")
        print(f"   {first_error['msg'][:200]}")
    
    print()
    print("=" * 50)
    print("Запишите инцидент в memory/bugs.md")


if __name__ == "__main__":
    run()
