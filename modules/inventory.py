import tkinter as tk
from tkinter import ttk
from modules.memory_map import DK64MemoryMap
from modules.lib import KrosshairState, KrosshairViewers
from modules.core import KrosshairCore
from enum import IntEnum, auto
from typing import Union
from PIL import Image, ImageTk, ImageEnhance, ImageFont, ImageDraw
from modules.preferences import get_preference, set_preference
from tkinter import colorchooser
import requests

class ItemTypes(IntEnum):
    CountStruct = auto()
    KongBase = auto()
    Flag = auto()

class CountStructItem:
    def __init__(self, offset: int, size: int, is_bitfield: bool, bit: int = 0):
        self.offset = offset
        self.is_bitfield = is_bitfield
        self.size = size
        self.bit = bit

    def getCount(self, core: KrosshairCore):
        populated = core.memory_client.read_u8(DK64MemoryMap.count_struct_pointer) == 0x80
        if not populated:
            return 0
        count_struct_loc = core.memory_client.read_u32(DK64MemoryMap.count_struct_pointer)
        base = count_struct_loc + self.offset
        val = 0
        if self.size == 1:
            val = core.memory_client.read_u8(base)
        elif self.size == 2:
            val = core.memory_client.read_u16(base)
        elif self.size == 4:
            val = core.memory_client.read_u32(base)
        if self.is_bitfield:
            val = (val >> self.bit) & 1
        return val

class KongBaseItem:
    def __init__(self, kong: int, offset: int, size: int, is_bitfield: bool, bit: int = 0):
        self.kong = kong
        self.offset = offset
        self.size = size
        self.is_bitfield = is_bitfield
        self.bit = bit

    def getCount(self, core: KrosshairCore):
        base = 0x807FC950 + (0x5E * self.kong) + self.offset
        val = 0
        if self.size == 1:
            val = core.memory_client.read_u8(base)
        elif self.size == 2:
            val = core.memory_client.read_u16(base)
        elif self.size == 4:
            val = core.memory_client.read_u32(base)
        if self.is_bitfield:
            val = (val >> self.bit) & 1
        return val

class FlagItem:
    def __init__(self, flag_index: int):
        self.flag_index = flag_index

    def getCount(self, core: KrosshairCore):
        flag_offset = self.flag_index >> 3
        flag_shift = self.flag_index & 7
        val = core.memory_client.read_u8(0x807ECEA8 + flag_offset)
        return (val >> flag_shift) & 1

class Item:
    def __init__(self, name: str, item_type: ItemTypes, packet: Union[CountStructItem, KongBaseItem, FlagItem], attr: str):
        self.name = name
        self.item_type = item_type
        self.packet = packet
        self.attr = attr
        self.count = 0

    def getCount(self, core: KrosshairCore) -> int:
        self.count = self.packet.getCount(core)
        return self.count

USE_COLOR_ICONS = True

class IconCondition:
    def __init__(self, icon: str, condition = None, dim_if_true: bool = False):
        self.icon = f"assets/{icon}"
        if condition is None:
            self.condition = lambda: True
        else:
            self.condition = condition
        self.dim_if_true = dim_if_true

class Icon:
    def __init__(self, name: str, x: float, y: int, icon_data: list[IconCondition], display_count: bool = False, count = None, is_compact = False):
        self.name = name
        self.key = name.replace(" ", "_").lower()
        self.x = x
        self.y = y
        self.icon_data = icon_data
        self.display_count = display_count
        if count is None:
            self.count = lambda: 0
        else:
            self.count = count
        self.is_compact = is_compact

class CanvasImageLayer:
    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.items = {}  # key -> image data
        self.state = {}
        self.stored_width = 0
        self.stored_height = 0

    def add_image(self, key, image_path, x, y, dim_factor=0.5, size=None, has_number=False):
        img = Image.open(image_path).convert("RGBA")

        if size:
            img = img.resize(size, Image.LANCZOS)

        if has_number:
            img = self._draw_number(img, 0)

        # Create dimmed version
        dimmed = ImageEnhance.Brightness(img).enhance(dim_factor)

        normal_tk = ImageTk.PhotoImage(img)
        dimmed_tk = ImageTk.PhotoImage(dimmed)

        canvas_id = self.canvas.create_image(
            x, y,
            image=normal_tk,
            anchor="nw"
        )

        self.items[key] = {
            "canvas_id": canvas_id,
            "normal": normal_tk,
            "dimmed": dimmed_tk,
            "state": "normal",
        }
        self.state[key] = {
            "dimmed": False,
            "image": image_path,
            "force_dim_refresh": False,
            "x": x,
            "y": y,
            "number": -32767,
            "size": size,
            "dim_factor": dim_factor
        }

    def _draw_number(self, img, number):
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype("assets/Roboto.ttf", max(12, int(img.width / 2)))

        text = str(number)

        # Use textbbox to get width and height
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = (bbox[3] - bbox[1]) + 5

        padding = 2
        x = img.width - text_width - padding
        y = img.height - text_height - padding

        # Black background rectangle
        draw.rectangle(
            [x - 1, y - 1, x + text_width + 1, y + text_height + 1],
            fill="black"
        )
        draw.text((x, y), text, font=font, fill="white")
        return img


    
    def set_number(self, key, number):
        """Update the number on an existing image."""
        if key not in self.items:
            return
        if number == self.state[key]["number"]:
            return
        self.state[key]["number"] = number
        image_path = self.state[key]["image"]
        item = self.items[key]

        img = Image.open(image_path).convert("RGBA")
        size = self.state[key]["size"]
        if size:
            img = img.resize(size, Image.LANCZOS)

        img = self._draw_number(img, number)

        dim_factor = self.state[key]["dim_factor"]
        dimmed = ImageEnhance.Brightness(img).enhance(dim_factor)
        normal_tk = ImageTk.PhotoImage(img)
        dimmed_tk = ImageTk.PhotoImage(dimmed)

        item["normal"] = normal_tk
        item["dimmed"] = dimmed_tk
        item["number"] = number

        self.canvas.itemconfig(
            item["canvas_id"],
            image=normal_tk if item["state"] == "normal" else dimmed_tk
        )

    def set_dimmed(self, key, dimmed: bool):
        if self.state[key]["dimmed"] == dimmed and not self.state[key]["force_dim_refresh"]:
            return
        self.state[key]["dimmed"] = dimmed
        self.state[key]["force_dim_refresh"] = False
        item = self.items[key]
        item["state"] = "dimmed" if dimmed else "normal"

        self.canvas.itemconfig(
            item["canvas_id"],
            image=item["dimmed"] if dimmed else item["normal"]
        )

    def set_background(self, color):
        self.canvas.configure(bg=color)

    def set_canvas_size(self, width, height):
        if width == self.stored_width and height == self.stored_height:
            return
        self.canvas.config(width=width, height=height)

    def swap_image(self, key, new_image_path, dim_factor=0.5, size=None, has_number=False):
        """Replace image but keep position + canvas ID"""
        if self.state[key]["image"] == new_image_path:
            return
        self.state[key]["image"] = new_image_path
        self.state[key]["force_dim_refresh"] = True  # Force dim change
        img = Image.open(new_image_path).convert("RGBA")

        if size:
            img = img.resize(size, Image.LANCZOS)

        if has_number:
            img = self._draw_number(img, 0)

        dimmed = ImageEnhance.Brightness(img).enhance(dim_factor)

        normal_tk = ImageTk.PhotoImage(img)
        dimmed_tk = ImageTk.PhotoImage(dimmed)

        item = self.items[key]
        item["normal"] = normal_tk
        item["dimmed"] = dimmed_tk

        self.canvas.itemconfig(
            item["canvas_id"],
            image=normal_tk if item["state"] == "normal" else dimmed_tk
        )

    def set_position(self, key, x, y):
        """Set absolute position of an image on the canvas."""
        if self.state[key]["x"] == x and self.state[key]["y"] == y:
            return
        if key not in self.items:
            return

        canvas_id = self.items[key]["canvas_id"]
        self.canvas.coords(canvas_id, x, y)


class Controls(tk.Frame):
    """UI controls that operate on ImageCanvas"""

    def __init__(self, parent, image_canvas: CanvasImageLayer):
        super().__init__(parent)
        self.image_canvas = image_canvas

        self.ui_scale = tk.DoubleVar(value=get_preference("ui_scale") / 20)
        self.use_color_icons = tk.BooleanVar(value=get_preference("color_mode"))

        # UI Scale
        tk.Label(self, text="UI Scale").pack(side="left")
        tk.Scale(
            self,
            from_=0.5, to=3.0,
            resolution=0.1,
            orient="horizontal",
            variable=self.ui_scale,
            command=self.on_scale
        ).pack(side="left")

        # Toggle
        tk.Checkbutton(
            self,
            text="Use color icons",
            variable=self.use_color_icons,
            command=self.on_toggle
        ).pack(side="left", padx=10)

        # Background color
        tk.Button(
            self,
            text="Canvas Background",
            command=self.pick_bg_color
        ).pack(side="left")

    def on_scale(self, _):
        set_preference("ui_scale", self.ui_scale.get() * 20)
        ui_scale = get_preference("ui_scale")
        self.image_canvas.set_canvas_size(7 * ui_scale, 10 * ui_scale)
        # Re-add all images
        for v in self.image_canvas.state.values():
            v["image"] = ""

    def on_toggle(self):
        global USE_COLOR_ICONS

        USE_COLOR_ICONS = self.use_color_icons.get()
        set_preference("color_mode", USE_COLOR_ICONS)

    def pick_bg_color(self):
        color = colorchooser.askcolor()[1]
        if color:
            set_preference("background_color", color)
            self.image_canvas.set_background(color)

COMPACT_SCALING = 7 / 8
WIDE_SCALING = 7 / 4

class Inventory(KrosshairCore):
    def __init__(self):
        """Initialize with given parameters."""

        self.layer = None
        self.items_frame = None
        self.states: list[KrosshairState] = [KrosshairState()]
        self.selected_state_index = 0
        self.active_state = self.states[self.selected_state_index]
        # Item database - separated into moves and items
        self.item_data = [
            # Kongs
            Item("Donkey Kong", ItemTypes.CountStruct, CountStructItem(0xB, 1, True, 0), "dk"),
            Item("Diddy Kong", ItemTypes.CountStruct, CountStructItem(0xB, 1, True, 1), "diddy"),
            Item("Lanky Kong", ItemTypes.CountStruct, CountStructItem(0xB, 1, True, 2), "lanky"),
            Item("Tiny Kong", ItemTypes.CountStruct, CountStructItem(0xB, 1, True, 3), "tiny"),
            Item("Chunky Kong", ItemTypes.CountStruct, CountStructItem(0xB, 1, True, 4), "chunky"),
            # All Kong Moves
            Item("Barrel Throwing", ItemTypes.CountStruct, CountStructItem(0x18, 1, True, 5), "barrels"),
            Item("Orange Throwing", ItemTypes.CountStruct, CountStructItem(0x18, 1, True, 6), "orange"),
            Item("Vine Swinging", ItemTypes.CountStruct, CountStructItem(0x18, 1, True, 4), "vine"),
            Item("Diving", ItemTypes.CountStruct, CountStructItem(0x18, 1, True, 7), "dive"),
            Item("Climbing", ItemTypes.Flag, FlagItem(0x29F), "climb"),
            Item("Camera", ItemTypes.CountStruct, CountStructItem(0x18, 1, True, 3), "camera"),
            Item("Shockwave", ItemTypes.CountStruct, CountStructItem(0x18, 1, True, 2), "shockwave"),
            Item("Slam", ItemTypes.KongBase, KongBaseItem(0, 1, 1, False), "slam"),
            Item("Homing", ItemTypes.KongBase, KongBaseItem(0, 2, 1, True, 1), "homing"),
            Item("Sniper", ItemTypes.KongBase, KongBaseItem(0, 2, 1, True, 2), "sniper"),
            # Guns
            Item("Coconut", ItemTypes.KongBase, KongBaseItem(0, 2, 1, True, 0), "coconut"),
            Item("Peanut", ItemTypes.KongBase, KongBaseItem(1, 2, 1, True, 0), "peanut"),
            Item("Grape", ItemTypes.KongBase, KongBaseItem(2, 2, 1, True, 0), "grape"),
            Item("Feather", ItemTypes.KongBase, KongBaseItem(3, 2, 1, True, 0), "feather"),
            Item("Pineapple", ItemTypes.KongBase, KongBaseItem(4, 2, 1, True, 0), "pineapple"),
            # Instruments
            Item("Bongos", ItemTypes.KongBase, KongBaseItem(0, 4, 1, True, 0), "bongos"),
            Item("Guitar", ItemTypes.KongBase, KongBaseItem(1, 4, 1, True, 0), "guitar"),
            Item("Trombone", ItemTypes.KongBase, KongBaseItem(2, 4, 1, True, 0), "trombone"),
            Item("Sax", ItemTypes.KongBase, KongBaseItem(3, 4, 1, True, 0), "sax"),
            Item("Triangle", ItemTypes.KongBase, KongBaseItem(4, 4, 1, True, 0), "triangle"),
            # Special Moves
            Item("Blast", ItemTypes.KongBase, KongBaseItem(0, 0, 1, True, 0), "blast"),
            Item("Charge", ItemTypes.KongBase, KongBaseItem(1, 0, 1, True, 0), "charge"),
            Item("Orangstand", ItemTypes.KongBase, KongBaseItem(2, 0, 1, True, 0), "ostand"),
            Item("Mini", ItemTypes.KongBase, KongBaseItem(3, 0, 1, True, 0), "mini"),
            Item("Hunky", ItemTypes.KongBase, KongBaseItem(4, 0, 1, True, 0), "hunky"),
            Item("Strong", ItemTypes.KongBase, KongBaseItem(0, 0, 1, True, 1), "strong"),
            Item("Rocket", ItemTypes.KongBase, KongBaseItem(1, 0, 1, True, 1), "rocket"),
            Item("Balloon", ItemTypes.KongBase, KongBaseItem(2, 0, 1, True, 1), "balloon"),
            Item("Twirl", ItemTypes.KongBase, KongBaseItem(3, 0, 1, True, 1), "twirl"),
            Item("Punch", ItemTypes.KongBase, KongBaseItem(4, 0, 1, True, 1), "punch"),
            Item("Grab", ItemTypes.KongBase, KongBaseItem(0, 0, 1, True, 2), "grab"),
            Item("Spring", ItemTypes.KongBase, KongBaseItem(1, 0, 1, True, 2), "spring"),
            Item("Sprint", ItemTypes.KongBase, KongBaseItem(2, 0, 1, True, 2), "osprint"),
            Item("Port", ItemTypes.KongBase, KongBaseItem(3, 0, 1, True, 2), "port"),
            Item("Gone", ItemTypes.KongBase, KongBaseItem(4, 0, 1, True, 2), "gone"),
            # Keys
            Item("Key 1", ItemTypes.CountStruct, CountStructItem(0xA, 1, True, 0), "key_1"),
            Item("Key 2", ItemTypes.CountStruct, CountStructItem(0xA, 1, True, 1), "key_2"),
            Item("Key 3", ItemTypes.CountStruct, CountStructItem(0xA, 1, True, 2), "key_3"),
            Item("Key 4", ItemTypes.CountStruct, CountStructItem(0xA, 1, True, 3), "key_4"),
            Item("Key 5", ItemTypes.CountStruct, CountStructItem(0xA, 1, True, 4), "key_5"),
            Item("Key 6", ItemTypes.CountStruct, CountStructItem(0xA, 1, True, 5), "key_6"),
            Item("Key 7", ItemTypes.CountStruct, CountStructItem(0xA, 1, True, 6), "key_7"),
            Item("Key 8", ItemTypes.CountStruct, CountStructItem(0xA, 1, True, 7), "key_8"),
            # Blueprints
            Item("DK Blueprints", ItemTypes.CountStruct, CountStructItem(0x0, 1, False), "dk_bps"),
            Item("Diddy Blueprints", ItemTypes.CountStruct, CountStructItem(0x1, 1, False), "diddy_bps"),
            Item("Lanky Blueprints", ItemTypes.CountStruct, CountStructItem(0x2, 1, False), "lanky_bps"),
            Item("Tiny Blueprints", ItemTypes.CountStruct, CountStructItem(0x3, 1, False), "tiny_bps"),
            Item("Chunky Blueprints", ItemTypes.CountStruct, CountStructItem(0x4, 1, False), "chunky_bps"),
            Item("DK Turn-Ins", ItemTypes.CountStruct, CountStructItem(0x19, 1, False), "dk_turns"),
            Item("Diddy Turn-Ins", ItemTypes.CountStruct, CountStructItem(0x1A, 1, False), "diddy_turns"),
            Item("Lanky Turn-Ins", ItemTypes.CountStruct, CountStructItem(0x1B, 1, False), "lanky_turns"),
            Item("Tiny Turn-Ins", ItemTypes.CountStruct, CountStructItem(0x1C, 1, False), "tiny_turns"),
            Item("Chunky Turn-Ins", ItemTypes.CountStruct, CountStructItem(0x1D, 1, False), "chunky_turns"),
            # Shopkeepers
            Item("Cranky", ItemTypes.Flag, FlagItem(0x3C2), "cranky"),
            Item("Funky", ItemTypes.Flag, FlagItem(0x3C3), "funky"),
            Item("Candy", ItemTypes.Flag, FlagItem(0x3C4), "candy"),
            Item("Snide", ItemTypes.Flag, FlagItem(0x3C5), "snide"),
            # Items
            Item("Bean", ItemTypes.CountStruct, CountStructItem(0xD, 1, True, 5), "bean"),
            Item("Nintendo Coin", ItemTypes.CountStruct, CountStructItem(0xD, 1, True, 7), "nintendo_coin"),
            Item("Rareware Coin", ItemTypes.CountStruct, CountStructItem(0xD, 1, True, 6), "rareware_coin"),
            Item("Crowns", ItemTypes.CountStruct, CountStructItem(0xC, 1, False), "crowns"),
            Item("Medals", ItemTypes.CountStruct, CountStructItem(0xE, 1, False), "medals"),
            Item("Pearls", ItemTypes.CountStruct, CountStructItem(0xF, 1, False), "pearls"),
            Item("Fairies", ItemTypes.CountStruct, CountStructItem(0x10, 1, False), "fairies"),
            Item("Rainbow Coins", ItemTypes.CountStruct, CountStructItem(0x11, 1, False), "rainbow_coins"),
        ]
        for level_index, level in enumerate(["japes", "aztec", "factory", "galleon", "fungi", "caves", "castle", "isles", "helm"]):
            for kong_index, kong in enumerate(["dk", "diddy", "lanky", "tiny", "chunky"]):
                self.item_data.append(
                    Item(f"{kong} {level} GBs", ItemTypes.KongBase, KongBaseItem(kong_index, 0x42 + (2 * level_index), 2, False), f"gb_{kong}_{level}")
                )

        self.icons = [
            Icon("Donkey Kong", 0, 0, [
                IconCondition("dk/donkey.png", lambda: not self.active_state.dk, True),
                IconCondition("dk/donkey.png", lambda: self.active_state.dk, False),
            ]),
            Icon("Diddy Kong", 0, 1, [
                IconCondition("diddy/diddy.png", lambda: not self.active_state.diddy, True),
                IconCondition("diddy/diddy.png", lambda: self.active_state.diddy, False),
            ]),
            Icon("Lanky Kong", 0, 2, [
                IconCondition("lanky/lanky.png", lambda: not self.active_state.lanky, True),
                IconCondition("lanky/lanky.png", lambda: self.active_state.lanky, False),
            ]),
            Icon("Tiny Kong", 0, 3, [
                IconCondition("tiny/tiny.png", lambda: not self.active_state.tiny, True),
                IconCondition("tiny/tiny.png", lambda: self.active_state.tiny, False),
            ]),
            Icon("Chunky Kong", 0, 4, [
                IconCondition("chunky/chunky.png", lambda: not self.active_state.chunky, True),
                IconCondition("chunky/chunky.png", lambda: self.active_state.chunky, False),
            ]),
            Icon("Barrel Throwing", 3, 5, [
                IconCondition("all_kong/barrel_throwing.png", lambda: not self.active_state.barrels, True),
                IconCondition("all_kong/barrel_throwing.png", lambda: self.active_state.barrels, False),
            ]),
            Icon("Orange Throwing", 2, 5, [
                IconCondition("all_kong/orange_throwing.png", lambda: not self.active_state.orange, True),
                IconCondition("all_kong/orange_throwing.png", lambda: self.active_state.orange, False),
            ]),
            Icon("Vine Swinging", 4, 5, [
                IconCondition("all_kong/vine_swinging.png", lambda: not self.active_state.vine, True),
                IconCondition("all_kong/vine_swinging.png", lambda: self.active_state.vine, False),
            ]),
            Icon("Diving", 1, 5, [
                IconCondition("all_kong/diving.png", lambda: not self.active_state.dive, True),
                IconCondition("all_kong/diving.png", lambda: self.active_state.dive, False),
            ]),
            Icon("Climbing", 5, 5, [
                IconCondition("all_kong/climbing.png", lambda: not self.active_state.climb, True),
                IconCondition("all_kong/climbing.png", lambda: self.active_state.climb, False),
            ]),
            Icon("Camera", 2, 6, [
                IconCondition("shockwave_camera/film.png", lambda: not self.active_state.camera, True),
                IconCondition("shockwave_camera/film.png", lambda: self.active_state.camera, False),
            ]),
            Icon("Shockwave", 3, 6, [
                IconCondition("shockwave_camera/shockwave.png", lambda: not self.active_state.shockwave, True),
                IconCondition("shockwave_camera/shockwave.png", lambda: self.active_state.shockwave, False),
            ]),
            # Icon("Camera_Shockwave", 6 * COMPACT_SCALING, 5, [
            #     IconCondition("shockwave_camera/filmwave.png", lambda: not self.active_state.camera and not self.active_state.shockwave, True),
            #     IconCondition("shockwave_camera/filmwave.png", lambda: self.active_state.camera and self.active_state.shockwave, False),
            #     IconCondition("shockwave_camera/fairycamonly.png", lambda: self.active_state.camera and not self.active_state.shockwave, False),
            #     IconCondition("shockwave_camera/shockwaveonly.png", lambda: not self.active_state.camera and self.active_state.shockwave, False),
            # ], is_compact=True),
            Icon("Slam", 0, 5, [
                IconCondition("slam/slam1.png", lambda: self.active_state.slam < 1, True),
                IconCondition("slam/slam1.png", lambda: self.active_state.slam == 1, False),
                IconCondition("slam/slam2.png", lambda: self.active_state.slam == 2, False),
                IconCondition("slam/slam3.png", lambda: self.active_state.slam > 2, False),
            ]),
            Icon("GBs", 6, 5, [
                IconCondition("plural_items/gb.png", lambda: self.active_state.getGBs() <= 0, True),
                IconCondition("plural_items/gb.png", lambda: self.active_state.getGBs() > 0, False),
            ], True, lambda: self.active_state.getGBs()),
            Icon("Homing", 0, 6, [
                IconCondition("homing_sniper/homing_ammo.png", lambda: not self.active_state.homing, True),
                IconCondition("homing_sniper/homing_ammo.png", lambda: self.active_state.homing, False),
            ]),
            Icon("Sniper", 1, 6, [
                IconCondition("homing_sniper/sniper_scope.png", lambda: not self.active_state.sniper, True),
                IconCondition("homing_sniper/sniper_scope.png", lambda: self.active_state.sniper, False),
            ]),
            # Icon("Homing_Sniper", 7 * COMPACT_SCALING, 5, [
            #     IconCondition("homing_sniper/homingscope.png", lambda: not self.active_state.homing and not self.active_state.sniper, True),
            #     IconCondition("homing_sniper/homingscope.png", lambda: self.active_state.homing and self.active_state.sniper, False),
            #     IconCondition("homing_sniper/homingonly.png", lambda: self.active_state.homing and not self.active_state.sniper, False),
            #     IconCondition("homing_sniper/scopeonly.png", lambda: not self.active_state.homing and self.active_state.sniper, False),
            # ], is_compact=True),
            Icon("Coconut", 1, 0, [
                IconCondition("dk/dk_gun.png", lambda: not self.active_state.coconut, True),
                IconCondition("dk/dk_gun.png", lambda: self.active_state.coconut, False),
            ]),
            Icon("Peanut", 1, 1, [
                IconCondition("diddy/diddy_gun.png", lambda: not self.active_state.peanut, True),
                IconCondition("diddy/diddy_gun.png", lambda: self.active_state.peanut, False),
            ]),
            Icon("Grape", 1, 2, [
                IconCondition("lanky/lanky_gun.png", lambda: not self.active_state.grape, True),
                IconCondition("lanky/lanky_gun.png", lambda: self.active_state.grape, False),
            ]),
            Icon("Feather", 1, 3, [
                IconCondition("tiny/tiny_gun.png", lambda: not self.active_state.feather, True),
                IconCondition("tiny/tiny_gun.png", lambda: self.active_state.feather, False),
            ]),
            Icon("Pineapple", 1, 4, [
                IconCondition("chunky/chunky_gun.png", lambda: not self.active_state.pineapple, True),
                IconCondition("chunky/chunky_gun.png", lambda: self.active_state.pineapple, False),
            ]),
            Icon("Bongos", 2, 0, [
                IconCondition("dk/dk_inst.png", lambda: not self.active_state.bongos, True),
                IconCondition("dk/dk_inst.png", lambda: self.active_state.bongos, False),
            ]),
            Icon("Guitar", 2, 1, [
                IconCondition("diddy/diddy_inst.png", lambda: not self.active_state.guitar, True),
                IconCondition("diddy/diddy_inst.png", lambda: self.active_state.guitar, False),
            ]),
            Icon("Trombone", 2, 2, [
                IconCondition("lanky/lanky_inst.png", lambda: not self.active_state.trombone, True),
                IconCondition("lanky/lanky_inst.png", lambda: self.active_state.trombone, False),
            ]),
            Icon("Sax", 2, 3, [
                IconCondition("tiny/tiny_inst.png", lambda: not self.active_state.sax, True),
                IconCondition("tiny/tiny_inst.png", lambda: self.active_state.sax, False),
            ]),
            Icon("Triangle", 2, 4, [
                IconCondition("chunky/chunky_inst.png", lambda: not self.active_state.triangle, True),
                IconCondition("chunky/chunky_inst.png", lambda: self.active_state.triangle, False),
            ]),
            Icon("Blast", 4, 0, [
                IconCondition("dk/dkpad.png", lambda: not self.active_state.blast and not USE_COLOR_ICONS, True),
                IconCondition("dk/dkpad.png", lambda: self.active_state.blast and not USE_COLOR_ICONS, False),
                IconCondition("dk/dkpad_c.png", lambda: not self.active_state.blast and USE_COLOR_ICONS, True),
                IconCondition("dk/dkpad_c.png", lambda: self.active_state.blast and USE_COLOR_ICONS, False),
            ]),
            Icon("Charge", 3, 1, [
                IconCondition("diddy/diddy_move.png", lambda: not self.active_state.charge, True),
                IconCondition("diddy/diddy_move.png", lambda: self.active_state.charge, False),
            ]),
            Icon("Orangstand", 3, 2, [
                IconCondition("lanky/lanky_move.png", lambda: not self.active_state.ostand, True),
                IconCondition("lanky/lanky_move.png", lambda: self.active_state.ostand, False),
            ]),
            Icon("Mini", 5, 3, [
                IconCondition("tiny/tinybarrel.png", lambda: not self.active_state.mini and not USE_COLOR_ICONS, True),
                IconCondition("tiny/tinybarrel.png", lambda: self.active_state.mini and not USE_COLOR_ICONS, False),
                IconCondition("tiny/tinybarrel_c.png", lambda: not self.active_state.mini and USE_COLOR_ICONS, True),
                IconCondition("tiny/tinybarrel_c.png", lambda: self.active_state.mini and USE_COLOR_ICONS, False),
            ]),
            Icon("Hunky", 5, 4, [
                IconCondition("chunky/chunkybarrel.png", lambda: not self.active_state.hunky and not USE_COLOR_ICONS, True),
                IconCondition("chunky/chunkybarrel.png", lambda: self.active_state.hunky and not USE_COLOR_ICONS, False),
                IconCondition("chunky/chunkybarrel_c.png", lambda: not self.active_state.hunky and USE_COLOR_ICONS, True),
                IconCondition("chunky/chunkybarrel_c.png", lambda: self.active_state.hunky and USE_COLOR_ICONS, False),
            ]),
            Icon("Strong", 5, 0, [
                IconCondition("dk/dkbarrel.png", lambda: not self.active_state.strong and not USE_COLOR_ICONS, True),
                IconCondition("dk/dkbarrel.png", lambda: self.active_state.strong and not USE_COLOR_ICONS, False),
                IconCondition("dk/dkbarrel_c.png", lambda: not self.active_state.strong and USE_COLOR_ICONS, True),
                IconCondition("dk/dkbarrel_c.png", lambda: self.active_state.strong and USE_COLOR_ICONS, False),
            ]),
            Icon("Rocket", 5, 1, [
                IconCondition("diddy/diddybarrel.png", lambda: not self.active_state.rocket and not USE_COLOR_ICONS, True),
                IconCondition("diddy/diddybarrel.png", lambda: self.active_state.rocket and not USE_COLOR_ICONS, False),
                IconCondition("diddy/diddybarrel_c.png", lambda: not self.active_state.rocket and USE_COLOR_ICONS, True),
                IconCondition("diddy/diddybarrel_c.png", lambda: self.active_state.rocket and USE_COLOR_ICONS, False),
            ]),
            Icon("Balloon", 4, 2, [
                IconCondition("lanky/lankypad.png", lambda: not self.active_state.balloon, True),
                IconCondition("lanky/lankypad.png", lambda: self.active_state.balloon, False),
            ]),
            Icon("Twirl", 3, 3, [
                IconCondition("tiny/tiny_move.png", lambda: not self.active_state.twirl, True),
                IconCondition("tiny/tiny_move.png", lambda: self.active_state.twirl, False),
            ]),
            Icon("Punch", 3, 4, [
                IconCondition("chunky/chunky_move.png", lambda: not self.active_state.punch, True),
                IconCondition("chunky/chunky_move.png", lambda: self.active_state.punch, False),
            ]),
            Icon("Grab", 3, 0, [
                IconCondition("dk/dk_move.png", lambda: not self.active_state.grab, True),
                IconCondition("dk/dk_move.png", lambda: self.active_state.grab, False),
            ]),
            Icon("Spring", 4, 1, [
                IconCondition("diddy/diddypad.png", lambda: not self.active_state.spring and not USE_COLOR_ICONS, True),
                IconCondition("diddy/diddypad.png", lambda: self.active_state.spring and not USE_COLOR_ICONS, False),
                IconCondition("diddy/diddypad_c.png", lambda: not self.active_state.spring and USE_COLOR_ICONS, True),
                IconCondition("diddy/diddypad_c.png", lambda: self.active_state.spring and USE_COLOR_ICONS, False),
            ]),
            Icon("Sprint", 5, 2, [
                IconCondition("lanky/lankybarrel.png", lambda: not self.active_state.osprint and not USE_COLOR_ICONS, True),
                IconCondition("lanky/lankybarrel.png", lambda: self.active_state.osprint and not USE_COLOR_ICONS, False),
                IconCondition("lanky/lankybarrel_c.png", lambda: not self.active_state.osprint and USE_COLOR_ICONS, True),
                IconCondition("lanky/lankybarrel_c.png", lambda: self.active_state.osprint and USE_COLOR_ICONS, False),
            ]),
            Icon("Port", 4, 3, [
                IconCondition("tiny/tinypad.png", lambda: not self.active_state.port and not USE_COLOR_ICONS, True),
                IconCondition("tiny/tinypad.png", lambda: self.active_state.port and not USE_COLOR_ICONS, False),
                IconCondition("tiny/tinypad_c.png", lambda: not self.active_state.port and USE_COLOR_ICONS, True),
                IconCondition("tiny/tinypad_c.png", lambda: self.active_state.port and USE_COLOR_ICONS, False),
            ]),
            Icon("Gone", 4, 4, [
                IconCondition("chunky/chunkypad.png", lambda: not self.active_state.gone and not USE_COLOR_ICONS, True),
                IconCondition("chunky/chunkypad.png", lambda: self.active_state.gone and not USE_COLOR_ICONS, False),
                IconCondition("chunky/chunkypad_c.png", lambda: not self.active_state.gone and USE_COLOR_ICONS, True),
                IconCondition("chunky/chunkypad_c.png", lambda: self.active_state.gone and USE_COLOR_ICONS, False),
            ]),
            Icon("Key 1", 0.25 * WIDE_SCALING, 9, [
                IconCondition("keys/k1.png", lambda: not self.active_state.key_1, True),
                IconCondition("keys/k1.png", lambda: self.active_state.key_1, False),
            ]),
            Icon("Key 2", 1.25 * WIDE_SCALING, 9, [
                IconCondition("keys/k2.png", lambda: not self.active_state.key_2, True),
                IconCondition("keys/k2.png", lambda: self.active_state.key_2, False),
            ]),
            Icon("Key 3", 2.25 * WIDE_SCALING, 9, [
                IconCondition("keys/k3.png", lambda: not self.active_state.key_3, True),
                IconCondition("keys/k3.png", lambda: self.active_state.key_3, False),
            ]),
            Icon("Key 4", 3.25 * WIDE_SCALING, 9, [
                IconCondition("keys/k4.png", lambda: not self.active_state.key_4, True),
                IconCondition("keys/k4.png", lambda: self.active_state.key_4, False),
            ]),
            Icon("Key 5", 0.25 * WIDE_SCALING, 10, [
                IconCondition("keys/k5.png", lambda: not self.active_state.key_5, True),
                IconCondition("keys/k5.png", lambda: self.active_state.key_5, False),
            ]),
            Icon("Key 6", 1.25 * WIDE_SCALING, 10, [
                IconCondition("keys/k6.png", lambda: not self.active_state.key_6, True),
                IconCondition("keys/k6.png", lambda: self.active_state.key_6, False),
            ]),
            Icon("Key 7", 2.25 * WIDE_SCALING, 10, [
                IconCondition("keys/k7.png", lambda: not self.active_state.key_7, True),
                IconCondition("keys/k7.png", lambda: self.active_state.key_7, False),
            ]),
            Icon("Key 8", 3.25 * WIDE_SCALING, 10, [
                IconCondition("keys/k8.png", lambda: not self.active_state.key_8, True),
                IconCondition("keys/k8.png", lambda: self.active_state.key_8, False),
            ]),
            Icon("Cranky", 0.25 * WIDE_SCALING, 7, [
                IconCondition("shopkeepers/cranky.png", lambda: not self.active_state.cranky, True),
                IconCondition("shopkeepers/cranky.png", lambda: self.active_state.cranky, False),
            ]),
            Icon("Funky", 1.25 * WIDE_SCALING, 7, [
                IconCondition("shopkeepers/funky.png", lambda: not self.active_state.funky, True),
                IconCondition("shopkeepers/funky.png", lambda: self.active_state.funky, False),
            ]),
            Icon("Candy", 2.25 * WIDE_SCALING, 7, [
                IconCondition("shopkeepers/candy.png", lambda: not self.active_state.candy, True),
                IconCondition("shopkeepers/candy.png", lambda: self.active_state.candy, False),
            ]),
            Icon("Snide", 3.25 * WIDE_SCALING, 7, [
                IconCondition("shopkeepers/snide.png", lambda: not self.active_state.snide, True),
                IconCondition("shopkeepers/snide.png", lambda: self.active_state.snide, False),
            ]),
            Icon("Donkey Blueprints", 6, 0, [
                IconCondition("dk/dk_bp.png", lambda: self.active_state.dk_bps == self.active_state.dk_turns, True),
                IconCondition("dk/dk_bp.png", lambda: self.active_state.dk_bps != self.active_state.dk_turns, False),
            ], True, lambda: self.active_state.dk_bps - self.active_state.dk_turns),
            Icon("Diddy Blueprints", 6, 1, [
                IconCondition("diddy/diddy_bp.png", lambda: self.active_state.diddy_bps == self.active_state.diddy_turns, True),
                IconCondition("diddy/diddy_bp.png", lambda: self.active_state.diddy_bps != self.active_state.diddy_turns, False),
            ], True, lambda: self.active_state.diddy_bps - self.active_state.diddy_turns),
            Icon("Lanky Blueprints", 6, 2, [
                IconCondition("lanky/lanky_bp.png", lambda: self.active_state.lanky_bps == self.active_state.lanky_turns, True),
                IconCondition("lanky/lanky_bp.png", lambda: self.active_state.lanky_bps != self.active_state.lanky_turns, False),
            ], True, lambda: self.active_state.lanky_bps - self.active_state.lanky_turns),
            Icon("Tiny Blueprints", 6, 3, [
                IconCondition("tiny/tiny_bp.png", lambda: self.active_state.tiny_bps == self.active_state.tiny_turns, True),
                IconCondition("tiny/tiny_bp.png", lambda: self.active_state.tiny_bps != self.active_state.tiny_turns, False),
            ], True, lambda: self.active_state.tiny_bps - self.active_state.tiny_turns),
            Icon("Chunky Blueprints", 6, 4, [
                IconCondition("chunky/chunky_bp.png", lambda: self.active_state.chunky_bps == self.active_state.chunky_turns, True),
                IconCondition("chunky/chunky_bp.png", lambda: self.active_state.chunky_bps != self.active_state.chunky_turns, False),
            ], True, lambda: self.active_state.chunky_bps - self.active_state.chunky_turns),
            Icon("Bean", 0, 8, [
                IconCondition("all_kong/bean.png", lambda: not self.active_state.bean, True),
                IconCondition("all_kong/bean.png", lambda: self.active_state.bean, False),
            ]),
            Icon("Company Coins", 1, 8, [
                IconCondition("company_coins/shared_coin.png", lambda: not self.active_state.nintendo_coin and not self.active_state.rareware_coin, True),
                IconCondition("company_coins/shared_coin.png", lambda: self.active_state.nintendo_coin and self.active_state.rareware_coin, False),
                IconCondition("company_coins/nin_only.png", lambda: self.active_state.nintendo_coin and not self.active_state.rareware_coin, False),
                IconCondition("company_coins/rw_only.png", lambda: not self.active_state.nintendo_coin and self.active_state.rareware_coin, False),
            ]),
            Icon("Crowns", 4, 8, [
                IconCondition("plural_items/crown.png", lambda: self.active_state.crowns < 1, True),
                IconCondition("plural_items/crown.png", lambda: self.active_state.crowns > 0, False),
            ], True, lambda: self.active_state.crowns),
            Icon("Medals", 6, 8, [
                IconCondition("plural_items/bananamedal.png", lambda: self.active_state.medals < 1, True),
                IconCondition("plural_items/bananamedal.png", lambda: self.active_state.medals > 0, False),
            ], True, lambda: self.active_state.medals),
            Icon("Pearls", 2, 8, [
                IconCondition("plural_items/pearl.png", lambda: self.active_state.pearls < 1, True),
                IconCondition("plural_items/pearl.png", lambda: self.active_state.pearls > 0, False),
            ], True, lambda: self.active_state.pearls),
            Icon("Fairies", 5, 8, [
                IconCondition("plural_items/banana_fairies.png", lambda: self.active_state.fairies < 1, True),
                IconCondition("plural_items/banana_fairies.png", lambda: self.active_state.fairies > 0, False),
            ], True, lambda: self.active_state.fairies),
            Icon("Rainbow Coins", 3, 8, [
                IconCondition("plural_items/rainbowcoin.png", lambda: self.active_state.rainbow_coins < 1, True),
                IconCondition("plural_items/rainbowcoin.png", lambda: self.active_state.rainbow_coins > 0, False),
            ], True, lambda: self.active_state.rainbow_coins),
        ]

    def items_ui(self, parent_frame):
        self.items_frame = ttk.Frame(parent_frame, padding="5")
        self.items_frame.pack(fill="both", expand=True)

        controls = Controls(self.items_frame, None)
        controls.pack(fill="x", pady=6)

        canvas = tk.Canvas(self.items_frame, width=400, height=300, bg=get_preference("background_color"))
        canvas.pack()
        self.layer = CanvasImageLayer(canvas)
        controls.image_canvas = self.layer
        local_scale = get_preference("ui_scale")
        
        for icon in self.icons:
            dim = local_scale
            if icon.is_compact:
                dim *= 0.8
            self.layer.add_image(
                key=icon.key,
                image_path=icon.icon_data[0].icon,
                x=int(local_scale * icon.x),
                y=int(local_scale * icon.y),
                size=(int(dim), int(dim)),
                has_number=icon.display_count
            )
        controls.on_scale(True)
        controls.on_toggle()
        
        # Hide items frame
        self.items_frame.pack_forget()

    def show_items_frame(self):
        self.items_frame.pack(fill="both", expand=True)

    def hide_items_frame(self):
        self.items_frame.pack_forget()

    def update_items_ui(self, viewer_state: KrosshairViewers, password: str):
        if self.layer is None or self.item_data is None or self.icons is None:
            return
        self.active_state = self.states[self.selected_state_index]
        if viewer_state == KrosshairViewers.player:
            mode_1 = self.memory_client.read_u8(0x80755318)
            if mode_1 == 6:
                for item in self.item_data:
                    setattr(self.active_state, item.attr, item.getCount(self))
            self.active_state.encrypt(password)  # Send settings over
        elif viewer_state in (KrosshairViewers.restreamer, KrosshairViewers.comms):
            self.active_state.decrypt("", password)  # Receive settings
        local_scale = get_preference("ui_scale")
        for icon in self.icons:
            dim = local_scale
            if icon.is_compact:
                dim *= 0.8
            for cond in icon.icon_data:
                if cond.condition():
                    self.layer.swap_image(icon.key, cond.icon, 0.5, (int(dim), int(dim)), icon.display_count)
                    self.layer.set_position(icon.key, int(icon.x * local_scale), int(icon.y * local_scale))
                    self.layer.set_dimmed(icon.key, cond.dim_if_true)
            if icon.display_count:
                count = icon.count()
                self.layer.set_number(icon.key, count)

    def sendItemPacket(self, url, player_index, password):
        self.active_state = self.states[self.selected_state_index]
        # mode_1 = self.memory_client.read_u8(0x80755318)
        # if mode_1 == 6:
        for item in self.item_data:
            setattr(self.active_state, item.attr, item.getCount(self))
        enc = self.active_state.encrypt(password)
        print(url)
        try:
            payload = {}

            if player_index == 1:
                payload["value1"] = enc
            elif player_index == 2:
                payload["value2"] = enc

            response = requests.post(
                url,
                json=payload
            )
            print("Status:", response.status_code)
            print("Response:", response.text)
        except Exception as e:
            print("Error:", e)

    def getItemPacket(self, data, player_index, password):
        # URL = f"{BASE_URL}/state"
        self.active_state = self.states[self.selected_state_index]
        self.active_state.decrypt(data[f"value{player_index}"], password)
        # Render
        local_scale = get_preference("ui_scale")
        for icon in self.icons:
            dim = local_scale
            if icon.is_compact:
                dim *= 0.8
            for cond in icon.icon_data:
                if cond.condition():
                    self.layer.swap_image(icon.key, cond.icon, 0.5, (int(dim), int(dim)), icon.display_count)
                    self.layer.set_position(icon.key, int(icon.x * local_scale), int(icon.y * local_scale))
                    self.layer.set_dimmed(icon.key, cond.dim_if_true)
            if icon.display_count:
                count = icon.count()
                self.layer.set_number(icon.key, count)

    def initCanvas(self, canvas):
        self.layer = CanvasImageLayer(canvas)
        local_scale = get_preference("ui_scale")
        
        for icon in self.icons:
            dim = local_scale
            if icon.is_compact:
                dim *= 0.8
            self.layer.add_image(
                key=icon.key,
                image_path=icon.icon_data[0].icon,
                x=int(local_scale * icon.x),
                y=int(local_scale * icon.y),
                size=(int(dim), int(dim)),
                has_number=icon.display_count
            )