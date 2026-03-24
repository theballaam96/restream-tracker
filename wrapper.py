import os
import subprocess
import threading
import requests
import tkinter as tk
from tkinter import ttk
import time
import re
import random
import string
import json
import socket
import secrets
from modules.connection import KBConnection
from modules.inventory import Inventory

# ================= GLOBAL STATE =================

STATE = {
    "value1": "",
    "value2": ""
}

CLIENTS = {}

BASE_URL = None
SERVER_PORT = None

# ================= CLOUDflared =================

CF_DIR = "./cf"
CF_EXE = os.path.join(CF_DIR, "cloudflared")

def ensure_cloudflared():
    if os.path.exists(CF_EXE):
        return

    os.makedirs(CF_DIR, exist_ok=True)

    url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"

    print("Downloading cloudflared...")
    r = requests.get(url, stream=True)

    with open(CF_EXE, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

    os.chmod(CF_EXE, 0o755)

# ================= SIMPLE SERVER =================

from http.server import BaseHTTPRequestHandler, HTTPServer

class Handler(BaseHTTPRequestHandler):

    def send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path == "/state":
            self.send_response(200)
            self.send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(STATE).encode())

        elif self.path == "/clients":
            self.send_response(200)
            self.send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(CLIENTS).encode())

        else:
            self.send_response(404)
            self.send_cors()
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        data = json.loads(self.rfile.read(length) or "{}")

        if self.path == "/update":
            STATE.update(data)
            self.send_response(200)
            self.send_cors()
            self.end_headers()

        elif self.path == "/presence":
            CLIENTS[data["username"]] = {
                "role": data["role"],
                "last_seen": time.time()
            }
            self.send_response(200)
            self.send_cors()
            self.end_headers()

        else:
            self.send_response(404)
            self.send_cors()
            self.end_headers()

# ================= PORT FIX =================

def find_free_port():
    s = socket.socket()
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

def start_server():
    global SERVER_PORT

    SERVER_PORT = find_free_port()

    server = HTTPServer(("127.0.0.1", SERVER_PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

# ================= UTIL =================

def rand_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

def clear():
    for w in root.winfo_children():
        w.destroy()

# ================= DELAY =================

class DelayBuffer:
    def __init__(self, delay_getter, callback):
        self.delay_getter = delay_getter
        self.callback = callback

    def push(self, data):
        delay = self.delay_getter()

        def run():
            time.sleep(delay)
            self.callback(data)

        threading.Thread(target=run, daemon=True).start()

# ================= HEARTBEAT =================

def start_heartbeat(base_url, username, role):
    def loop():
        while True:
            try:
                requests.post(
                    f"{base_url}/presence",
                    json={"username": username, "role": role}
                )
            except:
                pass
            time.sleep(2)

    threading.Thread(target=loop, daemon=True).start()

# ================= MAIN MENU =================

def main_menu():
    clear()

    ttk.Label(root, text="Select Role", font=("Arial", 18)).pack(pady=20)

    ttk.Button(root, text="Restreamer", command=lambda: restreamer_ui(True)).pack(pady=10)
    ttk.Button(root, text="Player", command=lambda: login_ui("player")).pack(pady=10)
    ttk.Button(root, text="Comms", command=lambda: restreamer_ui(False)).pack(pady=10)

# ================= PASSWORD ==================

def valid_password(pw: str) -> bool:
    if not pw:
        return False

    checksum = sum(ord(c) for c in pw) % 97
    return checksum == 42

def generate_password(player: int, length=24):
    alphabet = string.ascii_letters + string.digits

    # ensure player is 1 or 2
    player_bit = player & 1  # 1 -> 1, 2 -> 0

    # obscure mapping (not obvious at a glance)
    prefix_pool = "Gk7QpR"  # arbitrary mix
    prefix_char = prefix_pool[player_bit::2][0]  
    # player 1 -> index 1 -> different char than player 2

    rest = ''.join(secrets.choice(alphabet) for _ in range(length - 1))

    return prefix_char + rest

def get_player_from_password(pw: str):
    prefix_pool = "Gk7QpR"
    c = pw[0]

    # reverse logic
    if c in prefix_pool[1::2]:
        return 1
    else:
        return 2

def gen_valid_password(player: int) -> str:
    pw = generate_password(player)
    while not valid_password(pw):
        pw = generate_password(player)
    return pw

# ================= RESTREAMER =================

def restreamer_ui(is_restreamer: bool = True):
    clear()

    status = tk.StringVar(value="Idle")
    canvas_color = "green" if is_restreamer else "black"
    canvas_height = 550

    ttk.Label(root, text="Restreamer Host", font=("Arial", 16)).pack()
    ttk.Label(root, textvariable=status).pack()

    server_row = ttk.Frame(root)
    server_row.pack(pady=5)
    url_val = tk.StringVar(value="")
    url_box = tk.Entry(server_row, textvariable=url_val, state="readonly" if is_restreamer else "normal")
    url_box.pack(side="left", padx=5)
    if is_restreamer:
        ttk.Button(
            server_row,
            text="Copy",
            command=lambda: copy_to_clipboard(url_val.get())
        ).pack(side="left", padx=5)

    # generate passwords
    p1_pass = tk.StringVar(value=gen_valid_password(1) if is_restreamer else "")
    p2_pass = tk.StringVar(value=gen_valid_password(2) if is_restreamer else "")

    def copy_to_clipboard(text):
        root.clipboard_clear()
        root.clipboard_append(text)

    # container
    container = ttk.Frame(root)
    container.pack(fill="both", expand=True, padx=10, pady=10)

    container.columnconfigure(0, weight=1)
    container.columnconfigure(1, weight=1)

    # ================= PLAYER 1 =================
    p1_frame = ttk.Frame(container, relief="ridge", padding=10)
    p1_frame.grid(row=0, column=0, sticky="nsew", padx=5)

    ttk.Label(p1_frame, text="Player 1", font=("Arial", 14)).pack(pady=5)

    ttk.Label(p1_frame, text="Password").pack()
    ttk.Entry(p1_frame, textvariable=p1_pass, state="readonly" if is_restreamer else "normal").pack(fill="x", pady=5)

    if is_restreamer:
        btn_row1 = ttk.Frame(p1_frame)
        btn_row1.pack(pady=5)

        ttk.Button(
            btn_row1,
            text="Copy",
            command=lambda: copy_to_clipboard(p1_pass.get())
        ).pack(side="left", padx=5)

        ttk.Button(
            btn_row1,
            text="Regenerate",
            command=lambda: p1_pass.set(gen_valid_password(1))
        ).pack(side="left", padx=5)

    delay_var_1 = tk.DoubleVar(value=0)
    ttk.Label(p1_frame, text="Display Delay").pack()
    ttk.Entry(p1_frame, textvariable=delay_var_1).pack()

    inventory_1 = Inventory()
    p1_canvas = tk.Canvas(p1_frame, height=canvas_height, bg=canvas_color)
    inventory_1.initCanvas(p1_canvas)
    p1_canvas.pack(fill="both", expand=True, pady=10)


    # ================= PLAYER 2 =================
    p2_frame = ttk.Frame(container, relief="ridge", padding=10)
    p2_frame.grid(row=0, column=1, sticky="nsew", padx=5)

    ttk.Label(p2_frame, text="Player 2", font=("Arial", 14)).pack(pady=5)

    ttk.Label(p2_frame, text="Password").pack()
    ttk.Entry(p2_frame, textvariable=p2_pass, state="readonly" if is_restreamer else "normal").pack(fill="x", pady=5)

    if is_restreamer:
        btn_row2 = ttk.Frame(p2_frame)
        btn_row2.pack(pady=5)

        ttk.Button(
            btn_row2,
            text="Copy",
            command=lambda: copy_to_clipboard(p2_pass.get())
        ).pack(side="left", padx=5)

        ttk.Button(
            btn_row2,
            text="Regenerate",
            command=lambda: p2_pass.set(gen_valid_password(2))
        ).pack(side="left", padx=5)

    delay_var_2 = tk.DoubleVar(value=0)
    ttk.Label(p2_frame, text="Display Delay").pack()
    ttk.Entry(p2_frame, textvariable=delay_var_2).pack()

    inventory_2 = Inventory()
    p2_canvas = tk.Canvas(p2_frame, height=canvas_height, bg=canvas_color)
    inventory_2.initCanvas(p2_canvas)
    p2_canvas.pack(fill="both", expand=True, pady=10)

    def log(msg):
        status.set(msg)
        root.update_idletasks()

    def launch():
        def run():
            if is_restreamer:
                log("Starting local server...")
                start_server()

                log(f"Server on port {SERVER_PORT}")

                log("Preparing tunnel...")
                ensure_cloudflared()

                log("Starting tunnel...")

                proc = subprocess.Popen(
                    [CF_EXE, "tunnel", "--url", f"http://127.0.0.1:{SERVER_PORT}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )

                url = None
                start = time.time()

                while True:
                    line = proc.stdout.readline()

                    if line:
                        print(line.strip())
                        m = re.search(r"(https://[a-zA-Z0-9\-]+\.trycloudflare\.com)", line)
                        if m:
                            url = m.group(1)
                            break

                    if time.time() - start > 15:
                        break

                if not url:
                    log("Tunnel failed")
                    return

                url_val.set(url)

            def update_display(v):
                # Display Logic
                try:
                    inventory_1.getItemPacket(v, 1, p1_pass.get())
                    inventory_2.getItemPacket(v, 2, p2_pass.get())
                except Exception as e:
                    print("Error:", e)

            buffer_1 = DelayBuffer(lambda: delay_var_1.get(), update_display)
            buffer_2 = DelayBuffer(lambda: delay_var_2.get(), update_display)

            def poll():
                while True:
                    try:
                        base = f"http://127.0.0.1:{SERVER_PORT}"
                        if not is_restreamer:
                            base = url_val.get()
                        r = requests.get(f"{base}/state")
                        buffer_1.push(r.json())
                        buffer_2.push(r.json())

                        r = requests.get(f"{base}/clients")
                        users = r.json()

                        # users_box.delete(1.0, tk.END)
                        # now = time.time()
                        # for u, d in users.items():
                        #     if now - d["last_seen"] < 5:
                        #         users_box.insert(tk.END, f"{u} ({d['role']})\n")

                    except:
                        pass

                    time.sleep(1)

            threading.Thread(target=poll, daemon=True).start()

            if is_restreamer:
                log("Server ready")
            else:
                log("Connection made")

        threading.Thread(target=run).start()

    ttk.Button(server_row, text="Start Server" if is_restreamer else "Start Connection", command=launch).pack()
    ttk.Button(root, text="Back", command=main_menu).pack()

# ================= LOGIN =================

def login_ui(role):
    clear()

    ttk.Label(root, text=f"{role} login").pack()

    ttk.Label(root, text="Server URL").pack()
    url = ttk.Entry(root)
    url.pack()

    ttk.Label(root, text="Password").pack()
    password = ttk.Entry(root, show="*")
    password.pack()

    status = tk.StringVar()
    ttk.Label(root, textvariable=status, foreground="red").pack()

    def login():
        global BASE_URL

        pw = password.get()

        if not valid_password(pw):
            status.set("Invalid password")
            return

        BASE_URL = url.get().rstrip("/")

        # derive a consistent username from password (optional)
        username = f"user_{abs(hash(pw)) % 10000}"

        start_heartbeat(BASE_URL, username, role)

        if role == "player":
            player_index = get_player_from_password(pw)
            player_ui(player_index, pw)
        else:
            comms_ui()

    ttk.Button(root, text="Continue", command=login).pack()
    ttk.Button(root, text="Back", command=main_menu).pack()
# ================= PLAYER =================

def player_ui(player_index: int, password: str):
    clear()

    ttk.Label(root, text=f"Player {player_index}").pack()
    connection = KBConnection()
    connection.connection_ui(root, root, f"{BASE_URL}/update", player_index, password)

# ================= COMMS =================

def comms_ui():
    clear()

    ttk.Label(root, text="Comms").pack()

    delay = tk.DoubleVar(value=0)
    ttk.Entry(root, textvariable=delay).pack()

    text = tk.Text(root)
    text.pack(fill="both", expand=True)

    def update(v):
        text.delete(1.0, tk.END)
        for k, val in v.items():
            text.insert(tk.END, f"{k}: {val}\n")

    buffer = DelayBuffer(lambda: delay.get(), update)

    def poll():
        while True:
            try:
                r = requests.get(f"{BASE_URL}/state")
                buffer.push(r.json())
            except:
                pass

            time.sleep(0.2)

    threading.Thread(target=poll, daemon=True).start()

    ttk.Button(root, text="Back", command=main_menu).pack()

# ================= APP =================

root = tk.Tk()
root.title("Restream Tool")
root.geometry("900x900")

main_menu()
root.mainloop()