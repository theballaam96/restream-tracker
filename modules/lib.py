import tkinter as tk
from enum import IntEnum, auto
import base64
import os
import json
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class KrosshairViewers(IntEnum):
    not_set = auto()
    player = auto()
    restreamer = auto()
    comms = auto()

class KrosshairState:
    def __init__(self):
        # Kongs
        self.dk = False
        self.diddy = False
        self.lanky = False
        self.tiny = False
        self.chunky = False
        # Moves
        self.blast = False
        self.strong = False
        self.grab = False
        self.rocket = False
        self.spring = False
        self.charge = False
        self.ostand = False
        self.osprint = False
        self.balloon = False
        self.port = False
        self.mini = False
        self.twirl = False
        self.hunky = False
        self.punch = False
        self.gone = False
        # Guns
        self.coconut = False
        self.peanut = False
        self.grape = False
        self.feather = False
        self.pineapple = False
        # Instruments
        self.bongos = False
        self.guitar = False
        self.trombone = False
        self.sax = False
        self.triangle = False
        # Shared
        self.slam = 0
        self.belt = 0
        self.ins_upgrade = 0
        self.melons = 1
        self.homing = False
        self.sniper = False
        self.barrels = False
        self.dive = False
        self.vine = False
        self.orange = False
        self.climb = False
        self.shockwave = False
        self.camera = False
        # Items
        self.bean = False
        self.nintendo_coin = False
        self.rareware_coin = False
        self.key_1 = False
        self.key_2 = False
        self.key_3 = False
        self.key_4 = False
        self.key_5 = False
        self.key_6 = False
        self.key_7 = False
        self.key_8 = False
        self.fairies = 0
        self.medals = 0
        self.crowns = 0
        self.gbs = 0
        self.pearls = 0
        self.rainbow_coins = 0
        self.candy = False
        self.cranky = False
        self.funky = False
        self.snide = False
        # Blueprints
        self.dk_bps = 0
        self.diddy_bps = 0
        self.lanky_bps = 0
        self.tiny_bps = 0
        self.chunky_bps = 0
        self.dk_turns = 0
        self.diddy_turns = 0
        self.lanky_turns = 0
        self.tiny_turns = 0
        self.chunky_turns = 0

    def derive_key(self, password: str, salt: bytes) -> bytes:
        kdf = Scrypt(
            salt=salt,
            length=32,
            n=2**14,
            r=8,
            p=1,
        )
        return kdf.derive(password.encode())

    def encrypt(self, password: str) -> str:
        current_item_state = self.__dict__
        salt = os.urandom(16)
        key = self.derive_key(password, salt)

        aesgcm = AESGCM(key)
        nonce = os.urandom(12)

        plaintext = json.dumps(current_item_state).encode()
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)

        # Store salt + nonce + ciphertext
        blob = salt + nonce + ciphertext
        return base64.b64encode(blob).decode()
    
    def decryptInternals(self, token: str, password: str) -> dict:
        blob = base64.b64decode(token.encode())

        salt = blob[:16]
        nonce = blob[16:28]
        ciphertext = blob[28:]
        key = self.derive_key(password, salt)
        aesgcm = AESGCM(key)

        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode())
    
    def decrypt(self, token: str, password: str) -> str:
        output_dict: dict = self.decryptInternals(token, password)
        self.__dict__.update(output_dict)

class KrosshairLib:
    def log_debug(self, message: str):
        """Log debug message."""
        if self.debug_output:
            self.debug_output.insert(tk.END, f"{message}\n")
            self.debug_output.see(tk.END)
        # print(message)