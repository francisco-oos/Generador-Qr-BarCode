#!/usr/bin/env python3
"""End-to-end serial protocol simulation for the read-only GRBL bridge (POSIX).

Creates a pseudo-terminal, emulates a tiny GRBL controller on the master side and
runs the same pyserial code used against a SCULPFUN. It proves the application can
open a real serial device abstraction, send only $I/$$ and parse responses without
requiring a physical laser or ever emitting motion/laser commands.
"""
from __future__ import annotations
import json, os, platform, sys, threading, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.machine_bridge import probe_grbl_readonly, serial as pyserial_module

OUT = ROOT/"qa"/"output"; OUT.mkdir(parents=True, exist_ok=True)


def main():
    if os.name != "posix":
        report = {"status":"SKIP", "reason":"PTY simulator is POSIX-only; unit-level fake-serial test covers other OSes."}
        (OUT/"grbl_serial_simulation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report)); return
    import pty
    master, slave = pty.openpty(); slave_name = os.ttyname(slave)
    received=[]; stop=threading.Event(); buffer=b""
    def controller():
        nonlocal buffer
        while not stop.is_set():
            try:
                data=os.read(master, 256)
            except OSError:
                break
            if not data: continue
            buffer += data
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n",1)
                cmd=line.strip().decode(errors="replace")
                if not cmd: continue
                received.append(cmd)
                if cmd == "$I": os.write(master, b"[VER:1.1h.20190825:]\r\nok\r\n")
                elif cmd == "$$": os.write(master, b"$30=1000\r\n$32=1\r\n$130=410\r\n$131=415\r\nok\r\n")
                else: os.write(master, b"error:2\r\n")
    t=threading.Thread(target=controller,daemon=True); t.start()
    try:
        result=probe_grbl_readonly(slave_name,115200,timeout=0.15)
    finally:
        stop.set(); os.close(slave); os.close(master); t.join(timeout=1)
    forbidden = [x for x in received if x not in {"$I","$$"}]
    status = "PASS" if received == ["$I","$$"] and not forbidden and result.get("laser_mode") == 1 else "FAIL"
    report={"status":status,"platform":platform.platform(),"transport_backend":"pyserial" if pyserial_module is not None else "native_posix_fallback","port":slave_name,"commands_received":received,"forbidden_commands":forbidden,"parsed":result}
    (OUT/"grbl_serial_simulation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if status != "PASS": raise SystemExit(1)

if __name__ == "__main__": main()
