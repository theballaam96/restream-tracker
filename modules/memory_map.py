# DK64 Memory Map constants
class DK64MemoryMap:
    memory_pointer = 0x807FC8A0  # Main memory pointer
    count_struct_pointer = 0x807FFFB8  # CountStruct pointer address (fixed to match working version)
    
    # Direct memory addresses that are commonly used
    map_index = 0x807444E4
    exit_index = 0x807444E8
    void_byte = 0x807FBB60
    player_pointer = 0x807FBB4C

    # Actor
    actor_list = 0x807FBFF0
    actor_count = 0x807FC3F0
    loaded_actor_array = 0x807FB930

    # Heap
    heap_arena_meta = 0x807F0988
    heap_arena_count = 0x807F0A28

class ActorStruct:
    actor_type = 0x58
    x_pos = 0x7C
    y_pos = 0x80
    z_pos = 0x84
    y_velocity = 0xC0
    pad_lock = 0x110
    collision_pointer = 0x13C
    control_state = 0x154
    control_state_progress = 0x155
    vehicle_pointer = 0x208