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

        # Acknowledge receipt of the queue name/command
        try:
            conn.sendall(b'\x00')
            print("[➡️] ACK sent for queue name")
        except Exception as ack_err:
            print(f"[❌] Failed to send queue ACK: {ack_err}")

        queue_folder = os.path.join(SAVE_FOLDER, queue_name)
        os.makedirs(queue_folder, exist_ok=True)

        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{addr[0].replace('.', '-')}.raw"
        filepath = os.path.join(queue_folder, filename)

        print(f"[💾] Saving job to: {filepath}")
        with open(filepath, "wb") as f:
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                f.write(chunk)

        print(f"[✅] Job saved: {filepath}")

        # Inform the client that the job was stored successfully
        try:
            conn.sendall(b'\x00')
            print("[➡️] ACK sent for job saved")
        except Exception as ack_err:
            print(f"[❌] Failed to send final ACK: {ack_err}")

        # Store to DB with Flask app context
        with flask_app.app_context():
            from . import db
            from .models import PrintQueue
            new_job = PrintQueue(
                filename=filepath,
                user_ip=addr[0],  # Use user_ip field from the model
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
