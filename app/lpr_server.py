import socket
import threading
import os
from datetime import datetime
from flask import current_app

LPR_PORT = 515
SAVE_FOLDER = "print_jobs"

# Ensure base folder exists
if not os.path.exists(SAVE_FOLDER):
    os.makedirs(SAVE_FOLDER)

def start_lpr_server(flask_app):
    print(f"[🚀] LPR Server listening on port {LPR_PORT}")
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("", LPR_PORT))
    server.listen(5)
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr, flask_app), daemon=True).start()

def handle_client(conn, addr, flask_app):
    print(f"[📥] Connection from {addr}")
    try:
        raw = conn.recv(1024)
        if not raw or raw[0] != 0x02:
            raise ValueError("Invalid LPR command")

        queue_name = raw[1:].split(b'\n', 1)[0].decode('utf-8').strip()
        print(f"[📦] Queue requested: {queue_name}")
        conn.sendall(b'\x00')

        queue_folder = os.path.join(SAVE_FOLDER, queue_name)
        os.makedirs(queue_folder, exist_ok=True)

        # --- Step 1: Receive control file (includes user info) ---
        ctrl_header = conn.recv(1024)
        if not ctrl_header or ctrl_header[0] != 0x02:
            raise ValueError("Missing control header")

        ctrl_size = int(ctrl_header[1:].split(b' ')[0])
        ctrl_filename = ctrl_header.split(b' ')[1].strip().decode('utf-8')

        conn.sendall(b'\x00')  # ACK for control header

        control_content = conn.recv(ctrl_size).decode('utf-8')
        conn.sendall(b'\x00')  # ACK for control content

        # Extract user from control file (line starting with 'P')
        lpr_user = "N/A"
        for line in control_content.splitlines():
            if line.startswith("P"):
                lpr_user = line[1:].strip()
                break

        print(f"[👤] LPR User: {lpr_user}")

        # --- Step 2: Receive data file (the actual print job) ---
        data_header = conn.recv(1024)
        if not data_header or data_header[0] != 0x03:
            raise ValueError("Missing data header")

        data_size = int(data_header[1:].split(b' ')[0])
        data_filename = data_header.split(b' ')[1].strip().decode('utf-8')
        conn.sendall(b'\x00')

        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = os.path.join(queue_folder, f"{timestamp_str}_{addr[0].replace('.', '-')}.raw")

        with open(filepath, "wb") as f:
            bytes_read = 0
            while bytes_read < data_size:
                chunk = conn.recv(min(4096, data_size - bytes_read))
                if not chunk:
                    break
                f.write(chunk)
                bytes_read += len(chunk)

        conn.sendall(b'\x00')
        print(f"[✅] Job saved: {filepath}")

        # --- Save to database ---
        with flask_app.app_context():
            from . import db
            from .models import PrintQueue
            new_job = PrintQueue(
                filename=filepath,
                user=lpr_user,
                user_ip=addr[0],
                timestamp=datetime.utcnow(),
                status='pending',
                queue_name=queue_name
            )
            db.session.add(new_job)
            db.session.commit()
            print("[💾] Job saved to database")

    except Exception as e:
        print(f"[❌] Error handling job: {e}")
    finally:
        conn.close()
