"""Basic class structure for defining apyori association parameters."""

from json import JSONEncoder


class Rule:
    associated_str: str = ""
    support: float = 0
    confidence: float = 0
    lift: float = 0

    def __init__(self, associated_str: str = "", support: float = 0, confidence: float = 0, lift: float = 0):
        self.associated_str = associated_str
        self.support = support
        self.confidence = confidence
        self.lift = lift


class RuleEncoder(JSONEncoder):
    def default(self, o):
        return o.__dict__
