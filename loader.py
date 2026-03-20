"""Loader script for tracking the success of tests."""

import platform
import os
import struct
import glob
from typing import Optional, Tuple, List, Dict, Any
from enum import IntEnum, auto

# Heavily based on the autoconnector work in GSTHD by JXJacob

# Detect operating system
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

# Windows API constants and structures
if IS_WINDOWS:
    import ctypes
    import ctypes.wintypes
    
    PROCESS_VM_READ = 0x0010
    PROCESS_VM_OPERATION = 0x0008
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    TH32CS_SNAPMODULE = 0x00000008
    TH32CS_SNAPMODULE32 = 0x00000010
    TH32CS_SNAPPROCESS = 0x00000002
    MAX_PATH = 260

    # Structures for Windows API
    class MODULEENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.wintypes.DWORD),
            ("th32ModuleID", ctypes.wintypes.DWORD),
            ("th32ProcessID", ctypes.wintypes.DWORD),
            ("GlblcntUsage", ctypes.wintypes.DWORD),
            ("ProccntUsage", ctypes.wintypes.DWORD),
            ("modBaseAddr", ctypes.POINTER(ctypes.wintypes.BYTE)),
            ("modBaseSize", ctypes.wintypes.DWORD),
            ("hModule", ctypes.wintypes.HMODULE),
            ("szModule", ctypes.c_char * 256),
            ("szExePath", ctypes.c_char * 260),
        ]

    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.wintypes.DWORD),
            ("cntUsage", ctypes.wintypes.DWORD),
            ("th32ProcessID", ctypes.wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.wintypes.ULONG)),
            ("th32ModuleID", ctypes.wintypes.DWORD),
            ("cntThreads", ctypes.wintypes.DWORD),
            ("th32ParentProcessID", ctypes.wintypes.DWORD),
            ("pcPriClassBase", ctypes.wintypes.LONG),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("szExeFile", ctypes.c_char * MAX_PATH),
        ]


def get_running_processes() -> List[Dict[str, Any]]:
    """Get list of running processes using native OS methods."""
    processes: List[Dict[str, Any]] = []
    
    if IS_WINDOWS:
        processes = _get_windows_processes()
    elif IS_LINUX:
        processes = _get_linux_processes()
    
    return processes


def _get_windows_processes() -> List[Dict[str, Any]]:
    """Get running processes on Windows using native API."""
    processes: List[Dict[str, Any]] = []
    
    snapshot = ctypes.windll.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == -1:
        return processes
    
    try:
        pe32 = PROCESSENTRY32()
        pe32.dwSize = ctypes.sizeof(PROCESSENTRY32)
        
        if ctypes.windll.kernel32.Process32First(snapshot, ctypes.byref(pe32)):
            while True:
                try:
                    process_name = pe32.szExeFile.decode('utf-8')
                    processes.append({
                        'name': process_name,
                        'pid': pe32.th32ProcessID
                    })
                except UnicodeDecodeError:
                    # Skip processes with invalid names
                    pass
                
                if not ctypes.windll.kernel32.Process32Next(snapshot, ctypes.byref(pe32)):
                    break
    finally:
        ctypes.windll.kernel32.CloseHandle(snapshot)
    
    return processes


def _get_linux_processes() -> List[Dict[str, Any]]:
    """Get running processes on Linux by reading /proc."""
    processes: List[Dict[str, Any]] = []
    
    try:
        for pid_dir in glob.glob('/proc/[0-9]*'):
            try:
                pid = int(os.path.basename(pid_dir))
                
                # Read process name from /proc/pid/comm
                comm_path = os.path.join(pid_dir, 'comm')
                if os.path.exists(comm_path):
                    with open(comm_path, 'r') as f:
                        process_name = f.read().strip()
                        processes.append({
                            'name': process_name,
                            'pid': pid
                        })
            except (ValueError, OSError, IOError):
                # Skip invalid PIDs or inaccessible processes
                continue
    except OSError:
        pass
    
    return processes

class ProcessMemory:
    """Class to handle process memory operations using ctypes on Windows and Linux."""
    
    def __init__(self, process_name: str, emu: Emulators):
        self.process_name = process_name
        self.process_handle = None
        self.process_id = None
        self.mem_file = None  # For Linux /proc/pid/mem
        self.force_exact_match = emu == Emulators.Ares
        self.emu = emu
        self.endianness = "big" if emu == Emulators.Ares else "little"
        self._attach_to_process()
    
    def _attach_to_process(self):
        """Attach to the process by name."""
        processes = get_running_processes()
        
        for proc in processes:
            if proc["name"]:
                if self.force_exact_match:
                    if proc["name"] != self.process_name:
                        continue
                else:
                    if not proc["name"].lower().startswith(self.process_name.lower()):
                        continue
                self.process_id = proc["pid"]
                
                if IS_WINDOWS:
                    self.process_handle = ctypes.windll.kernel32.OpenProcess(
                        PROCESS_VM_READ | PROCESS_VM_OPERATION | PROCESS_QUERY_INFORMATION,
                        False,
                        self.process_id
                    )
                    if not self.process_handle:
                        raise Exception(f"Failed to open process {self.process_name}")
                elif IS_LINUX:
                    # On Linux, we'll open /proc/pid/mem for memory access
                    try:
                        self.mem_file = open(f"/proc/{self.process_id}/mem", "r+b")
                    except (OSError, IOError) as e:
                        raise Exception(f"Failed to open memory file for process {self.process_name}: {e}")
                return
        raise Exception(f"Process {self.process_name} not found")
    
    def list_modules(self):
        """List modules in the process."""
        modules = []
        
        if IS_WINDOWS:
            return self._list_modules_windows()
        elif IS_LINUX:
            return self._list_modules_linux()
        
        return modules
    
    def _list_modules_windows(self):
        """List modules on Windows."""
        modules = []
        if not self.process_handle or not self.process_id:
            return modules
        
        snapshot = ctypes.windll.kernel32.CreateToolhelp32Snapshot(
            TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, 
            self.process_id
        )
        
        if snapshot == -1:
            return modules
        
        try:
            me32 = MODULEENTRY32()
            me32.dwSize = ctypes.sizeof(MODULEENTRY32)
            
            if ctypes.windll.kernel32.Module32First(snapshot, ctypes.byref(me32)):
                while True:
                    module_info = type('ModuleInfo', (), {
                        'name': me32.szModule.decode('utf-8'),
                        'lpBaseOfDll': ctypes.cast(me32.modBaseAddr, ctypes.c_void_p).value
                    })()
                    modules.append(module_info)
                    
                    if not ctypes.windll.kernel32.Module32Next(snapshot, ctypes.byref(me32)):
                        break
        finally:
            ctypes.windll.kernel32.CloseHandle(snapshot)
        
        return modules
    
    def _list_modules_linux(self):
        """List modules on Linux by reading /proc/pid/maps."""
        modules = []
        if not self.process_id:
            return modules
        
        try:
            with open(f"/proc/{self.process_id}/maps", "r") as maps_file:
                seen_modules = set()
                for line in maps_file:
                    parts = line.strip().split()
                    if len(parts) >= 6:
                        address_range = parts[0]
                        permissions = parts[1]
                        pathname = parts[5] if len(parts) > 5 else ""
                        
                        # Only include executable mappings with file paths
                        if 'x' in permissions and pathname and pathname != "[vdso]" and not pathname.startswith("["):
                            module_name = os.path.basename(pathname)
                            if module_name not in seen_modules:
                                start_addr = int(address_range.split('-')[0], 16)
                                module_info = type('ModuleInfo', (), {
                                    'name': module_name,
                                    'lpBaseOfDll': start_addr
                                })()
                                modules.append(module_info)
                                seen_modules.add(module_name)
        except (OSError, IOError):
            pass
        
        return modules
    
    def find_module_by_rough_size(self, size: int, tolerance: int):
        """List modules in the process."""
        if IS_WINDOWS:
            return None  # TODO: Figure this out
        elif IS_LINUX:
            return self._find_module_rough_size_linux(size, tolerance)
        
        return None

    def _find_module_rough_size_linux(self, size: int, tolerance: int):
        """List modules on Linux by reading /proc/pid/maps."""
        if not self.process_id:
            return None
        
        try:
            with open(f"/proc/{self.process_id}/maps", "r") as maps_file:
                for line in maps_file:
                    parts = line.strip().split()
                    address_range = parts[0]
                    start_addr = int(address_range.split('-')[0], 16)
                    end_addr = int(address_range.split('-')[1], 16)
                    module_size = end_addr - start_addr
                    if module_size > (size - tolerance) and module_size < (size + tolerance):
                        return start_addr
        except (OSError, IOError):
            pass
        
        return None
    
    def read_bytes(self, address: int, size: int, n64_addr: int) -> bytes:
        """Read bytes from process memory."""
        if IS_WINDOWS:
            return self._read_bytes_windows(address, size, n64_addr)
        elif IS_LINUX:
            return self._read_bytes_linux(address, size, n64_addr)
        else:
            raise Exception("Unsupported operating system")
    
    def _read_bytes_windows(self, address: int, size: int, n64_addr: int) -> bytes:
        """Read bytes from process memory on Windows."""
        if not self.process_handle:
            raise Exception("Process not attached")
        
        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.wintypes.DWORD(0)
        
        result = ctypes.windll.kernel32.ReadProcessMemory(
            self.process_handle,
            ctypes.c_void_p(address),
            buffer,
            size,
            ctypes.byref(bytes_read)
        )
        
        if not result:
            raise Exception(f"Failed to read memory at address 0x{address:08x} (N64: 0x{n64_addr:08x})")
        
        return buffer.raw[:bytes_read.value]
    
    def _read_bytes_linux(self, address: int, size: int, n64_addr: int) -> bytes:
        """Read bytes from process memory on Linux."""
        if not self.mem_file:
            raise Exception("Process not attached")
        
        try:
            self.mem_file.seek(address)
            data = self.mem_file.read(size)
            if len(data) != size:
                raise Exception(f"Failed to read {size} bytes at address 0x{address:08x} (N64: 0x{n64_addr:08x})")
            return data
        except (OSError, IOError) as e:
            raise Exception(f"Failed to read memory at address 0x{address:08x}: {e}")
    
    def read_int(self, address: int) -> int:
        """Read a 4-byte integer from memory."""
        data = self.read_bytes(address, 4, 0)
        return int.from_bytes(data, self.endianness)
    
    def read_longlong(self, address: int) -> int:
        """Read an 8-byte long long from memory."""
        data = self.read_bytes(address, 8, 0)
        return int.from_bytes(data, self.endianness)
    
    def close(self):
        """Close the process handle or file."""
        if IS_WINDOWS and self.process_handle:
            ctypes.windll.kernel32.CloseHandle(self.process_handle)
            self.process_handle = None
        elif IS_LINUX and self.mem_file:
            self.mem_file.close()
            self.mem_file = None


class Emulators(IntEnum):
    """Emulator enum."""

    Project64 = auto()
    BizHawk = auto()
    Project64_v4 = auto()
    RMG = auto()
    Simple64 = auto()
    ParallelLauncher = auto()
    RetroArch = auto()
    ParallelLauncher903 = auto()
    Ares = auto()


class EmulatorInfo:
    """Class to store emulator information."""

    def __init__(
        self,
        id: Emulators,
        readable_emulator_name: str,
        process_name: str,
        find_dll: bool,
        dll_name: Optional[str],
        additional_lookup: bool,
        lower_offset_range: int,
        upper_offset_range: int,
        range_step: int = 16,
        extra_offset: int = 0,
        linux_dll_name: Optional[str] = None,
        find_by_size: bool = False,
        target_size: int = 0,
        size_tolerance: int = 1
    ):
        """Initialize with given parameters."""
        self.id = id
        self.readable_emulator_name = readable_emulator_name
        self.process_name = process_name
        self.find_dll = find_dll
        self.dll_name = dll_name
        self.linux_dll_name = linux_dll_name
        self.additional_lookup = additional_lookup
        self.lower_offset_range = lower_offset_range
        self.upper_offset_range = upper_offset_range
        self.range_step = range_step
        self.extra_offset = extra_offset
        self.find_by_size = find_by_size
        self.target_size = target_size
        self.size_tolerance = size_tolerance
        self.connected_process: Optional[ProcessMemory] = None
        self.connected_offset: Optional[int] = None
        self.connection_error: Optional[str] = None
        self.runtime_error: Optional[str] = None

    def get_library_name(self) -> Optional[str]:
        """Get the appropriate library name for the current platform."""
        if IS_LINUX and self.linux_dll_name:
            return self.linux_dll_name
        return self.dll_name

    def get_possible_library_names(self) -> List[str]:
        """Get a list of possible library names to search for."""
        names = []
        primary_name = self.get_library_name()
        if primary_name:
            names.append(primary_name)
            
        # Add common variations on Linux
        if IS_LINUX and self.dll_name:
            # Convert .dll to .so
            if self.dll_name.endswith('.dll'):
                so_name = self.dll_name[:-4] + '.so'
                if so_name not in names:
                    names.append(so_name)
            
            # Add lib prefix if not present
            if not self.dll_name.startswith('lib'):
                lib_name = 'lib' + self.dll_name
                if lib_name not in names:
                    names.append(lib_name)
                # Also try with .so extension
                if lib_name.endswith('.dll'):
                    lib_so_name = lib_name[:-4] + '.so'
                    if lib_so_name not in names:
                        names.append(lib_so_name)
        
        return [name for name in names if name]  # Filter out None values

    def disconnect(self):
        """Disconnect emulator from process management."""
        if self.connected_process:
            self.connected_process.close()
        self.connected_offset = None
        self.connected_process = None

    def raiseError(self, msg: str):
        print(msg)
        self.connection_error = msg

    def attach_to_emulator(self) -> Optional[Tuple[ProcessMemory, int]]:
        """Grab  memory addresses of where emulated RDRAM is."""
        # Reset
        self.connected_process = None
        self.connected_offset = None
        # Find process by name
        target_proc = None
        processes = get_running_processes()
        
        for proc in processes:
            if proc["name"]:
                if self.id == Emulators.Ares:
                    if proc["name"].lower().startswith(self.process_name.lower()):
                        print(proc["name"], self.process_name)
                    if proc["name"] != self.process_name:
                        continue
                else:
                    if not proc["name"].lower().startswith(self.process_name.lower()):
                        continue
                target_proc = proc
                break
        if not target_proc:
            self.raiseError(f"Could not find process '{self.process_name}'")
            return None

        try:
            pm = ProcessMemory(target_proc["name"], self.id)
        except Exception as e:
            self.raiseError(f"Failed to attach to process: {str(e)}")
            return None
        # print("Listing models for ", target_proc["name"])
        # print(pm.list_modules())
        # print(pm.__dict__)
        # print("----------")
        address_dll = 0
        if self.find_dll:
            possible_names = self.get_possible_library_names()
            for module in pm.list_modules():
                for lib_name in possible_names:
                    if module.name.lower() == lib_name.lower():
                        address_dll = module.lpBaseOfDll
                        print(f"Found process for {self.readable_emulator_name}: {module.name.lower()}")
                        break
                if address_dll != 0:
                    break

            if address_dll == 0 and self.id == Emulators.BizHawk:
                address_dll = 2024407040  # fallback guess
            elif address_dll == 0:
                searched_names = ", ".join(possible_names)
                self.raiseError(f"Could not find any of [{searched_names}] in {self.readable_emulator_name}")
                return None
        elif self.find_by_size:
            attempt = pm.find_module_by_rough_size(self.target_size, self.size_tolerance)
            print(attempt)
            if attempt is not None:
                address_dll = attempt
                print(hex(address_dll))

        has_seen_nonzero = False
        for pot_off in range(self.lower_offset_range, self.upper_offset_range, self.range_step):
            if self.additional_lookup:
                rom_addr_start = address_dll + pot_off
                try:
                    read_address = pm.read_longlong(rom_addr_start)
                except Exception:
                    continue
                if read_address != 0:
                    has_seen_nonzero = True
            else:
                read_address = address_dll + pot_off

            addr = read_address + self.extra_offset + 0x759290

            try:
                test_value = pm.read_int(addr)
                print(hex(addr), ":", hex(test_value))
            except Exception:
                continue
            if test_value != 0:
                has_seen_nonzero = True
            if test_value == 0x52414D42:
                self.connected_process = pm
                self.connected_offset = read_address + self.extra_offset
                return (pm, read_address + self.extra_offset)

        if not has_seen_nonzero:
            self.raiseError(f"Could not read any data from {self.readable_emulator_name}")
        
        return None

    def readBytes(self, address: int, size: int) -> int:
        """Read a series of bytes and cast to an int."""
        if self.connected_process is None or self.connected_offset is None:
            self.runtime_error = "Not connected to a process, exiting"
            raise Exception(self.runtime_error)
        if address & 0x80000000:
            address &= 0x7FFFFFFF
        mem_address = self.connected_offset + address
        data = self.connected_process.read_bytes(mem_address, size)
        value = int.from_bytes(data, "big")
        return value


EMULATOR_CONFIGS = {
    Emulators.Project64: EmulatorInfo(Emulators.Project64, "Project64", "project64", False, None, False, 0xDFD00000, 0xE01FFFFF),
    Emulators.Project64_v4: EmulatorInfo(Emulators.Project64_v4, "Project64", "project64", False, None, False, 0xFDD00000, 0xFE1FFFFF),
    Emulators.BizHawk: EmulatorInfo(Emulators.BizHawk, "Bizhawk", "emuhawk", True, "mupen64plus.dll", False, 0x5A000, 0x5658DF, linux_dll_name="libmupen64plus.so"),
    Emulators.RMG: EmulatorInfo(Emulators.RMG, "Rosalie's Mupen GUI", "rmg", True, "mupen64plus.dll", True, 0x29C15D8, 0x2FC15D8, extra_offset=0x80000000, linux_dll_name="libmupen64plus.so"),
    Emulators.Simple64: EmulatorInfo(Emulators.Simple64, "simple64", "simple64-gui", True, "libmupen64plus.dll", True, 0x1380000, 0x29C95D8, linux_dll_name="libmupen64plus.so"),
    Emulators.ParallelLauncher: EmulatorInfo(Emulators.ParallelLauncher, "Parallel Launcher (<9.0.2)", "retroarch", True, "parallel_n64_next_libretro.dll", True, 0x845000, 0xD56000, linux_dll_name="parallel_n64_next_libretro.so"),
    Emulators.RetroArch: EmulatorInfo(Emulators.RetroArch, "RetroArch", "retroarch", True, "mupen64plus_next_libretro.dll", True, 0, 0xFFFFFF, range_step=4, linux_dll_name="mupen64plus_next_libretro.so"),
    Emulators.ParallelLauncher903: EmulatorInfo(Emulators.ParallelLauncher903, "Parallel Launcher (9.0.3+)", "retroarch", True, "parallel_n64_next_libretro.dll", True, 0x1400000, 0x1800000, linux_dll_name="parallel_n64_next_libretro.so"),
    Emulators.Ares: EmulatorInfo(Emulators.Ares, "Ares", "ares", False, None, False, 0x9A70000, 0x9A74000, find_by_size=True, target_size=0xB462000, size_tolerance=0x1001)
}


def attachWrapper(emu: Emulators) -> EmulatorInfo:
    """Wrap function for attaching to an emulator."""
    EMULATOR_CONFIGS[emu].attach_to_emulator()
    return EMULATOR_CONFIGS[emu]
