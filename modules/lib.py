import tkinter as tk
from enum import IntEnum, auto

class KrosshairViewers(IntEnum):
    not_set = auto()
    player = auto()
    restreamer = auto()
    comms = auto()

class KrosshairLib:
    def log_debug(self, message: str):
        """Log debug message."""
        if self.debug_output:
            self.debug_output.insert(tk.END, f"{message}\n")
            self.debug_output.see(tk.END)
        # print(message)