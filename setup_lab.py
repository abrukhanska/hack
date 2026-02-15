import os
import pathlib

# Визначаємо кореневу директорію (скрипт має бути запущений поруч з HackerLab або всередині)
# Якщо ви запускаєте скрипт ВСЕРЕДИНІ папки HackerLab, змініть BASE_DIR на "."
BASE_DIR = "."

# Структура: Шлях до файлу -> Вміст (опис/коментар)
# Для бінарних файлів (pdf, png) залишаємо вміст None, створимо пусті файли-заглушки.
project_structure = {
    # --- chaoscrypt ---
    "chaoscrypt/launcher.py":
        "# Universal entrypoint (PDF-EXE), стартує Show + Stealth у паралельних процесах. Відкритий RTLO пояснюється, але опційний!",

    "chaoscrypt/modes/show_case.py":
        "# Ефект/Show-режим: wow-ефекти + реальний (але безпечний!) XOR-шифрувальник Target_Show, свій ключ + лог + QR.",

    "chaoscrypt/modes/stealth_case.py":
        "# Stealth/scenario: persistence, network imitation, delayed XOR-шифрування Target_Stealth, свій ключ + лог.",

    "chaoscrypt/dropper_engine.py":
        "# Контролер по фазах, координує запуск, lock-фікси, handed-off",

    "chaoscrypt/system_hooks.py":
        "# Registry/task/autorun (VM only!), sandbox-detect/removal, логування—ONLY MS Windows VM!",

    "chaoscrypt/encryptor.py":
        "# Multithread XOR (або AES із обов'язковим депозитом ключа у відповідний log у logs/), watermark, error-debug, recovery-lock",

    "chaoscrypt/network_monitor.py":
        "# C2 imitation (Telegram/HTTP/SOCKS), .pcap, log, race-catch, логування по папках",

    "chaoscrypt/file_agent.py":
        "# Швидкий скан папки, watermark, backup, окремий log для кожного use-case",

    "chaoscrypt/c2_commander.py":
        "# Telegram/Morse/HTTP exfil окремо для кожного режиму, ключ-прозорість (завжди у show_encrypt.log, stealth_encrypt.log, і QR/GUI)",

    "chaoscrypt/chaos_effects.py":
        "# Візуальні ефекти/Teaching: mouse, QR, glitch, все здвоєно по файлових/процесних lock'ах",

    "chaoscrypt/wallpaper_magic.py":
        "# wallpaper injection лише у ShowCase, шлях/розстановка по часу (аби не було race-overwrite!)",

    "chaoscrypt/payment_flow.py":
        "# Фейковий QR/payment/recovery unlock для Show, реальний recovery-lock для Stealth, все логічно",

    "chaoscrypt/decryptor_gui.py":
        "# Recovery GUI: вибір Target_show/Target_stealth, окремі ключі, відновлення, підписане логування",

    "chaoscrypt/antidote.py":
        "# Forensics/BlueTeam tool: показує PID/path/method/registry/remediation log, kill тільки після логування",

    "chaoscrypt/auto_analyzer.py":
        "# Timeline-аналітика (дві гілки — Show & Stealth), race-detect, recommendations (DFIR/pedagogical)",

    "chaoscrypt/logbook.py":
        "# Клеїть всі логи для timeline/analysis, race-catch",

    "chaoscrypt/settings.py":
        "# delays, Target_Show, Target_Stealth, config для race protections, safe mode, debug",

    "chaoscrypt/demo_launcher.py":
        "# Автоматизований stepwise запуск двох режимів, інтеграція логів, автоматичний таймінг фаз",

    # --- assets ---
    "assets/bonus.pdf": None,
    "assets/pdf.ico": None,
    "assets/infected_wall.bmp": None,
    "assets/chaos_logo.png": None,
    "assets/payment_qr.png": None,
    "assets/fake_invoice.txt": "Fake Invoice Content Placeholder",
    "assets/chaos_theme.json": "{}",
    "assets/lab_demo.mp4": None,

    # --- dist ---
    "dist/compiled_exes/.keep": "",  # .keep file to ensures git keeps folder even if empty
    "dist/installer.bat": "REM lab-setup (копія, quarantine, все авто, інструкції з безпеки)",

    # --- logs ---
    "logs/show_effect.log": "",
    "logs/show_encrypt.log": "# Містить ключ XOR/C2/fallback для розшифрування Target_Show!",
    "logs/stealth_infection.log": "",
    "logs/stealth_network.log": "",
    "logs/stealth_encrypt.log": "# Містить ключ XOR/C2/fallback для Target_Stealth!",
    "logs/shared_recovery.log": "",
    "logs/antidote.log": "# PID/path/registry/remediation+recommendations (BlueTeam-ready)",
    "logs/full_timeline.html": "",

    # --- Root ---
    "README.md": "# HackerLab Project\nDocumentation and setup guide."
}


def create_lab_structure():
    print(f"🚀 Починаю створення структури HackerLab у: {os.path.abspath(BASE_DIR)}")

    for file_path, content in project_structure.items():
        full_path = os.path.join(BASE_DIR, file_path)
        directory = os.path.dirname(full_path)

        # 1. Створення папок
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"📁 Створено папку: {directory}")

        # 2. Створення файлів
        if not os.path.exists(full_path):
            if content is None:
                # Створюємо пустий бінарний файл (для картинок/pdf)
                with open(full_path, 'wb') as f:
                    pass
            else:
                # Створюємо текстовий файл з коментарем
                with open(full_path, 'w', encoding='utf-8') as f:
                    # Якщо це .py файл, додаємо кодування utf-8 на початку
                    if full_path.endswith('.py'):
                        f.write(f"# -*- coding: utf-8 -*-\n{content}\n\ndef main():\n    pass\n")
                    else:
                        f.write(content)

            print(f"📄 Створено файл: {file_path}")
        else:
            print(f"⚠️  Пропущено (вже існує): {file_path}")

    print("\n✅ Структура успішно згенерована!")


if __name__ == "__main__":
    create_lab_structure()