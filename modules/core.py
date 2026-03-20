from modules.client import N64MemoryClient

class KrosshairCore:
    """Core functions that allow for better intellisense."""
    def __init__(self):
        self.memory_client: N64MemoryClient = None