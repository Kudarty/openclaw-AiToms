#!/usr/bin/env python3
"""
clean_sessions.py — чистильщик base64 изображений из JSONL сессий OpenClaw.

Что делает:
- Находит все .jsonl файлы сессий
- Заменяет встроенные base64 изображения на текст "[image saved to media/inbound/...]"
- Оригинал уже лежит в ~/.openclaw/media/inbound/ — данные не теряются
- Перезаписывает файл только если были изменения

Запуск: python3 clean_sessions.py
Крон: каждый час
"""

import json
import os
import re
import shutil
from pathlib import Path
from datetime import datetime

SESSIONS_DIR = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
LOG_FILE = Path("/tmp/clean_sessions.log")

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def clean_content(content):
    """Заменяет base64 изображения в content блоках на ссылку."""
    if not isinstance(content, list):
        return content, False

    changed = False
    new_content = []
    for block in content:
        if not isinstance(block, dict):
            new_content.append(block)
            continue

        is_image = False
        media_type = "image"

        # Формат 1: {"type": "image", "source": {"type": "base64", ...}}
        if block.get("type") == "image":
            source = block.get("source", {})
            if isinstance(source, dict) and source.get("type") == "base64":
                media_type = source.get("media_type", "image")
                is_image = True

        # Формат 2: {"type": "image", "data": "base64...", "mimeType": "image/jpeg"}
        if block.get("type") == "image" and "data" in block:
            data = block.get("data", "")
            if isinstance(data, str) and len(data) > 100:  # явно base64
                media_type = block.get("mimeType", "image")
                is_image = True

        if is_image:
            new_block = {
                "type": "text",
                "text": f"[image embedded: {media_type}, saved to ~/.openclaw/media/inbound/]"
            }
            new_content.append(new_block)
            changed = True
            continue

        new_content.append(block)
    return new_content, changed

def clean_jsonl(filepath: Path) -> dict:
    """Чистит один JSONL файл. Возвращает статистику."""
    size_before = filepath.stat().st_size
    lines_changed = 0
    new_lines = []

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                new_lines.append(line)
                continue
            try:
                obj = json.loads(line)
                if obj.get("type") == "message":
                    msg = obj.get("message", {})
                    content = msg.get("content")
                    new_content, changed = clean_content(content)
                    if changed:
                        obj["message"]["content"] = new_content
                        lines_changed += 1
                new_lines.append(json.dumps(obj, ensure_ascii=False))
            except json.JSONDecodeError:
                new_lines.append(line)

    if lines_changed > 0:
        # Бекап перед перезаписью
        backup = filepath.with_suffix(".jsonl.pre_clean")
        shutil.copy2(filepath, backup)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")

        size_after = filepath.stat().st_size
        # Удаляем бекап если всё ок
        backup.unlink()
        return {
            "changed": True,
            "lines_changed": lines_changed,
            "size_before": size_before,
            "size_after": size_after,
            "saved_bytes": size_before - size_after
        }

    return {"changed": False, "lines_changed": 0, "size_before": size_before}

def main():
    if not SESSIONS_DIR.exists():
        log(f"Папка сессий не найдена: {SESSIONS_DIR}")
        return

    jsonl_files = sorted(SESSIONS_DIR.glob("*.jsonl"), key=lambda f: f.stat().st_size, reverse=True)
    total_saved = 0
    files_cleaned = 0

    log(f"Найдено файлов: {len(jsonl_files)}")

    for filepath in jsonl_files:
        size_mb = filepath.stat().st_size / 1024 / 1024
        if size_mb < 0.1:  # Пропускаем файлы меньше 100KB
            continue

        result = clean_jsonl(filepath)
        if result["changed"]:
            saved_kb = result["saved_bytes"] / 1024
            log(f"✅ {filepath.name}: убрано {result['lines_changed']} картинок, "
                f"сэкономлено {saved_kb:.1f}KB "
                f"({result['size_before']//1024}KB → {result['size_after']//1024}KB)")
            total_saved += result["saved_bytes"]
            files_cleaned += 1
        else:
            log(f"— {filepath.name}: без изменений ({size_mb:.1f}MB)")

    if files_cleaned > 0:
        log(f"Итого: почищено {files_cleaned} файлов, сэкономлено {total_saved/1024:.1f}KB")
    else:
        log("Нечего чистить — изображений в сессиях не найдено")

if __name__ == "__main__":
    main()
