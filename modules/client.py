import struct
from modules.loader import EmulatorInfo, Emulators

# Wrapper for N64 memory operations with proper address translation
class N64MemoryClient:
    def __init__(self, emulator_info: EmulatorInfo):
        self.emulator_info = emulator_info
        self.endianness = "big" if emulator_info.id == Emulators.Ares else "little"
        
    def read_u8(self, address):
        """Read an unsigned 8-bit value with N64 address fixing."""
        fixed_address = self._fix_n64_address(address, 1)
        data = self.emulator_info.connected_process.read_bytes(fixed_address, 1, address)
        return int.from_bytes(data, self.endianness)
    
    def read_u16(self, address):
        """Read an unsigned 16-bit value with N64 address fixing."""
        fixed_address = self._fix_n64_address(address, 2)
        data = self.emulator_info.connected_process.read_bytes(fixed_address, 2, address)
        return int.from_bytes(data, self.endianness)
    
    def read_u32(self, address):
        """Read an unsigned 32-bit value with N64 address fixing."""
        fixed_address = self._fix_n64_address(address, 4)
        data = self.emulator_info.connected_process.read_bytes(fixed_address, 4, address)
        return int.from_bytes(data, self.endianness)
    
    def read_f32(self, address):
        """Read a single-precision float with N64 address fixing."""
        value = self.read_u32(address)
        if value == 0:
            return 0
        return struct.unpack("!f", bytes.fromhex("{:08X}".format(value)))[0]
    
    def _fix_n64_address(self, address, size):
        """Fix N64 address for emulator compatibility - critical for memory operations."""
        # Apply N64 address fixing - strip MSB if set
        if address & 0x80000000:
            address &= 0x7FFFFFFF

        # Apply N64 address fixing based on size
        if self.endianness == "little":
            if size == 1:  # 8-bit operation
                remainder = address % 4
                if remainder == 0:
                    address += 3
                elif remainder == 1:
                    address += 1
                elif remainder == 2:
                    address -= 1
                elif remainder == 3:
                    address -= 3
            elif size == 2:  # 16-bit operation
                remainder = address % 4
                if remainder in (2, 3):
                    address -= 2
                elif remainder in (0, 1):
                    address += 2
            # 32-bit operations (size == 4) don't need address fixing
        
        final_address = self.emulator_info.connected_offset + address
        return final_address
    
    def close(self):
        """Close the connection."""
        if self.emulator_info and hasattr(self.emulator_info, 'connected_process'):
            try:
                self.emulator_info.connected_process.close()
            except:
                pass