#!/usr/bin/env python3
import os
import pty
import select
import sys
import termios
import time

# Full 64-character SHA-256 hashes
BASELINE_HASH = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
TAMPERED_HASH = "8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4"


def run_simulator():
    # Create a pseudo-terminal pair (Master <-> Slave)
    master, slave = pty.openpty()
    slave_name = os.ttyname(slave)

    # Disable terminal ECHO on slave so sent telemetry is not looped back as incoming commands
    try:
        attrs = termios.tcgetattr(slave)
        attrs[3] = attrs[3] & ~termios.ECHO
        termios.tcsetattr(slave, termios.TCSANOW, attrs)
    except Exception as e:
        print(f"[!] Warning: Could not disable pty echo: {e}")

    # Create symlink path for easy UI port selection
    symlink_path = "/tmp/ttyESP32"
    if os.path.exists(symlink_path):
        os.remove(symlink_path)
    os.symlink(slave_name, symlink_path)

    print("=" * 65)
    print("      ESP32 VIRTUAL HARDWARE SERIAL SIMULATOR")
    print("=" * 65)
    print(f"  [+] Virtual Serial Device: {slave_name}")
    print(f"  [+] Symlink Created:       {symlink_path}")
    print("-" * 65)
    print("  -> Open Settings in your C2 Dashboard UI.")
    print(f"  -> Select or enter Port: {symlink_path} (or {slave_name})")
    print("  -> Click 'Connect Device' to begin continuous testing.")
    print("=" * 65 + "\n")

    current_baseline = BASELINE_HASH
    current_hash = BASELINE_HASH

    # Sequence of test conditions
    test_sequence = [
        # (Severity, Event Code, Hash Variant, Interval, Log Message)
        ("INFO", "STATUS_SAFE", "BASELINE", 3.0, "Normal telemetry cycle (Pass)"),
        ("INFO", "STATUS_SAFE", "BASELINE", 3.0, "Normal telemetry cycle (Pass)"),
        ("CRITICAL", "FIRMWARE_TAMPERED", "TAMPERED", 4.0, "ALERT: Simulated memory tamper detected!"),
        ("CRITICAL", "FIRMWARE_TAMPERED", "TAMPERED", 3.0, "ALERT: Tamper persisting in flash memory!"),
        ("WARNING", "SYSTEM_RESTORED", "BASELINE", 3.0, "System self-healing / firmware restored"),
        ("INFO", "STATUS_SAFE", "BASELINE", 3.0, "Integrity verified (Normal)"),
    ]

    seq_idx = 0

    try:
        while True:
            # Check for incoming commands from UI (Reset / Recalibrate)
            rlist, _, _ = select.select([master], [], [], 0.1)
            if rlist:
                incoming = os.read(master, 1024).decode("utf-8", errors="ignore").strip()
                if incoming:
                    print(f"\n[RECEIVED COMMAND FROM UI] -> '{incoming}'")

                    if "RESET" in incoming:
                        print("  [!] RESET COMMAND RECEIVED: Clearing CRITICAL tamper state...")
                        current_baseline = BASELINE_HASH
                        current_hash = BASELINE_HASH
                        seq_idx = 0  # Jump back to safe telemetry state
                        
                        # Send immediate restoration packet
                        resp = f"::ALERT:WARNING:SYSTEM_RESTORED|ORIG:{current_baseline}|CURR:{current_hash}::\n"
                        os.write(master, resp.encode("utf-8"))
                        print("  [+] Sent immediate restoration frame to UI.")

                    elif "RECALIBRATE" in incoming:
                        print("  [!] RECALIBRATE COMMAND RECEIVED: Re-calibrating baseline hash...")
                        # Update simulator baseline to current active hash
                        current_baseline = current_hash
                        seq_idx = 0  # Jump back to safe telemetry state
                        
                        resp = f"::ALERT:INFO:STATUS_SAFE|ORIG:{current_baseline}|CURR:{current_hash}::\n"
                        os.write(master, resp.encode("utf-8"))
                        print(f"  [+] Baseline updated to {current_baseline[:16]}... Sent safe frame.")

            # Resolve current hash based on sequence step
            sev, code, hash_variant, interval, desc = test_sequence[seq_idx]
            if hash_variant == "TAMPERED":
                curr_hash_to_send = TAMPERED_HASH
            else:
                curr_hash_to_send = current_baseline

            # Send telemetry packet to UI
            telemetry_pkt = f"::ALERT:{sev}:{code}|ORIG:{current_baseline}|CURR:{curr_hash_to_send}::\n"
            os.write(master, telemetry_pkt.encode("utf-8"))

            print(f"[SENT TELEMETRY] ({sev}) {code} | Hash: {curr_hash_to_send[:16]}... | {desc}")

            # Advance sequence index
            seq_idx = (seq_idx + 1) % len(test_sequence)
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n[!] Stopping Virtual ESP32 Simulator.")
    finally:
        os.close(master)
        os.close(slave)
        if os.path.exists(symlink_path):
            os.remove(symlink_path)


if __name__ == "__main__":
    run_simulator()