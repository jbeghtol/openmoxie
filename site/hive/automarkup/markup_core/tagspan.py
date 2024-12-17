from typing import Tuple


class TagSpan:
    associated_str: str = ""
    start_index: int = -1
    end_index: int = -1
    size: int = 0

    def __init__(self, _associated_str: str, _start_index: int, _end_index: int):
        self.associated_str = _associated_str
        self.start_index = _start_index
        self.end_index = _end_index
        self.size = _end_index + 1 - _start_index

    def conflicts(self, b) -> Tuple[bool, str]:
        conflicted: bool = False
        if self.size == 1 or b.size == 1:
            msg = "OK 1-word"
        elif self.start_index < b.start_index and self.end_index >= b.start_index and self.end_index < b.end_index:
            msg = "OUT OF RANGE"
            conflicted = True
        elif b.start_index < self.start_index and b.end_index >= self.start_index and b.end_index < self.end_index:
            msg = "OUT OF RANGE 2"
            conflicted = True
        else:
            msg = "OK"

        return conflicted, msg
