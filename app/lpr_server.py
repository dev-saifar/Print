import socket
import threading
import os
from datetime import datetime

LPR_PORT = 515
SAVE_FOLDER = "print_jobs"

if not os.path.exists(SAVE_FOLDER):
    os.makedirs(SAVE_FOLDER)

def handle_client(conn, addr):
    print(f"[📥] Connection from {addr}")
    try:
        queue_name = conn.recv(1024).decode(errors='ignore')
        print(f"[📦] Queue requested: {queue_name}")

        # Simulate saving a job
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{addr[0].replace('.', '-')}.raw"
        filepath = os.path.join(SAVE_FOLDER, filename)

        with open(filepath, "wb") as f:
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                f.write(chunk)

        print(f"[✅] Job saved: {filepath}")

        # Optional: Insert into DB here
        # from models import PrintQueue, db
        # new_job = PrintQueue(file_name=filename, spool_path=filepath, status='pending')
        # db.session.add(new_job)
        # db.session.commit()

    except Exception as e:
        print(f"[❌] Error handling job: {e}")
    finally:
        conn.close()

def start_lpr_server():
    print(f"[🚀] LPR Server listening on port {LPR_PORT}")
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("", LPR_PORT))
    server.listen(5)
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr)).start()
