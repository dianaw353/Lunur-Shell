import json
import subprocess
from typing import Iterator

modmask_map = {
    64: "SUPER",
    8: "ALT",
    4: "CTRL",
    1: "SHIFT",
}

def modmask_to_key(modmask: int) -> str:
    keys = [key for bf, key in modmask_map.items() if (modmask & bf) == bf]
    known_bits = sum(bf for bf in modmask_map.keys())
    unknown_bits = modmask & (~known_bits)
    if unknown_bits != 0:
        keys.append(f"({unknown_bits})")
    return " + ".join(keys)

class KeybindLoader:
    def __init__(self):
        self.keybinds = []

    def load_keybinds(self):
        try:
            output = subprocess.check_output(["hyprctl", "binds", "-j"], text=True)
            binds = json.loads(output)
        except Exception as e:
            print(f"ERROR: Failed to load keybinds from hyprctl: {e}")
            self.keybinds = []
            return

        self.keybinds.clear()
        for bind in binds:
            key_combo = f"{modmask_to_key(bind['modmask'])} + {bind['key']}:"
            description = bind.get('description', '').strip()
            dispatcher = bind.get('dispatcher', '').strip()
            arg = bind.get('arg', '').strip()
            cmd = f"{dispatcher}: {arg}".strip(": ")
            self.keybinds.append((key_combo.strip(), description, cmd))

    def filter_keybinds(self, query: str = "") -> Iterator[tuple]:
        query_cf = query.casefold()
        return (kb for kb in self.keybinds if query_cf in " ".join(kb).casefold())
