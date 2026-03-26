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
        # GBs
        self.gb_dk_japes = 0
        self.gb_dk_aztec = 0
        self.gb_dk_factory = 0
        self.gb_dk_galleon = 0
        self.gb_dk_fungi = 0
        self.gb_dk_caves = 0
        self.gb_dk_castle = 0
        self.gb_dk_isles = 0
        self.gb_dk_helm = 0
        self.gb_diddy_japes = 0
        self.gb_diddy_aztec = 0
        self.gb_diddy_factory = 0
        self.gb_diddy_galleon = 0
        self.gb_diddy_fungi = 0
        self.gb_diddy_caves = 0
        self.gb_diddy_castle = 0
        self.gb_diddy_isles = 0
        self.gb_diddy_helm = 0
        self.gb_lanky_japes = 0
        self.gb_lanky_aztec = 0
        self.gb_lanky_factory = 0
        self.gb_lanky_galleon = 0
        self.gb_lanky_fungi = 0
        self.gb_lanky_caves = 0
        self.gb_lanky_castle = 0
        self.gb_lanky_isles = 0
        self.gb_lanky_helm = 0
        self.gb_tiny_japes = 0
        self.gb_tiny_aztec = 0
        self.gb_tiny_factory = 0
        self.gb_tiny_galleon = 0
        self.gb_tiny_fungi = 0
        self.gb_tiny_caves = 0
        self.gb_tiny_castle = 0
        self.gb_tiny_isles = 0
        self.gb_tiny_helm = 0
        self.gb_chunky_japes = 0
        self.gb_chunky_aztec = 0
        self.gb_chunky_factory = 0
        self.gb_chunky_galleon = 0
        self.gb_chunky_fungi = 0
        self.gb_chunky_caves = 0
        self.gb_chunky_castle = 0
        self.gb_chunky_isles = 0
        self.gb_chunky_helm = 0

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

    def getGBs(self) -> int:
        dk_gbs = self.gb_dk_japes + self.gb_dk_aztec + self.gb_dk_factory + self.gb_dk_galleon + self.gb_dk_fungi + self.gb_dk_caves + self.gb_dk_castle + self.gb_dk_isles  + self.gb_dk_helm
        diddy_gbs = self.gb_diddy_japes + self.gb_diddy_aztec + self.gb_diddy_factory + self.gb_diddy_galleon + self.gb_diddy_fungi + self.gb_diddy_caves + self.gb_diddy_castle + self.gb_diddy_isles + self.gb_diddy_helm
        lanky_gbs = self.gb_lanky_japes + self.gb_lanky_aztec + self.gb_lanky_factory + self.gb_lanky_galleon + self.gb_lanky_fungi + self.gb_lanky_caves + self.gb_lanky_castle + self.gb_lanky_isles + self.gb_lanky_helm
        tiny_gbs = self.gb_tiny_japes + self.gb_tiny_aztec + self.gb_tiny_factory + self.gb_tiny_galleon + self.gb_tiny_fungi + self.gb_tiny_caves + self.gb_tiny_castle + self.gb_tiny_isles + self.gb_tiny_helm
        chunky_gbs = self.gb_chunky_japes + self.gb_chunky_aztec + self.gb_chunky_factory + self.gb_chunky_galleon + self.gb_chunky_fungi + self.gb_chunky_caves + self.gb_chunky_castle + self.gb_chunky_isles + self.gb_chunky_helm
        return dk_gbs + diddy_gbs + lanky_gbs + tiny_gbs + chunky_gbs