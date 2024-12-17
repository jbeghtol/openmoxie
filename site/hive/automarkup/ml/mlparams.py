"""This holds all global parameters for data-model training as well as markup rules."""

import os
import pathlib
import re
import string

_FILE_DIR = os.path.dirname(__file__)
DATA_PATH = "../../../data"
EXE_DATA_PATH = 'data'
CSV_PATH = str(pathlib.Path(_FILE_DIR, os.path.join(DATA_PATH, "csLines_200715.csv")).resolve())
ML_DATA_PATH = str(pathlib.Path(_FILE_DIR, os.path.join(DATA_PATH, "_mlprocesseddata.txt")).resolve())
ML_DATA_EXE_PATH = str(pathlib.Path(_FILE_DIR, os.path.join(EXE_DATA_PATH, "_mlprocesseddata.txt")).resolve())
TXT_REPLACE_FILE_PATH = str(pathlib.Path(_FILE_DIR, os.path.join(DATA_PATH, "text_replacement.json")).resolve())
TXT_REPLACE_FILE_EXE_PATH = str(pathlib.Path(_FILE_DIR, os.path.join(EXE_DATA_PATH, "text_replacement.json")).resolve())

# Overall knobs
RESTRICT_TO_DISTINCT_TAG = True # Default False; True = ONLY look at all of the same tags (ie. Only look at all vocalVariant usage, ignoring any non-marked/otherwise-marked words)
IGNORE_MARKUP_ATTRIB = False # Default False (When this is True, you'll likely want RESTRICT_TO_DISTINCT_TAG=False, otherwse 0 rules)
SHOW_MISSED_TAGS = False
MARKUP_GESTURES = True

# Markup params
ADD_AUTO_GENERATED_ATTRIB = True
REMOVE_SINGLE_WORD_USEL_TAGS = True
ACCEPTED_SINGLE_WORD_USEL_TAGS = ['question', 'motivational', 'excited']

# Breaks between sentences
PAUSE_LARGE_TEXT = 0.7
PAUSE_DEFAULT = 0.2
LARGE_TEXT_SENTENCE_THRESHOLD = 6
SYNTH_RATE_DEFAULT = 1.0
SYNTH_RATE_LARGE_TEXT = 0.95

# Tags we care about
tagNameFormat = "{{\"{0}\": "
TAG_SIG = tagNameFormat.format('sig')
TAG_USEL = tagNameFormat.format("usel")
TAG_PROSODY = tagNameFormat.format("prosody")
TAG_EMPHASIS = tagNameFormat.format("emphasis")
TAG_BREAK = tagNameFormat.format("break")
TAG_LEX = tagNameFormat.format("lex")
TAG_PHONEME = tagNameFormat.format("phoneme")
TAG_MARK = tagNameFormat.format("mark")
TAG_ROOT = tagNameFormat.format("root")

# TAGS = [TAG_USEL, TAG_PROSODY, TAG_EMPHASIS, TAG_BREAK, TAG_LEX, TAG_PHONEME]#, TAG_MARK, TAG_ROOT]
TAGS = [TAG_USEL, TAG_PROSODY, TAG_EMPHASIS, TAG_LEX]#, TAG_MARK, TAG_ROOT]

# Using alias so tags with the same name (but for different things) can be added to the dictionary of words-to-tags
# ie. both behavior markup and mood markup uses <mark /> format
# Update below aliastotag()
TAG_BREAK_BASE = "break"
TAG_MARK_BEHAVIOR = "mark"
ALIAS_TAG_MARK_MOOD = "mark_mood"
ALIAS_TAGS = [ ALIAS_TAG_MARK_MOOD ]
ALIAS_TAGS_MAP = [ "mark" ]

UNSCOPED_TAGS = [ TAG_BREAK_BASE, TAG_MARK_BEHAVIOR, ALIAS_TAG_MARK_MOOD ]

IGNORE_WORDS_LIST = [ ] #"a", "of", "for", "I", "to", "me", "if" ]
IGNORE_WORD_IF_SHORTER_THAN = 3

# Voice
CLAMP_MAX_USEL_VARIANT = 3

# MOOD
MOOD_INTENSITY_MAX = 2 # 0-based

# GESTURES & BEHAVIOR
GESTURE_CHANGE_WORDS_MIN = 3
GESTURE_CHANGE_WORDS_MAX = 7

# NLP JSON DATA
NLP_JSON_UTTERANCE = "utterance"
NLP_JSON_SENTENCES = "sentences"
NLP_JSON_SUBSENTENCES = "subsentences"
NLP_JSON_TOKENS = "tokens"
NLP_JSON_START_INDEX = "start_index"
NLP_JSON_END_INDEX = "end_index"
NLP_JSON_DIALOG_ACT = "dialog_act"
NLP_JSON_MARK = "mark"
NLP_JSON_VALUE = "value"
NLP_JSON_CONFIDENCE = "confidence"
NLP_JSON_IMPORTANCE = "importance"
NLP_JSON_QUESTION = "question"
NLP_JSON_MOOD = "emotion"

# XML Generation
IGNORE_TAGS_LIST = [ "phoneme", "emphasis", "lex" ]
MAX_SPAN_MERGE_WORD_SEPARATION = 5 #20

# Rule algorithm thresholds and values
APRIORI_VALUES = {
    TAG_USEL : {
        "min_support": 0.0001, # 0.00015 gets me 93 rules, 05 will likely be pretty awesome-tastic
        "min_confidence": 0.15,
        "min_lift": 2,
        "min_length": 2
    },
    TAG_PROSODY : {
        "min_support": 0.00015,
        "min_confidence": 0.15,
        "min_lift": 2,
        "min_length": 2
    },
    TAG_EMPHASIS : {
        "min_support": 0.0005,
        "min_confidence": 0.2,
        "min_lift": 2,
        "min_length": 2
    },
    TAG_BREAK : {
        "min_support": 0.0045,
        "min_confidence": 0.2,
        "min_lift": 2,
        "min_length": 2
    },
    TAG_LEX : {
        "min_support": 0.0025,
        "min_confidence": 0.2,
        "min_lift": 2,
        "min_length": 2
    },
    TAG_PHONEME : {
        "min_support": 0.0005,
        "min_confidence": 0.2,
        "min_lift": 2,
        "min_length": 2
    },
    TAG_MARK : {
        "min_support": 0.0005,
        "min_confidence": 0.2,
        "min_lift": 2,
        "min_length": 2
    },

    # The root can be left as default and last, it is ignored from rule generation
    TAG_ROOT : {
        "min_support": 0.0005,
        "min_confidence": 0.2,
        "min_lift": 2,
        "min_length": 2
    }
}

SPECIAL_CHARS = re.escape(string.punctuation.replace("'", "").replace("_", ""))
CHAR_EOL = "__EOL__"

def aliastotag(alias):
    """Converts the markup tag alias to its original name."""
    if alias in ALIAS_TAGS:
        index = ALIAS_TAGS.index(alias)
        return ALIAS_TAGS_MAP[index]
    return alias
