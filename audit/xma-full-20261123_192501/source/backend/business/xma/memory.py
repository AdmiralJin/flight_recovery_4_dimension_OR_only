"""Resource limits shared by the XMA campaign supervisor and first-solution search."""

GIB = 1024**3
DEFAULT_MEMORY_GIB = 6
ADMISSION_FRACTION = 0.70


def admission_bytes(memory_gib: int) -> int:
    if memory_gib <= 0:
        raise ValueError("memory_gib must be positive")
    return int(memory_gib * GIB * ADMISSION_FRACTION)
