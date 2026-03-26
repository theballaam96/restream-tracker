import tkinter as tk
from tkinter import ttk
from modules.loader import attachWrapper, Emulators
from modules.client import N64MemoryClient
from modules.memory_map import DK64MemoryMap
from modules.inventory import Inventory

def connect_to_emulator():
    """Connect to any available emulator using the official loader system."""
    # Try each emulator in order until one connects successfully
    # Put Project64 4.0 before legacy since user mentioned PJ64 4.0 specifically
    emulator_order = [
        Emulators.Ares,
        Emulators.RMG,                  # RMG
        Emulators.Project64_v4,         # Project64 4.0
        Emulators.Project64,            # Project64 3.0
        Emulators.BizHawk,              # BizHawk
        Emulators.Simple64,             # Simple64
        Emulators.RetroArch,            # RetroArch
        Emulators.ParallelLauncher,     # Parallel Launcher
        Emulators.ParallelLauncher903,  # Parallel Launcher (9.0.3+)
    ]
    
    for emulator in emulator_order:
        try:
            emulator_info = attachWrapper(emulator)
            if emulator_info and hasattr(emulator_info, 'connected_process') and emulator_info.connected_process:
                return emulator_info
        except Exception:
            # This emulator is not running or failed to connect, continue silently
            continue
    
    # No emulator found
    return None

class KBConnection(Inventory):
    def __init__(self):
        self.memory_client = None
        self.memory_pointer = 0
        Inventory.__init__(self)

    def connect_internal(self, root, url, player_index, password):
        try:
            # Use the official loader to connect to any available emulator
            print("Attempting to connect to any available emulator...")
            emulator_info = connect_to_emulator()
            
            if emulator_info:
                # Wrap the emulator connection with our N64 address fixing
                self.memory_client = N64MemoryClient(emulator_info)
                
                print(f"Connected to {emulator_info.readable_emulator_name}")
                print(f"Process name: {emulator_info.process_name}")
                print(f"Memory offset: 0x{emulator_info.connected_offset:08X}")
                
                # Test basic memory reading first
                try:
                    ramb_test = emulator_info.connected_process.read_bytes(emulator_info.connected_offset + 0x759290, 4, 0x80759290)
                    ramb_value = int.from_bytes(ramb_test, "little")
                    print(f"RAMB signature test: 0x{ramb_value:08X}")
                    
                    # Check if this looks like DK64 ROM
                    if ramb_value == 0x52414D42:  # "RAMB" in little endian
                        print("DK64 ROM detected successfully")
                    else:
                        print(f"Warning: RAMB signature doesn't match DK64 (got 0x{ramb_value:08X})")
                        
                except Exception as test_error:
                    print(f"RAMB test failed: {str(test_error)}")
                    print("Note: DK64 might not be loaded yet")
                    pass
                
                # Try to validate connection with a simple read
                try:
                    memory_pointer = self.memory_client.read_u32(DK64MemoryMap.memory_pointer)
                    print(f"Memory pointer read successful: 0x{memory_pointer:08X}")
                    self.memory_pointer = memory_pointer
                    self.status_label.config(text=f"Connected to {emulator_info.readable_emulator_name}", foreground="green")
                    print(f"Successfully connected to {emulator_info.readable_emulator_name}")
                    self.frame_loop(root, url, player_index, password)
                except Exception as validation_error:
                    print(f"Memory pointer read failed: {str(validation_error)}")
                    
                    # Try basic map index read instead to verify connection works
                    try:
                        map_index = self.memory_client.read_u32(DK64MemoryMap.map_index)
                        print(f"Basic connection test successful - Map index: {map_index}")
                        self.status_label.config(text=f"Connected to {emulator_info.readable_emulator_name}", foreground="green")
                        print(f"Successfully connected to {emulator_info.readable_emulator_name} (basic mode)")
                        self.frame_loop(root, url, player_index, password)
                    except Exception as basic_error:
                        print(f"Basic connection test also failed: {str(basic_error)}")
                        self.status_label.config(text=f"Connected to {emulator_info.readable_emulator_name} (partial)", foreground="orange")
            else:
                print("No supported emulator found running")
                self.status_label.config(text="No emulator found", foreground="red")
            
        except Exception as e:
            print(f"Failed to connect: {str(e)}")
            self.status_label.config(text="Connection failed", foreground="red")

    def connect(self, root, url, player_index, password):
        """Connect to the emulator."""
        self.status_label.config(text="Attempting Connection...", foreground="orange")
        root.after(10, lambda: self.connect_internal(root, url, player_index, password))  # Needs to be done like this to allow a UI update
    
    def disconnect(self):
        """Disconnect from emulator."""
        if self.memory_client:
            self.memory_client.close()
        self.memory_client = None
        self.memory_pointer = 0
        self.status_label.config(text="Not connected", foreground="red")
        print("Disconnected")
    
    def validate_connection(self):
        """Validate the connection."""
        if not self.memory_client:
            if self.debug_output:
                self.debug_output.insert(tk.END, "Not connected to emulator\n")
            return
        
        try:
            print("=== CONNECTION VALIDATION ===")
            
            # Test basic memory reading
            test_addr = 0x807444E4  # Map index
            try:
                value = self.memory_client.read_u32(test_addr)
                print(f"Successfully read from 0x{test_addr:08X}: {value}")
            except Exception as read_error:
                pass
                print(f"Failed to read from test address: {str(read_error)}")
                
            # Test memory pointer
            try:
                memory_pointer = self.memory_client.read_u32(DK64MemoryMap.memory_pointer)
                if memory_pointer != 0:
                    print(f"Memory pointer: 0x{memory_pointer:08X}")
                    
                    # Try to read from memory pointer
                    try:
                        ptr_val = self.memory_client.read_u32(memory_pointer)
                        print(f"Value at memory pointer: 0x{ptr_val:08X}")
                    except Exception as ptr_read_error:
                        print(f"Failed to read from memory pointer: {str(ptr_read_error)}")
                        pass
            except Exception as ptr_error:
                pass
                print(f"Memory pointer read failed: {str(ptr_error)}")
                
            print("=== END VALIDATION ===")
                
        except Exception as e:
            pass
            print(f"Validation error: {str(e)}")

    def connection_ui(self, parent_frame, root, url, player_index, password):
        connection_frame = ttk.LabelFrame(parent_frame, text="Emulator Connection", padding="5")
        connection_frame.pack(fill=tk.X, pady=(0, 10))
        
        button_frame = ttk.Frame(connection_frame)
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="Connect", command=lambda: self.connect(root, url, player_index, password)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Disconnect", command=self.disconnect).pack(side=tk.LEFT)
        
        self.status_label = ttk.Label(connection_frame, text="Not connected", foreground="red")
        self.status_label.pack(anchor=tk.W, pady=(5, 0))

    def debug_ui(self, parent_frame):
        debug_frame = ttk.LabelFrame(parent_frame, text="Debug", padding="5")
        debug_frame.pack(fill=tk.X)

        # ── Output ───────────────────────────────────
        self.debug_output = tk.Text(debug_frame, height=6, width=60)
        self.debug_output.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    def frame_loop(self, root, url, player_index, password):
        # if self.memory_client:
            # if not self.mem_client_state:
            #     self.show_items_frame()
            #     self.mem_client_state = True
            # self.update_items_ui()
        # else:
            # if self.mem_client_state:
            #     self.hide_items_frame()
            #     self.mem_client_state = False
        self.sendItemPacket(url, player_index, password)
        root.after(1000, lambda: self.frame_loop(root, url, player_index, password))