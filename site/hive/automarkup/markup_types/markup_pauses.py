import json
from typing import List

from .markup_base import MarkupBase
from ..ml import mlparams


class MarkupPauses(MarkupBase):
    TAG = mlparams.TAG_BREAK_BASE

    @staticmethod
    def as_string(pause_seconds: float) -> str:
        data: dict = {}
        data[MarkupPauses.TAG] = {}
        data[MarkupPauses.TAG]["time"] = str(pause_seconds)+'s'
        return json.dumps(data)

    @staticmethod
    def markup(words: List[str], orig_words: List[str], **kwargs):
        pause_seconds = kwargs["pause_seconds"]

        # Iterate through every word, ignoring the last word
        # We do not want to add pauses to the last word even if it denotes the end of the sentence,
        # so to not add delays in volleys/turn-taking
        # Note: "-2" because we had already inserted "__EOL__" as the last word
        i: int = 0
        num_words_skip = 2
        markup_rules = []
        last_word_is_acronym = False
        mark_next_word_with_pause = False
        while i < (len(words) - num_words_skip):
            the_orig_word = orig_words[i]

            # Take care of previous loop's conditions
            if mark_next_word_with_pause:
                markup_rules.append(MarkupPauses.as_string(pause_seconds=pause_seconds))
                mark_next_word_with_pause = False
            else:
                markup_rules.append(None)

            # Skip any acronyms like "G.R.L."
            if len(the_orig_word.split(".")) > 2:
                last_word_is_acronym = True
                i += 1
                continue

            if len(orig_words[i]) > 0 and orig_words[i][-1] == ".":
                if not last_word_is_acronym:
                    mark_next_word_with_pause = True

            last_word_is_acronym = False
            i += 1

        for i in range(num_words_skip):
            markup_rules.append(None)
        return markup_rules

    @staticmethod
    def pause_rule(words: List[str], pause_seconds: float) :
        rules = [None]*len(words)
        rules[len(words)-1] = MarkupPauses.as_string(pause_seconds=pause_seconds)
        return rules