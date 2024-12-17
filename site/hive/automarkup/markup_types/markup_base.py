from abc import ABC, abstractmethod
from typing import List


class MarkupBase(ABC):
    @staticmethod
    @abstractmethod
    def markup(words: List[str], orig_words: List[str], **kwargs):
        pass
