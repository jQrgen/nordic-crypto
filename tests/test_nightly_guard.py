#!/usr/bin/env python3
"""The nightly fetch must not hang: the fetch lock is re-entrant, requests have a timeout,
and routines/nightly-fetch.sh reports a stale lock and its own timeout instead of sitting silent.
No network.
"""
import os
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import fetch
import crosssite_handoff

fails = []


def check(ok, msg):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


def test_log_while_holding_the_fetch_lock():
    """add() used to call log() while it already held this lock. A Lock deadlocks the run."""
    done = []

    def run():
        with fetch._io:
            fetch.log("reentered lock")
        done.append(True)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(3)
    check(not t.is_alive() and done == [True], "log() while holding the fetch lock returns")


def test_requests_get_a_default_timeout():
    seen = {}
    real = fetch._REAL_REQUEST

    def fake(self, method, url, **kw):
        seen.clear()
        seen.update(kw)
        return "ok"

    fetch._REAL_REQUEST = fake
    try:
        fetch._request_with_timeout(object(), "GET", "http://example.invalid/")
        check(seen.get("timeout") == 25, "a request with no timeout gets 25s")
        fetch._request_with_timeout(object(), "GET", "http://example.invalid/", timeout=7)
        check(seen.get("timeout") == 7, "an explicit timeout is kept")
        fetch._request_with_timeout(object(), "GET", "http://example.invalid/", timeout=None)
        check(seen.get("timeout") == 25, "timeout=None is not an infinite wait")
    finally:
        fetch._REAL_REQUEST = real


def _run(env, timeout=20):
    e = os.environ.copy()
    e.update(env)
    e.setdefault("NIGHTLY_TIMEOUT_SECS", "30")
    e.setdefault("NIGHTLY_STALE_SECS", "1500")
    return subprocess.run(
        ["bash", os.path.join(ROOT, "routines", "nightly-fetch.sh")],
        cwd=ROOT, env=e, capture_output=True, text=True, timeout=timeout,
    )


def test_script_times_out_with_a_message():
    log = tempfile.NamedTemporaryFile(prefix="nightly-", suffix=".txt", delete=False)
    log.close()
    lock = tempfile.NamedTemporaryFile(prefix="nightly-", suffix=".lock", delete=False)
    lock.close()
    os.unlink(lock.name)
    try:
        r = _run({
            "NIGHTLY_TIMEOUT_SECS": "2",
            "NIGHTLY_LOG": log.name,
            "NIGHTLY_LOCK": lock.name,
            "NIGHTLY_HOOK": "sleep 30",
        }, timeout=15)
        text = (r.stdout or "") + (r.stderr or "") + open(log.name, encoding="utf-8").read()
        check(r.returncode == 124, f"timeout exits 124 (got {r.returncode})")
        check("== nightly fetch" in text, "progress is printed before any work")
        check("timed out after 2s" in text, "the timeout says how long it waited")
        check("sleep 30" not in text or "timed out" in text, "the message is the timeout, not an empty log")
    finally:
        os.unlink(log.name)
        if os.path.exists(lock.name):
            os.unlink(lock.name)


def test_a_live_lock_does_not_wait():
    log1 = tempfile.NamedTemporaryFile(prefix="nightly-", suffix=".txt", delete=False)
    log2 = tempfile.NamedTemporaryFile(prefix="nightly-", suffix=".txt", delete=False)
    log1.close(); log2.close()
    lock = tempfile.NamedTemporaryFile(prefix="nightly-", suffix=".lock", delete=False)
    lock.close()
    os.unlink(lock.name)
    env = {
        "NIGHTLY_TIMEOUT_SECS": "40",
        "NIGHTLY_STALE_SECS": "1500",
        "NIGHTLY_LOCK": lock.name,
        "NIGHTLY_HOOK": "sleep 40",
        "NIGHTLY_LOG": log1.name,
    }
    first = subprocess.Popen(
        ["bash", os.path.join(ROOT, "routines", "nightly-fetch.sh")],
        cwd=ROOT, env={**os.environ, **env}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        for _ in range(50):
            if os.path.exists(lock.name) and open(lock.name).read().strip():
                break
            time.sleep(0.1)
        second = _run({
            "NIGHTLY_TIMEOUT_SECS": "30",
            "NIGHTLY_STALE_SECS": "1500",
            "NIGHTLY_LOCK": lock.name,
            "NIGHTLY_LOG": log2.name,
            "NIGHTLY_HOOK": "true",
        }, timeout=15)
        text = (second.stdout or "") + (second.stderr or "")
        check(second.returncode == 1, f"a live lock exits 1 (got {second.returncode})")
        check("another run is active" in text, "a live lock is reported, not waited out")
        check(first.poll() is None, "the running fetch is left alone when its lock is fresh")
    finally:
        first.kill()
        first.wait(timeout=5)
        for p in (log1.name, log2.name, lock.name):
            if os.path.exists(p):
                os.unlink(p)


def test_a_stale_lock_is_taken():
    log1 = tempfile.NamedTemporaryFile(prefix="nightly-", suffix=".txt", delete=False)
    log2 = tempfile.NamedTemporaryFile(prefix="nightly-", suffix=".txt", delete=False)
    log1.close(); log2.close()
    lock = tempfile.NamedTemporaryFile(prefix="nightly-", suffix=".lock", delete=False)
    lock.close()
    os.unlink(lock.name)
    first = subprocess.Popen(
        ["bash", os.path.join(ROOT, "routines", "nightly-fetch.sh")],
        cwd=ROOT,
        env={**os.environ, "NIGHTLY_TIMEOUT_SECS": "40", "NIGHTLY_STALE_SECS": "1500",
             "NIGHTLY_LOCK": lock.name, "NIGHTLY_LOG": log1.name, "NIGHTLY_HOOK": "sleep 40"},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        for _ in range(50):
            if os.path.exists(lock.name) and open(lock.name).read().strip():
                break
            time.sleep(0.1)
        time.sleep(1.2)
        second = _run({
            "NIGHTLY_TIMEOUT_SECS": "20",
            "NIGHTLY_STALE_SECS": "1",
            "NIGHTLY_LOCK": lock.name,
            "NIGHTLY_LOG": log2.name,
            "NIGHTLY_HOOK": "echo hook-ok",
        }, timeout=15)
        text = (second.stdout or "") + open(log2.name, encoding="utf-8").read()
        check(second.returncode == 0, f"a stale lock is taken and the run finishes (got {second.returncode}, {text!r})")
        check("stale lock" in text, "a stale lock is named in the log")
        check("hook-ok" in text, "the new run does the work")
        first.wait(timeout=5)
        check(first.returncode is not None, "the stale holder is stopped")
    finally:
        if first.poll() is None:
            first.kill()
            first.wait(timeout=5)
        for p in (log1.name, log2.name, lock.name):
            if os.path.exists(p):
                os.unlink(p)


def test_handoff_lock_does_not_wait_forever():
    path = tempfile.NamedTemporaryFile(prefix="handoff-", suffix=".lock", delete=False).name
    os.unlink(path)
    holder = subprocess.Popen(
        [sys.executable, "-c",
         "import sys,time; sys.path.insert(0,'tools'); import crosssite_handoff as h; "
         "fh=h.acquire_lock(sys.argv[1], stale=900, wait=5); print('held', flush=True); time.sleep(30)",
         path],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        line = holder.stdout.readline()
        check(line.startswith("held"), f"holder took the lock ({line!r})")
        started = time.time()
        r = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0,'tools'); import crosssite_handoff as h; "
             "h.acquire_lock(sys.argv[1], stale=900, wait=1)",
             path],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )
        waited = time.time() - started
        check(r.returncode != 0, "a held handoff lock fails")
        check(waited < 8, f"the handoff lock gives up (waited {waited:.1f}s)")
        check("lock held by pid" in (r.stderr + r.stdout), "the message names the holder")
        check(holder.poll() is None, "a fresh handoff holder is not killed")
    finally:
        holder.kill()
        holder.wait(timeout=5)
        if os.path.exists(path):
            os.unlink(path)


def main():
    test_log_while_holding_the_fetch_lock()
    test_requests_get_a_default_timeout()
    test_script_times_out_with_a_message()
    test_a_live_lock_does_not_wait()
    test_a_stale_lock_is_taken()
    test_handoff_lock_does_not_wait_forever()
    if fails:
        print(f"{len(fails)} failed")
        sys.exit(1)
    print("nightly guard ok")


if __name__ == "__main__":
    main()
