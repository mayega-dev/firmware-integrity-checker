#!/usr/bin/env python3
import time
import serial
import threading
import hashlib

# Configuration
PORT = "/tmp/ttyV1"
BAUD = 115200

# Canonical 64-character SHA-256 Baseline Hash (Threshold)
ORIGINAL_HASH = hashlib.sha256(b"ESP32_FACTORY_FIRMWARE_V1.0.0_TRUSTED_IMAGE").hexdigest()
current_hash = ORIGINAL_HASH
tamper_active = False

def serial_reader(ser):
    global current_hash, tamper_active
    while True:
        try:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if not line:
                continue
            
            print(f"[FIRMWARE RX] {line}")
            
            if "::POLL::" in line:
                send_integrity_status(ser)
            elif "::TAMPER::" in line:
                print("\n[!] TAMPER ATTACK INJECTED! Modifying memory bytes...")
                # Bit-flip the hash to simulate unauthorized flash modification
                current_hash = hashlib.sha256(b"CORRUPTED_FIRMWARE_PAYLOAD_DATA").hexdigest()
                tamper_active = True
                send_integrity_status(ser)
            elif "::RESET::" in line or "::RESTORE::" in line:
                print("\n[*] FIRMWARE RESTORE COMMAND RECEIVED. Re-flashing original image...")
                current_hash = ORIGINAL_HASH
                tamper_active = False
                ser.write(f"::ALERT:INFO:SYSTEM_RESTORED|ORIG:{ORIGINAL_HASH}|CURR:{current_hash}::\n".encode())
        except Exception as e:
            print(f"Read error: {e}")
            break

def send_integrity_status(ser):
    global current_hash, ORIGINAL_HASH
    if current_hash == ORIGINAL_HASH:
        msg = f"::ALERT:INFO:STATUS_SAFE|ORIG:{ORIGINAL_HASH}|CURR:{current_hash}::\n"
        print(f"[STATUS SAFE]\n  Baseline: {ORIGINAL_HASH}\n  Current:  {current_hash}\n")
    else:
        msg = f"::ALERT:CRITICAL:FIRMWARE_TAMPERED|ORIG:{ORIGINAL_HASH}|CURR:{current_hash}::\n"
        print(f"[CRITICAL TAMPER MISMATCH!]\n  Baseline: {ORIGINAL_HASH}\n  Current:  {current_hash}\n")
    
    ser.write(msg.encode())

def main():
    print(f"Starting ESP32 Simulator on {PORT}...")
    print(f"Golden Original Hash (Threshold): {ORIGINAL_HASH}\n")
    
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
    except Exception as e:
        print(f"Failed to open port {PORT}: {e}")
        return

    # Announce identity on boot
    boot_msg = f"::STATUS:VERSION=1.0.0,HW=ESP32-MOCK,ORIG_HASH={ORIGINAL_HASH}::\n"
    ser.write(boot_msg.encode())

    # Start listener thread for incoming POLL/TAMPER/RESET commands
    t = threading.Thread(target=serial_reader, args=(ser,), daemon=True)
    t.start()

    # Continuous background re-hashing loop (every 3 seconds)
    while True:
        send_integrity_status(ser)
        time.sleep(3)

if __name__ == "__main__":
    main()