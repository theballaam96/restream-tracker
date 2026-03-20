import tkinter as tk
from tkinter import ttk
from modules.memory_map import DK64MemoryMap
from modules.lib import KrossbonesLib
from modules.core import KrossbonesCore
from enum import IntEnum, auto
from typing import Union
from PIL import Image, ImageTk, ImageEnhance, ImageFont, ImageDraw
from modules.preferences import get_preference, set_preference
from tkinter import colorchooser

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

    def getCount(self, core: KrossbonesCore):
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

    def getCount(self, core: KrossbonesCore):
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

    def getCount(self, core: KrossbonesCore):
        flag_offset = self.flag_index >> 3
        flag_shift = self.flag_index & 7
        val = core.memory_client.read_u8(0x807ECEA8 + flag_offset)
        return (val >> flag_shift) & 1

class Item:
    def __init__(self, name: str, item_type: ItemTypes, packet: Union[CountStructItem, KongBaseItem, FlagItem]):
        self.name = name
        self.item_type = item_type
        self.packet = packet
        self.count = 0

    def getCount(self, core: KrossbonesCore) -> int:
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
        font = ImageFont.truetype("assets/Roboto.ttf", max(12, int(img.width / 3)))

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

class Inventory(KrossbonesCore, KrossbonesLib):
    def __init__(self):
        """Initialize with given parameters."""

        self.layer = None
        self.items_frame = None
        # Item database - separated into moves and items
        self.item_data = [
            # Kongs
            Item("Donkey Kong", ItemTypes.CountStruct, CountStructItem(0xB, 1, True, 0)),
            Item("Diddy Kong", ItemTypes.CountStruct, CountStructItem(0xB, 1, True, 1)),
            Item("Lanky Kong", ItemTypes.CountStruct, CountStructItem(0xB, 1, True, 2)),
            Item("Tiny Kong", ItemTypes.CountStruct, CountStructItem(0xB, 1, True, 3)),
            Item("Chunky Kong", ItemTypes.CountStruct, CountStructItem(0xB, 1, True, 4)),
            # All Kong Moves
            Item("Barrel Throwing", ItemTypes.CountStruct, CountStructItem(0x18, 1, True, 5)),
            Item("Orange Throwing", ItemTypes.CountStruct, CountStructItem(0x18, 1, True, 6)),
            Item("Vine Swinging", ItemTypes.CountStruct, CountStructItem(0x18, 1, True, 4)),
            Item("Diving", ItemTypes.CountStruct, CountStructItem(0x18, 1, True, 7)),
            Item("Climbing", ItemTypes.Flag, FlagItem(0x29F)),
            Item("Camera", ItemTypes.Flag, FlagItem(0x2FD)),
            Item("Shockwave", ItemTypes.Flag, FlagItem(0x179)),
            Item("Slam", ItemTypes.KongBase, KongBaseItem(0, 1, 1, False)),
            Item("Homing", ItemTypes.KongBase, KongBaseItem(0, 2, 1, True, 1)),
            Item("Sniper", ItemTypes.KongBase, KongBaseItem(0, 2, 1, True, 2)),
            # Guns
            Item("Coconut", ItemTypes.KongBase, KongBaseItem(0, 2, 1, True, 0)),
            Item("Peanut", ItemTypes.KongBase, KongBaseItem(1, 2, 1, True, 0)),
            Item("Grape", ItemTypes.KongBase, KongBaseItem(2, 2, 1, True, 0)),
            Item("Feather", ItemTypes.KongBase, KongBaseItem(3, 2, 1, True, 0)),
            Item("Pineapple", ItemTypes.KongBase, KongBaseItem(4, 2, 1, True, 0)),
            # Instruments
            Item("Bongos", ItemTypes.KongBase, KongBaseItem(0, 4, 1, True, 0)),
            Item("Guitar", ItemTypes.KongBase, KongBaseItem(1, 4, 1, True, 0)),
            Item("Trombone", ItemTypes.KongBase, KongBaseItem(2, 4, 1, True, 0)),
            Item("Sax", ItemTypes.KongBase, KongBaseItem(3, 4, 1, True, 0)),
            Item("Triangle", ItemTypes.KongBase, KongBaseItem(4, 4, 1, True, 0)),
            # Special Moves
            Item("Blast", ItemTypes.KongBase, KongBaseItem(0, 0, 1, True, 0)),
            Item("Charge", ItemTypes.KongBase, KongBaseItem(1, 0, 1, True, 0)),
            Item("Orangstand", ItemTypes.KongBase, KongBaseItem(2, 0, 1, True, 0)),
            Item("Mini", ItemTypes.KongBase, KongBaseItem(3, 0, 1, True, 0)),
            Item("Hunky", ItemTypes.KongBase, KongBaseItem(4, 0, 1, True, 0)),
            Item("Strong", ItemTypes.KongBase, KongBaseItem(0, 0, 1, True, 1)),
            Item("Rocket", ItemTypes.KongBase, KongBaseItem(1, 0, 1, True, 1)),
            Item("Balloon", ItemTypes.KongBase, KongBaseItem(2, 0, 1, True, 1)),
            Item("Twirl", ItemTypes.KongBase, KongBaseItem(3, 0, 1, True, 1)),
            Item("Punch", ItemTypes.KongBase, KongBaseItem(4, 0, 1, True, 1)),
            Item("Grab", ItemTypes.KongBase, KongBaseItem(0, 0, 1, True, 2)),
            Item("Spring", ItemTypes.KongBase, KongBaseItem(1, 0, 1, True, 2)),
            Item("Sprint", ItemTypes.KongBase, KongBaseItem(2, 0, 1, True, 2)),
            Item("Port", ItemTypes.KongBase, KongBaseItem(3, 0, 1, True, 2)),
            Item("Gone", ItemTypes.KongBase, KongBaseItem(4, 0, 1, True, 2)),
            # Keys
            Item("Key 1", ItemTypes.CountStruct, CountStructItem(0xA, 1, True, 0)),
            Item("Key 2", ItemTypes.CountStruct, CountStructItem(0xA, 1, True, 1)),
            Item("Key 3", ItemTypes.CountStruct, CountStructItem(0xA, 1, True, 2)),
            Item("Key 4", ItemTypes.CountStruct, CountStructItem(0xA, 1, True, 3)),
            Item("Key 5", ItemTypes.CountStruct, CountStructItem(0xA, 1, True, 4)),
            Item("Key 6", ItemTypes.CountStruct, CountStructItem(0xA, 1, True, 5)),
            Item("Key 7", ItemTypes.CountStruct, CountStructItem(0xA, 1, True, 6)),
            Item("Key 8", ItemTypes.CountStruct, CountStructItem(0xA, 1, True, 7)),
            # Blueprints
            Item("DK Blueprints", ItemTypes.CountStruct, CountStructItem(0x0, 1, False)),
            Item("Diddy Blueprints", ItemTypes.CountStruct, CountStructItem(0x1, 1, False)),
            Item("Lanky Blueprints", ItemTypes.CountStruct, CountStructItem(0x2, 1, False)),
            Item("Tiny Blueprints", ItemTypes.CountStruct, CountStructItem(0x3, 1, False)),
            Item("Chunky Blueprints", ItemTypes.CountStruct, CountStructItem(0x4, 1, False)),
            Item("DK Turn-Ins", ItemTypes.CountStruct, CountStructItem(0x19, 1, False)),
            Item("Diddy Turn-Ins", ItemTypes.CountStruct, CountStructItem(0x1A, 1, False)),
            Item("Lanky Turn-Ins", ItemTypes.CountStruct, CountStructItem(0x1B, 1, False)),
            Item("Tiny Turn-Ins", ItemTypes.CountStruct, CountStructItem(0x1C, 1, False)),
            Item("Chunky Turn-Ins", ItemTypes.CountStruct, CountStructItem(0x1D, 1, False)),
            # Shopkeepers
            Item("Cranky", ItemTypes.Flag, FlagItem(0x3C2)),
            Item("Funky", ItemTypes.Flag, FlagItem(0x3C3)),
            Item("Candy", ItemTypes.Flag, FlagItem(0x3C4)),
            Item("Snide", ItemTypes.Flag, FlagItem(0x3C5)),
            # Items
            Item("Bean", ItemTypes.CountStruct, CountStructItem(0xD, 1, True, 5)),
            Item("Nintendo Coin", ItemTypes.CountStruct, CountStructItem(0xD, 1, True, 7)),
            Item("Rareware Coin", ItemTypes.CountStruct, CountStructItem(0xD, 1, True, 6)),
            Item("Crowns", ItemTypes.CountStruct, CountStructItem(0xC, 1, False)),
            Item("Medals", ItemTypes.CountStruct, CountStructItem(0xE, 1, False)),
            Item("Pearls", ItemTypes.CountStruct, CountStructItem(0xF, 1, False)),
            Item("Fairies", ItemTypes.CountStruct, CountStructItem(0x10, 1, False)),
            Item("Rainbow Coins", ItemTypes.CountStruct, CountStructItem(0x11, 1, False)),
        ]

        self.icons = [
            Icon("Donkey Kong", 0, 0, [
                IconCondition("dk/donkey.png", lambda: self.getCount("Donkey Kong") == 0, True),
                IconCondition("dk/donkey.png", lambda: self.getCount("Donkey Kong") != 0, False),
            ]),
            Icon("Diddy Kong", 0, 1, [
                IconCondition("diddy/diddy.png", lambda: self.getCount("Diddy Kong") == 0, True),
                IconCondition("diddy/diddy.png", lambda: self.getCount("Diddy Kong") != 0, False),
            ]),
            Icon("Lanky Kong", 0, 2, [
                IconCondition("lanky/lanky.png", lambda: self.getCount("Lanky Kong") == 0, True),
                IconCondition("lanky/lanky.png", lambda: self.getCount("Lanky Kong") != 0, False),
            ]),
            Icon("Tiny Kong", 0, 3, [
                IconCondition("tiny/tiny.png", lambda: self.getCount("Tiny Kong") == 0, True),
                IconCondition("tiny/tiny.png", lambda: self.getCount("Tiny Kong") != 0, False),
            ]),
            Icon("Chunky Kong", 0, 4, [
                IconCondition("chunky/chunky.png", lambda: self.getCount("Chunky Kong") == 0, True),
                IconCondition("chunky/chunky.png", lambda: self.getCount("Chunky Kong") != 0, False),
            ]),
            Icon("Barrel Throwing", 3 * COMPACT_SCALING, 5, [
                IconCondition("all_kong/barrel_throwing.png", lambda: self.getCount("Barrel Throwing") == 0, True),
                IconCondition("all_kong/barrel_throwing.png", lambda: self.getCount("Barrel Throwing") != 0, False),
            ], is_compact=True),
            Icon("Orange Throwing", 2 * COMPACT_SCALING, 5, [
                IconCondition("all_kong/orange_throwing.png", lambda: self.getCount("Orange Throwing") == 0, True),
                IconCondition("all_kong/orange_throwing.png", lambda: self.getCount("Orange Throwing") != 0, False),
            ], is_compact=True),
            Icon("Vine Swinging", 4 * COMPACT_SCALING, 5, [
                IconCondition("all_kong/vine_swinging.png", lambda: self.getCount("Vine Swinging") == 0, True),
                IconCondition("all_kong/vine_swinging.png", lambda: self.getCount("Vine Swinging") != 0, False),
            ], is_compact=True),
            Icon("Diving", 1 * COMPACT_SCALING, 5, [
                IconCondition("all_kong/diving.png", lambda: self.getCount("Diving") == 0, True),
                IconCondition("all_kong/diving.png", lambda: self.getCount("Diving") != 0, False),
            ], is_compact=True),
            Icon("Climbing", 5 * COMPACT_SCALING, 5, [
                IconCondition("all_kong/climbing.png", lambda: self.getCount("Climbing") == 0, True),
                IconCondition("all_kong/climbing.png", lambda: self.getCount("Climbing") != 0, False),
            ], is_compact=True),
            Icon("Camera_Shockwave", 6 * COMPACT_SCALING, 5, [
                IconCondition("shockwave_camera/filmwave.png", lambda: self.getCount("Camera") == 0 and self.getCount("Shockwave") == 0, True),
                IconCondition("shockwave_camera/filmwave.png", lambda: self.getCount("Camera") != 0 and self.getCount("Shockwave") != 0, False),
                IconCondition("shockwave_camera/fairycamonly.png", lambda: self.getCount("Camera") != 0 and self.getCount("Shockwave") == 0, False),
                IconCondition("shockwave_camera/shockwaveonly.png", lambda: self.getCount("Camera") == 0 and self.getCount("Shockwave") != 0, False),
            ], is_compact=True),
            Icon("Slam", 0 * COMPACT_SCALING, 5, [
                IconCondition("slam/slam1.png", lambda: self.getCount("Slam") < 1, True),
                IconCondition("slam/slam1.png", lambda: self.getCount("Slam") == 1, False),
                IconCondition("slam/slam2.png", lambda: self.getCount("Slam") == 2, False),
                IconCondition("slam/slam3.png", lambda: self.getCount("Slam") > 2, False),
            ], is_compact=True),
            Icon("Homing_Sniper", 7 * COMPACT_SCALING, 5, [
                IconCondition("homing_sniper/homingscope.png", lambda: self.getCount("Homing") == 0 and self.getCount("Sniper") == 0, True),
                IconCondition("homing_sniper/homingscope.png", lambda: self.getCount("Homing") != 0 and self.getCount("Sniper") != 0, False),
                IconCondition("homing_sniper/homingonly.png", lambda: self.getCount("Homing") != 0 and self.getCount("Sniper") == 0, False),
                IconCondition("homing_sniper/scopeonly.png", lambda: self.getCount("Homing") == 0 and self.getCount("Sniper") != 0, False),
            ], is_compact=True),
            Icon("Coconut", 1, 0, [
                IconCondition("dk/dk_gun.png", lambda: self.getCount("Coconut") == 0, True),
                IconCondition("dk/dk_gun.png", lambda: self.getCount("Coconut") != 0, False),
            ]),
            Icon("Peanut", 1, 1, [
                IconCondition("diddy/diddy_gun.png", lambda: self.getCount("Peanut") == 0, True),
                IconCondition("diddy/diddy_gun.png", lambda: self.getCount("Peanut") != 0, False),
            ]),
            Icon("Grape", 1, 2, [
                IconCondition("lanky/lanky_gun.png", lambda: self.getCount("Grape") == 0, True),
                IconCondition("lanky/lanky_gun.png", lambda: self.getCount("Grape") != 0, False),
            ]),
            Icon("Feather", 1, 3, [
                IconCondition("tiny/tiny_gun.png", lambda: self.getCount("Feather") == 0, True),
                IconCondition("tiny/tiny_gun.png", lambda: self.getCount("Feather") != 0, False),
            ]),
            Icon("Pineapple", 1, 4, [
                IconCondition("chunky/chunky_gun.png", lambda: self.getCount("Pineapple") == 0, True),
                IconCondition("chunky/chunky_gun.png", lambda: self.getCount("Pineapple") != 0, False),
            ]),
            Icon("Bongos", 2, 0, [
                IconCondition("dk/dk_inst.png", lambda: self.getCount("Bongos") == 0, True),
                IconCondition("dk/dk_inst.png", lambda: self.getCount("Bongos") != 0, False),
            ]),
            Icon("Guitar", 2, 1, [
                IconCondition("diddy/diddy_inst.png", lambda: self.getCount("Guitar") == 0, True),
                IconCondition("diddy/diddy_inst.png", lambda: self.getCount("Guitar") != 0, False),
            ]),
            Icon("Trombone", 2, 2, [
                IconCondition("lanky/lanky_inst.png", lambda: self.getCount("Trombone") == 0, True),
                IconCondition("lanky/lanky_inst.png", lambda: self.getCount("Trombone") != 0, False),
            ]),
            Icon("Sax", 2, 3, [
                IconCondition("tiny/tiny_inst.png", lambda: self.getCount("Sax") == 0, True),
                IconCondition("tiny/tiny_inst.png", lambda: self.getCount("Sax") != 0, False),
            ]),
            Icon("Triangle", 2, 4, [
                IconCondition("chunky/chunky_inst.png", lambda: self.getCount("Triangle") == 0, True),
                IconCondition("chunky/chunky_inst.png", lambda: self.getCount("Triangle") != 0, False),
            ]),
            Icon("Blast", 4, 0, [
                IconCondition("dk/dkpad.png", lambda: self.getCount("Blast") == 0 and not USE_COLOR_ICONS, True),
                IconCondition("dk/dkpad.png", lambda: self.getCount("Blast") != 0 and not USE_COLOR_ICONS, False),
                IconCondition("dk/dkpad_c.png", lambda: self.getCount("Blast") == 0 and USE_COLOR_ICONS, True),
                IconCondition("dk/dkpad_c.png", lambda: self.getCount("Blast") != 0 and USE_COLOR_ICONS, False),
            ]),
            Icon("Charge", 3, 1, [
                IconCondition("diddy/diddy_move.png", lambda: self.getCount("Charge") == 0, True),
                IconCondition("diddy/diddy_move.png", lambda: self.getCount("Charge") != 0, False),
            ]),
            Icon("Orangstand", 3, 2, [
                IconCondition("lanky/lanky_move.png", lambda: self.getCount("Orangstand") == 0, True),
                IconCondition("lanky/lanky_move.png", lambda: self.getCount("Orangstand") != 0, False),
            ]),
            Icon("Mini", 5, 3, [
                IconCondition("tiny/tinybarrel.png", lambda: self.getCount("Mini") == 0 and not USE_COLOR_ICONS, True),
                IconCondition("tiny/tinybarrel.png", lambda: self.getCount("Mini") != 0 and not USE_COLOR_ICONS, False),
                IconCondition("tiny/tinybarrel_c.png", lambda: self.getCount("Mini") == 0 and USE_COLOR_ICONS, True),
                IconCondition("tiny/tinybarrel_c.png", lambda: self.getCount("Mini") != 0 and USE_COLOR_ICONS, False),
            ]),
            Icon("Hunky", 5, 4, [
                IconCondition("chunky/chunkybarrel.png", lambda: self.getCount("Hunky") == 0 and not USE_COLOR_ICONS, True),
                IconCondition("chunky/chunkybarrel.png", lambda: self.getCount("Hunky") != 0 and not USE_COLOR_ICONS, False),
                IconCondition("chunky/chunkybarrel_c.png", lambda: self.getCount("Hunky") == 0 and USE_COLOR_ICONS, True),
                IconCondition("chunky/chunkybarrel_c.png", lambda: self.getCount("Hunky") != 0 and USE_COLOR_ICONS, False),
            ]),
            Icon("Strong", 5, 0, [
                IconCondition("dk/dkbarrel.png", lambda: self.getCount("Strong") == 0 and not USE_COLOR_ICONS, True),
                IconCondition("dk/dkbarrel.png", lambda: self.getCount("Strong") != 0 and not USE_COLOR_ICONS, False),
                IconCondition("dk/dkbarrel_c.png", lambda: self.getCount("Strong") == 0 and USE_COLOR_ICONS, True),
                IconCondition("dk/dkbarrel_c.png", lambda: self.getCount("Strong") != 0 and USE_COLOR_ICONS, False),
            ]),
            Icon("Rocket", 5, 1, [
                IconCondition("diddy/diddybarrel.png", lambda: self.getCount("Rocket") == 0 and not USE_COLOR_ICONS, True),
                IconCondition("diddy/diddybarrel.png", lambda: self.getCount("Rocket") != 0 and not USE_COLOR_ICONS, False),
                IconCondition("diddy/diddybarrel_c.png", lambda: self.getCount("Rocket") == 0 and USE_COLOR_ICONS, True),
                IconCondition("diddy/diddybarrel_c.png", lambda: self.getCount("Rocket") != 0 and USE_COLOR_ICONS, False),
            ]),
            Icon("Balloon", 4, 2, [
                IconCondition("lanky/lankypad.png", lambda: self.getCount("Balloon") == 0, True),
                IconCondition("lanky/lankypad.png", lambda: self.getCount("Balloon") != 0, False),
            ]),
            Icon("Twirl", 3, 3, [
                IconCondition("tiny/tiny_move.png", lambda: self.getCount("Twirl") == 0, True),
                IconCondition("tiny/tiny_move.png", lambda: self.getCount("Twirl") != 0, False),
            ]),
            Icon("Punch", 3, 4, [
                IconCondition("chunky/chunky_move.png", lambda: self.getCount("Punch") == 0, True),
                IconCondition("chunky/chunky_move.png", lambda: self.getCount("Punch") != 0, False),
            ]),
            Icon("Grab", 3, 0, [
                IconCondition("dk/dk_move.png", lambda: self.getCount("Grab") == 0, True),
                IconCondition("dk/dk_move.png", lambda: self.getCount("Grab") != 0, False),
            ]),
            Icon("Spring", 4, 1, [
                IconCondition("diddy/diddypad.png", lambda: self.getCount("Spring") == 0 and not USE_COLOR_ICONS, True),
                IconCondition("diddy/diddypad.png", lambda: self.getCount("Spring") != 0 and not USE_COLOR_ICONS, False),
                IconCondition("diddy/diddypad_c.png", lambda: self.getCount("Spring") == 0 and USE_COLOR_ICONS, True),
                IconCondition("diddy/diddypad_c.png", lambda: self.getCount("Spring") != 0 and USE_COLOR_ICONS, False),
            ]),
            Icon("Sprint", 5, 2, [
                IconCondition("lanky/lankybarrel.png", lambda: self.getCount("Sprint") == 0 and not USE_COLOR_ICONS, True),
                IconCondition("lanky/lankybarrel.png", lambda: self.getCount("Sprint") != 0 and not USE_COLOR_ICONS, False),
                IconCondition("lanky/lankybarrel_c.png", lambda: self.getCount("Sprint") == 0 and USE_COLOR_ICONS, True),
                IconCondition("lanky/lankybarrel_c.png", lambda: self.getCount("Sprint") != 0 and USE_COLOR_ICONS, False),
            ]),
            Icon("Port", 4, 3, [
                IconCondition("tiny/tinypad.png", lambda: self.getCount("Port") == 0 and not USE_COLOR_ICONS, True),
                IconCondition("tiny/tinypad.png", lambda: self.getCount("Port") != 0 and not USE_COLOR_ICONS, False),
                IconCondition("tiny/tinypad_c.png", lambda: self.getCount("Port") == 0 and USE_COLOR_ICONS, True),
                IconCondition("tiny/tinypad_c.png", lambda: self.getCount("Port") != 0 and USE_COLOR_ICONS, False),
            ]),
            Icon("Gone", 4, 4, [
                IconCondition("chunky/chunkypad.png", lambda: self.getCount("Gone") == 0 and not USE_COLOR_ICONS, True),
                IconCondition("chunky/chunkypad.png", lambda: self.getCount("Gone") != 0 and not USE_COLOR_ICONS, False),
                IconCondition("chunky/chunkypad_c.png", lambda: self.getCount("Gone") == 0 and USE_COLOR_ICONS, True),
                IconCondition("chunky/chunkypad_c.png", lambda: self.getCount("Gone") != 0 and USE_COLOR_ICONS, False),
            ]),
            Icon("Key 1", 0.25 * WIDE_SCALING, 8, [
                IconCondition("keys/k1.png", lambda: self.getCount("Key 1") == 0, True),
                IconCondition("keys/k1.png", lambda: self.getCount("Key 1") != 0, False),
            ]),
            Icon("Key 2", 1.25 * WIDE_SCALING, 8, [
                IconCondition("keys/k2.png", lambda: self.getCount("Key 2") == 0, True),
                IconCondition("keys/k2.png", lambda: self.getCount("Key 2") != 0, False),
            ]),
            Icon("Key 3", 2.25 * WIDE_SCALING, 8, [
                IconCondition("keys/k3.png", lambda: self.getCount("Key 3") == 0, True),
                IconCondition("keys/k3.png", lambda: self.getCount("Key 3") != 0, False),
            ]),
            Icon("Key 4", 3.25 * WIDE_SCALING, 8, [
                IconCondition("keys/k4.png", lambda: self.getCount("Key 4") == 0, True),
                IconCondition("keys/k4.png", lambda: self.getCount("Key 4") != 0, False),
            ]),
            Icon("Key 5", 0.25 * WIDE_SCALING, 9, [
                IconCondition("keys/k5.png", lambda: self.getCount("Key 5") == 0, True),
                IconCondition("keys/k5.png", lambda: self.getCount("Key 5") != 0, False),
            ]),
            Icon("Key 6", 1.25 * WIDE_SCALING, 9, [
                IconCondition("keys/k6.png", lambda: self.getCount("Key 6") == 0, True),
                IconCondition("keys/k6.png", lambda: self.getCount("Key 6") != 0, False),
            ]),
            Icon("Key 7", 2.25 * WIDE_SCALING, 9, [
                IconCondition("keys/k7.png", lambda: self.getCount("Key 7") == 0, True),
                IconCondition("keys/k7.png", lambda: self.getCount("Key 7") != 0, False),
            ]),
            Icon("Key 8", 3.25 * WIDE_SCALING, 9, [
                IconCondition("keys/k8.png", lambda: self.getCount("Key 8") == 0, True),
                IconCondition("keys/k8.png", lambda: self.getCount("Key 8") != 0, False),
            ]),
            Icon("Cranky", 0.25 * WIDE_SCALING, 6, [
                IconCondition("shopkeepers/cranky.png", lambda: self.getCount("Cranky") == 0, True),
                IconCondition("shopkeepers/cranky.png", lambda: self.getCount("Cranky") != 0, False),
            ]),
            Icon("Funky", 1.25 * WIDE_SCALING, 6, [
                IconCondition("shopkeepers/funky.png", lambda: self.getCount("Funky") == 0, True),
                IconCondition("shopkeepers/funky.png", lambda: self.getCount("Funky") != 0, False),
            ]),
            Icon("Candy", 2.25 * WIDE_SCALING, 6, [
                IconCondition("shopkeepers/candy.png", lambda: self.getCount("Candy") == 0, True),
                IconCondition("shopkeepers/candy.png", lambda: self.getCount("Candy") != 0, False),
            ]),
            Icon("Snide", 3.25 * WIDE_SCALING, 6, [
                IconCondition("shopkeepers/snide.png", lambda: self.getCount("Snide") == 0, True),
                IconCondition("shopkeepers/snide.png", lambda: self.getCount("Snide") != 0, False),
            ]),
            Icon("Donkey Blueprints", 6, 0, [
                IconCondition("dk/dk_bp.png", lambda: self.getCount("DK Blueprints") == self.getCount("DK Turn-Ins"), True),
                IconCondition("dk/dk_bp.png", lambda: self.getCount("DK Blueprints") != self.getCount("DK Turn-Ins"), False),
            ], True, lambda: self.getCount("DK Blueprints") - self.getCount("DK Turn-Ins")),
            Icon("Diddy Blueprints", 6, 1, [
                IconCondition("diddy/diddy_bp.png", lambda: self.getCount("Diddy Blueprints") == self.getCount("Diddy Turn-Ins"), True),
                IconCondition("diddy/diddy_bp.png", lambda: self.getCount("Diddy Blueprints") != self.getCount("Diddy Turn-Ins"), False),
            ], True, lambda: self.getCount("Diddy Blueprints") - self.getCount("Diddy Turn-Ins")),
            Icon("Lanky Blueprints", 6, 2, [
                IconCondition("lanky/lanky_bp.png", lambda: self.getCount("Lanky Blueprints") == self.getCount("Lanky Turn-Ins"), True),
                IconCondition("lanky/lanky_bp.png", lambda: self.getCount("Lanky Blueprints") != self.getCount("Lanky Turn-Ins"), False),
            ], True, lambda: self.getCount("Lanky Blueprints") - self.getCount("Lanky Turn-Ins")),
            Icon("Tiny Blueprints", 6, 3, [
                IconCondition("tiny/tiny_bp.png", lambda: self.getCount("Tiny Blueprints") == self.getCount("Tiny Turn-Ins"), True),
                IconCondition("tiny/tiny_bp.png", lambda: self.getCount("Tiny Blueprints") != self.getCount("Tiny Turn-Ins"), False),
            ], True, lambda: self.getCount("Tiny Blueprints") - self.getCount("Tiny Turn-Ins")),
            Icon("Chunky Blueprints", 6, 4, [
                IconCondition("chunky/chunky_bp.png", lambda: self.getCount("Chunky Blueprints") == self.getCount("Chunky Turn-Ins"), True),
                IconCondition("chunky/chunky_bp.png", lambda: self.getCount("Chunky Blueprints") != self.getCount("Chunky Turn-Ins"), False),
            ], True, lambda: self.getCount("Chunky Blueprints") - self.getCount("Chunky Turn-Ins")),
            Icon("Bean", 0, 7, [
                IconCondition("all_kong/bean.png", lambda: self.getCount("Bean") == 0, True),
                IconCondition("all_kong/bean.png", lambda: self.getCount("Bean") != 0, False),
            ]),
            Icon("Company Coins", 1, 7, [
                IconCondition("company_coins/shared_coin.png", lambda: self.getCount("Nintendo Coin") == 0 and self.getCount("Rareware Coin") == 0, True),
                IconCondition("company_coins/shared_coin.png", lambda: self.getCount("Nintendo Coin") != 0 and self.getCount("Rareware Coin") != 0, False),
                IconCondition("company_coins/nin_only.png", lambda: self.getCount("Nintendo Coin") != 0 and self.getCount("Rareware Coin") == 0, False),
                IconCondition("company_coins/rw_only.png", lambda: self.getCount("Nintendo Coin") == 0 and self.getCount("Rareware Coin") != 0, False),
            ]),
            Icon("Crowns", 4, 7, [
                IconCondition("plural_items/crown.png", lambda: self.getCount("Crowns") < 1, True),
                IconCondition("plural_items/crown.png", lambda: self.getCount("Crowns") > 0, False),
            ], True, lambda: self.getCount("Crowns")),
            Icon("Medals", 6, 7, [
                IconCondition("plural_items/bananamedal.png", lambda: self.getCount("Medals") < 1, True),
                IconCondition("plural_items/bananamedal.png", lambda: self.getCount("Medals") > 0, False),
            ], True, lambda: self.getCount("Medals")),
            Icon("Pearls", 2, 7, [
                IconCondition("plural_items/pearl.png", lambda: self.getCount("Pearls") < 1, True),
                IconCondition("plural_items/pearl.png", lambda: self.getCount("Pearls") > 0, False),
            ], True, lambda: self.getCount("Pearls")),
            Icon("Fairies", 5, 7, [
                IconCondition("plural_items/banana_fairies.png", lambda: self.getCount("Fairies") < 1, True),
                IconCondition("plural_items/banana_fairies.png", lambda: self.getCount("Fairies") > 0, False),
            ], True, lambda: self.getCount("Fairies")),
            Icon("Rainbow Coins", 3, 7, [
                IconCondition("plural_items/rainbowcoin.png", lambda: self.getCount("Rainbow Coins") < 1, True),
                IconCondition("plural_items/rainbowcoin.png", lambda: self.getCount("Rainbow Coins") > 0, False),
            ], True, lambda: self.getCount("Rainbow Coins")),
        ]

    def getCount(self, check) -> int:
        for item in self.item_data:
            if item.name == check:
                return item.count
        raise Exception("Invalid key")


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

    def update_items_ui(self):
        if self.layer is None or self.item_data is None or self.icons is None:
            return
        mode_1 = self.memory_client.read_u8(0x80755318)
        if mode_1 == 6:
            for item in self.item_data:
                item.getCount(self)
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
