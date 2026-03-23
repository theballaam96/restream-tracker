#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk

from modules.connection import KBConnection
from modules.inventory import Inventory
from modules.lib import KrosshairViewers
class Krosshair(KBConnection, Inventory):
    """Krosshair using official loader connection logic."""
    
    def __init__(self):
        # All child initialization functions
        KBConnection.__init__(self)
        Inventory.__init__(self)

        # Everything with the parent
        self.root = tk.Tk()
        self.root.title("Krosshair")
        self.root.geometry("600x800")
        icon = tk.PhotoImage(file="krosshair.png")
        self.root.iconphoto(True, icon)
        self.debug_output = None
        self.mem_client_state = False
        self.viewer = KrosshairViewers.not_set
        
        # Processing
        self.last_process_frame = 0
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface."""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.connection_ui(main_frame)
        self.items_ui(main_frame)

        # Debug Stuff
        # self.debug_ui(main_frame)

    def frame_loop(self):
        if self.memory_client:
            if not self.mem_client_state:
                self.show_items_frame()
                self.mem_client_state = True
            self.update_items_ui()
        else:
            if self.mem_client_state:
                self.hide_items_frame()
                self.mem_client_state = False
        self.root.after(int(1000 / 10), self.frame_loop)
    
    def run(self):
        """Run the application."""
        self.root.mainloop()

if __name__ == "__main__":
    app = Krosshair()
    app.run()
