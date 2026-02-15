import os
import json
import datetime
import html
import threading
import queue

from chaoscrypt.settings import (
    LOG_DIR, LOGFILES, TXT_LOGS, ROTATE_MAX_BYTES, PARSE_ERROR_LOG, TELEGRAM_AUTO_NOTIFY, ALL_PHASES
)

try:
    from chaoscrypt.telegram_notify import send_message
except ImportError:
    send_message = None


# --- Async telegram notifications (one worker, no spam)
class TelegramNotifier:
    _queue = queue.Queue()
    _worker_started = False

    @classmethod
    def notify(cls, text, parse_mode=None):
        cls._queue.put((text, parse_mode))
        if not cls._worker_started and send_message:
            threading.Thread(target=cls._worker, daemon=True).start()
            cls._worker_started = True

    @classmethod
    def _worker(cls):
        while True:
            text, parse_mode = cls._queue.get()
            try:
                send_message(text, parse_mode=parse_mode, async_mode=False)
            except Exception:
                pass


class LogbookEvent:
    def __init__(self, phase, event_type, msg, metadata=None, tag=None,
                 recommendation=None, source=None, timestamp=None):
        self.ts = timestamp or datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")
        self.phase = phase
        self.event_type = event_type
        self.msg = msg
        self.metadata = metadata or {}
        self.tag = tag
        self.recommendation = recommendation
        self.source = source

    def as_dict(self):
        return {
            "ts": self.ts,
            "phase": self.phase,
            "event_type": self.event_type,
            "msg": self.msg,
            "metadata": self.metadata,
            "tag": self.tag,
            "recommendation": self.recommendation,
            "source": self.source
        }

    def as_text(self):
        meta = "; ".join(f"{k}={v}" for k, v in (self.metadata or {}).items())
        base = f"{self.ts} [{self.phase.upper():7}] {self.event_type:<12}: {self.msg}"
        if meta: base += f" | {meta}"
        if self.tag: base += f" [{self.tag}]"
        if self.recommendation: base += f"\n  Recommendation: {self.recommendation}"
        if self.source: base += f"\n  Source: {self.source}"
        return base


class LogBook:
    def __init__(self, phase: str, log_path_override=None):
        os.makedirs(LOG_DIR, exist_ok=True)
        if phase not in LOGFILES:
            self.phase = phase
            self.jsonl_path = log_path_override or os.path.join(LOG_DIR, f"master_{phase}.jsonl")
            self.txt_path = os.path.join(LOG_DIR, f"{phase}.log")
        else:
            self.phase = phase
            self.jsonl_path = LOGFILES[phase]
            self.txt_path = TXT_LOGS[phase]
        self.fp_jsonl = open(self.jsonl_path, 'a+', encoding='utf-8', buffering=1)
        self.fp_txt = open(self.txt_path, 'a+', encoding='utf-8', buffering=1)
        self._lock = threading.Lock()
        self._maybe_rotate()

    def _rotate_file(self, path, file_handle):
        if os.path.exists(path):
            try:
                if os.path.getsize(path) > ROTATE_MAX_BYTES:
                    file_handle.flush()
                    file_handle.close()
                    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')
                    os.rename(path, f"{path}.{ts}.bak")
                    return open(path, 'a+', encoding='utf-8', buffering=1)
            except Exception:
                try:
                    return open(path, 'a+', encoding='utf-8', buffering=1)
                except:
                    pass
        return file_handle

    def _maybe_rotate(self):
        self.fp_jsonl = self._rotate_file(self.jsonl_path, self.fp_jsonl)
        self.fp_txt = self._rotate_file(self.txt_path, self.fp_txt)

    def log(self, event: LogbookEvent):
        # 1. Запис у файли (завжди повний лог)
        data = event.as_dict()
        text = event.as_text()
        with self._lock:
            try:
                self.fp_jsonl.write(json.dumps(data, ensure_ascii=False) + '\n')
                self.fp_txt.write(text + '\n')
                self._maybe_rotate()
            except Exception as e:
                with open(PARSE_ERROR_LOG, 'a', encoding='utf-8') as ef:
                    ef.write(f"Log I/O error: {e}\n")

        # 2. Фільтрований Telegram Notify (Розумна фільтрація)
        if TELEGRAM_AUTO_NOTIFY and send_message:
            # Список типів, які ВАРТО слати в Telegram
            # Примітка: 'encryption' тут немає, бо ми шлемо summary вручну з show_case.py
            important_types = {
                "fail", "finish", "phase", "dropper", "summary",
                "IOC", "network", "recommendation", "remediation", "exfiltration"
            }

            # Також пропускаємо, якщо є теги CRITICAL або IOC
            has_urgent_tag = event.tag and ("critical" in event.tag.lower() or "ioc" in event.tag.lower())
            is_important = (event.event_type in important_types)

            if is_important or has_urgent_tag:
                # 2.1. Формуємо красивий HTML
                msg = f"<b>[{self.phase.upper()}]</b> {html.escape(event.msg)}"

                # 2.2. === ДОДАНО: Екстракція важливих метаданих ===
                # Щоб бачити PID, назви процесів, шляхи в повідомленні
                if event.metadata:
                    # Вибираємо тільки ключові поля, щоб не захаращувати чат
                    key_fields = ('pid', 'process', 'exe', 'file', 'count', 'rc', 'key', 'reg_key')
                    meta_str = ""
                    for k, v in event.metadata.items():
                        if k in key_fields or 'path' in k:
                            # Обрізаємо довгі шляхи
                            val_str = str(v)
                            if len(val_str) > 40: val_str = "..." + val_str[-37:]
                            meta_str += f"\n  └ <code>{k}: {val_str}</code>"
                    msg += meta_str

                if event.tag:
                    msg += f"\n🏷️ <i>#{event.tag}</i>"

                TelegramNotifier.notify(msg, parse_mode="HTML")

    def log_event(self, event_type, msg, **kwargs):
        ev = LogbookEvent(
            phase=self.phase,
            event_type=event_type,
            msg=msg,
            metadata=kwargs.get('metadata'),
            tag=kwargs.get('tag'),
            recommendation=kwargs.get('recommendation'),
            source=kwargs.get('source')
        )
        self.log(ev)

    def close(self):
        self.fp_jsonl.flush()
        self.fp_jsonl.close()
        self.fp_txt.flush()
        self.fp_txt.close()

    # ... (get_events, combine_events, export_timeline_... залишаються без змін) ...
    def get_events(self):
        if not os.path.exists(self.jsonl_path): return
        with open(self.jsonl_path, 'r', encoding='utf-8') as jf:
            for idx, line in enumerate(jf):
                line = line.strip()
                if not line: continue
                try:
                    yield json.loads(line)
                except Exception as e:
                    with open(PARSE_ERROR_LOG, 'a', encoding='utf-8') as ef:
                        ef.write(f"Line {idx}: {type(e).__name__}: {e}: {line}\n")

    @staticmethod
    def combine_events(phases=None):
        phases = phases or ALL_PHASES
        for ph in phases:
            logpth = LOGFILES.get(ph)
            if not logpth or not os.path.exists(logpth): continue
            with open(logpth, 'r', encoding='utf-8') as f:
                for idx, line in enumerate(f):
                    line = line.strip()
                    if not line: continue
                    try:
                        ev = json.loads(line)
                        ev['__logfile'] = ph
                        yield ev
                    except Exception as e:
                        with open(PARSE_ERROR_LOG, 'a', encoding='utf-8') as ef:
                            ef.write(f"[{ph} Line {idx}] {type(e).__name__}: {e}: {line}\n")

    @staticmethod
    def export_timeline_html(out_file=None, phases=None):
        # ... (код з попереднього повідомлення) ...
        # (для економії місця, якщо він у тебе вже є, можна не дублювати,
        #  головне - оновлений метод log)
        from collections import defaultdict
        phases = phases or ALL_PHASES
        grps = defaultdict(list)
        for ev in LogBook.combine_events(phases):
            grps[ev.get("phase")].append(ev)
        html_table = ""
        for phase in sorted(grps.keys()):
            html_table += f"<h3>Phase: {html.escape(str(phase).title())}</h3>"
            html_table += ("<table><tr><th>Time (UTC)</th><th>EventType</th><th>Message</th><th>Tag</th>"
                           "<th>Meta</th><th>Recommendation</th><th>Source</th></tr>")
            for ev in grps[phase]:
                meta = "; ".join(
                    f"{html.escape(str(k))}={html.escape(str(v))}" for k, v in (ev.get('metadata') or {}).items())
                rec = (
                    f"<span style='color:#0066cc;font-weight:bold'>{html.escape(str(ev.get('recommendation', '')))}</span>"
                    if ev.get("recommendation") else "")
                html_table += (f"<tr><td>{html.escape(ev['ts'])}</td><td>{html.escape(ev['event_type'])}</td>"
                               f"<td>{html.escape(ev['msg'])}</td><td>{html.escape(str(ev.get('tag', '')))}</td>"
                               f"<td>{meta}</td><td>{rec}</td><td>{html.escape(str(ev.get('source', '')))}</td></tr>")
            html_table += "</table>\n"
        html_content = (
                "<html><head><meta charset='utf-8'><style>"
                "body{font-family:Consolas;font-size:13px;}"
                "table{border-collapse:collapse;width:100%;margin-bottom:25px;}"
                "th,td{border:1px #bbb solid;padding:6px 10px;}"
                "tr:nth-child(even){background:#f7f7f7;}"
                "</style></head><body>"
                "<h2>ChaosCrypt Parallel Attack Timeline (All phases, UTC/streamed)</h2>"
                + html_table +
                "</body></html>"
        )
        outp = out_file or os.path.join(LOG_DIR, "full_timeline.html")
        with open(outp, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return outp

    @staticmethod
    def export_timeline_csv(out_file=None, phases=None):
        import csv
        phases = phases or ALL_PHASES
        outp = out_file or os.path.join(LOG_DIR, "full_timeline.csv")
        keys = ["ts", "phase", "event_type", "msg", "tag", "metadata", "source", "recommendation"]
        with open(outp, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for ev in LogBook.combine_events(phases):
                row = {k: ev.get(k, "") for k in keys}
                if isinstance(row['metadata'], dict):
                    row['metadata'] = "; ".join(f"{k}={v}" for k, v in row['metadata'].items())
                writer.writerow(row)
        return outp

    @staticmethod
    def export_timeline_json(out_file=None, phases=None):
        phases = phases or ALL_PHASES
        outp = out_file or os.path.join(LOG_DIR, "full_timeline.json")
        with open(outp, 'w', encoding='utf-8') as f:
            f.write("[\n")
            items = LogBook.combine_events(phases)
            first = True
            for ev in items:
                if not first:
                    f.write(",\n")
                f.write(json.dumps(ev, ensure_ascii=False))
                first = False
            f.write("\n]\n")
        return outp


if __name__ == "__main__":
    # Test run
    test = LogBook('test')
    test.log_event('remediation', "Process killed", metadata={'pid': 1234, 'exe': 'malware.exe'})
    test.close()