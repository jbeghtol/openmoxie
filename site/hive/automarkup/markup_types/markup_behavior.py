"""Adds gestural markups to input list of words based the following basic rules (see README.md for more info).
- Change gesture every new sentence. (even if it's just changing poses of the same gesture).
- Change gestures between 5 and 8 words. (this is a VERY vague guideline, it depends on the line).
- Use GESTURE_SELF gesture for thoughts that are softer (please, may I, rainbow, happy, love...)
- Use GESTURE_QSTN gesture for thoughts that are more aggressive (you should, great!, hey, awesome, etc...)
- End with a "None" gesture

Sub-module to markup.py.
"""

import json
import logging
import random
from string import punctuation
from typing import List, Dict

from ..utils import bcolors
from .. import markup as m
from ..ml import mlparams
from .._version import __package_version__

TAG = mlparams.TAG_MARK_BEHAVIOR
GESTURE_CHANGE_WORDS_MIN = mlparams.GESTURE_CHANGE_WORDS_MIN
GESTURE_CHANGE_WORDS_MAX = mlparams.GESTURE_CHANGE_WORDS_MAX

GESTURE_NONE = "AUTO_GESTURE_NONE"
GESTURE_TALK = "AUTO_GESTURE_TALK"
GESTURE_TALK_PRIORITY = "AUTO_GESTURE_TALK_PRIORITY"
GESTURE_QSTN = "Gesture_Question"
GESTURE_SELF = "AUTO_GESTURE_ME"
GESTURE_YOU = "AUTO_GESTURE_YOU"
GESTURE_US = "Gesture_We"
GESTURE_HIGH = "Gesture_Higher"
GESTURE_LOW = "Gesture_Lower"
GESTURE_BIG = "Gesture_Large"
GESTURE_SMALL = "Gesture_Small"
GESTURE_DIRECTION = "Gesture_Discard"

GESTURE_PROBABILITY = 0.8  # 80% chance

GESTURE_MAP = {
    "spacial:small": GESTURE_SMALL, "spacial:big": GESTURE_BIG,
    "spacial:low": GESTURE_LOW, "spacial:high": GESTURE_HIGH,
    "spacial:direction": GESTURE_DIRECTION,
    "self": GESTURE_SELF, "you": GESTURE_YOU, "we": GESTURE_US
}

# All lower-case here
WORDS_QUESTION = ["please", "who", "what", "where", "how", "curious", "wondering", "question"]
WORDS_SELF = ["i", "me", "us", "my", "mine", "myself"]
WORDS_YOUU = ["you", "your"]
WORDS_HIGH = ["up", "above", "higher", "high", "wow", "great", "fantastic", "wonderful", "amazing", "awesome", "yay", "fun"]

def gesture_change_word_count():
    return random.randint(GESTURE_CHANGE_WORDS_MIN, GESTURE_CHANGE_WORDS_MAX)

class MarkupBehavior:
    behavior_name: str = ""
    b_dict: Dict[str, Dict[str, str]] = {}

    def __init__(self, behavior_name: str):
        self.behavior_name = behavior_name
        self.b_dict[TAG] = {}
        self.b_dict[TAG]["name"] = 'cmd:behaviour-tree,data:{+transition+:0.5,+duration+:1.0,+repeat+:1,+layerBlendInTime+:0.5,+layerBlendOutTime+:0.5,+blocking+:false,+action+:4,+variableName+:++,+variableValue+:++,+eventName+:+' + self.behavior_name + '+,+lifetime+:0,+category+:+None+,+behaviour+:++,+Track+:++}'

    def json(self):
        return json.dumps(self.b_dict)


def CanMarkupFit(markedIndices, index, minDistance, hasPunctuation: bool = False):
    """Checks if a markup/gesture can fit based on number-of-words distance from list of marked-words indices"""
    markedIndices.sort()
    i = 0
    while i < len(markedIndices)-1:

        lowerIndex = markedIndices[i]
        upperIndex = markedIndices[i+1]

        lowerIndexOffset = lowerIndex if hasPunctuation else (lowerIndex + minDistance)
        upperIndexOffset = upperIndex if hasPunctuation else (upperIndex - minDistance)

        logging.debug("{} <= {} ? {}".format(lowerIndexOffset,upperIndexOffset,(lowerIndexOffset <= upperIndexOffset)))
        if lowerIndexOffset <= upperIndexOffset:
            logging.debug("{} > {} AND {} < {} ? {}".format(index,lowerIndexOffset,index,upperIndexOffset,(index > lowerIndexOffset and index < upperIndexOffset)))
            if index > lowerIndexOffset and index < upperIndexOffset:
                return True
        i += 1
    
    return False

def get_behaviors_from_str(words: List[str], orig_words: List[str], outRules: List[MarkupBehavior]):
    logging.debug("Adding behavior markup using default method")

    # Bool-dict per word to see which words might have gestures correlating with them
    b_dict: Dict[str, List[bool]] = {}
    b_dict[GESTURE_QSTN] = []
    b_dict[GESTURE_SELF] = []
    b_dict[GESTURE_YOU] = []
    b_dict[GESTURE_HIGH] = []
    b_dict[GESTURE_TALK_PRIORITY] = []
    b_dict[GESTURE_TALK] = []
    b_dict[GESTURE_NONE] = []
    lastGestureIndex = 0
    gestureChangeWordCount = gesture_change_word_count()
    logging.debug("Will change words at {} words".format(gestureChangeWordCount))
    multiSentence = False
    i = 0
    while i < len(words) - 1:
        lastWordHasPeriod = False
        if i > 0:
            lastWord = orig_words[i - 1]
            lastWordHasPeriod = "." in lastWord or "?" in lastWord
            if i < len(words) - 2 and lastWordHasPeriod:
                multiSentence = True
        word = words[i]
        origWord = orig_words[i]
        b_dict[GESTURE_QSTN].append(word in WORDS_QUESTION or "?" in origWord)
        b_dict[GESTURE_TALK_PRIORITY].append(lastWordHasPeriod or i == 0)
        b_dict[GESTURE_SELF].append(word in WORDS_SELF and random.random() <= GESTURE_PROBABILITY)
        b_dict[GESTURE_YOU].append(word in WORDS_YOUU and random.random() <= GESTURE_PROBABILITY)
        b_dict[GESTURE_HIGH].append(word in WORDS_HIGH and random.random() <= GESTURE_PROBABILITY)
        b_dict[GESTURE_NONE].append(False)

        # Talk gestures are on a number-of-words basis
        doTalkGesture = False
        if (i - lastGestureIndex) >= gestureChangeWordCount:
            doTalkGesture = True
            gestureChangeWordCount = gesture_change_word_count()
            logging.debug("Next word will be {} words later (at index {})".format(gestureChangeWordCount, i + gestureChangeWordCount))
            lastGestureIndex = i
        b_dict[GESTURE_TALK].append(doTalkGesture)

        i += 1

    # Last EOL word is always Gesture_None
    b_dict[GESTURE_QSTN].append(False)
    b_dict[GESTURE_SELF].append(False)
    b_dict[GESTURE_YOU].append(False)
    b_dict[GESTURE_HIGH].append(False)
    b_dict[GESTURE_TALK_PRIORITY].append(False)
    b_dict[GESTURE_TALK].append(False)
    b_dict[GESTURE_NONE].append(True)

    # Debugging
    # if getattr(logging):
    msgW = "{:30}".format("word")
    msgQ = "{:30}".format(GESTURE_QSTN)
    msgS = "{:30}".format(GESTURE_SELF)
    msgY = "{:30}".format(GESTURE_YOU)
    msgH = "{:30}".format(GESTURE_HIGH)
    msgTP = "{:30}".format(GESTURE_TALK_PRIORITY)
    msgT = "{:30}".format(GESTURE_TALK)
    msgN = "{:30}".format(GESTURE_NONE)
    i = 0
    while i < len(words):
        word = words[i]
        msgW = "{}{:<15}".format(msgW, word)
        msgQ = "{}{:<15}".format(msgQ, b_dict[GESTURE_QSTN][i] if b_dict[GESTURE_QSTN][i] else "")
        msgS = "{}{:<15}".format(msgS, b_dict[GESTURE_SELF][i] if b_dict[GESTURE_SELF][i] else "")
        msgY = "{}{:<15}".format(msgY, b_dict[GESTURE_YOU][i] if b_dict[GESTURE_YOU][i] else "")
        msgH = "{}{:<15}".format(msgH, b_dict[GESTURE_HIGH][i] if b_dict[GESTURE_HIGH][i] else "")
        msgTP = "{}{:<15}".format(msgTP, b_dict[GESTURE_TALK_PRIORITY][i] if b_dict[GESTURE_TALK_PRIORITY][i] else "")
        msgT = "{}{:<15}".format(msgT, b_dict[GESTURE_TALK][i] if b_dict[GESTURE_TALK][i] else "")
        msgN = "{}{:<15}".format(msgN, b_dict[GESTURE_NONE][i] if b_dict[GESTURE_NONE][i] else "")
        i += 1

    logging.debug(msgW)
    logging.debug(msgQ)
    logging.debug(msgS)
    logging.debug(msgY)
    logging.debug(msgH)
    logging.debug(msgTP)
    logging.debug(msgT)
    logging.debug(msgN)

    # Assemble rules
    indicesMarked = [ 0, len(words) - 1 ] # first and last always marked
    for tag in [GESTURE_HIGH, GESTURE_SELF, GESTURE_YOU, GESTURE_TALK_PRIORITY, GESTURE_QSTN, GESTURE_TALK]: # In this order of importance
        # Clean up the alias tag for my faux PRIORITY layer
        thisTag = tag
        if tag == GESTURE_TALK_PRIORITY:
            thisTag = GESTURE_TALK

        i = 0
        while i < len(words) - 1:
            if b_dict[tag][i]:
                hasPunctuation = any(p in orig_words[i-1] or (i+1<len(orig_words) and p in orig_words[i+1]) for p in punctuation)
                logging.debug("Checking fit for {}".format(tag))
                if CanMarkupFit(indicesMarked, i, GESTURE_CHANGE_WORDS_MIN, hasPunctuation):
                    indicesMarked.append(i)

                    behaviorMarkup = MarkupBehavior(thisTag)
                    outRule = behaviorMarkup.json()
                    outRules[i] = outRule

            i += 1

    # Shift all rules up one spot for anticipation in animation
    offset = 2
    outRulesShifted = [None] * len(outRules)
    lastRule = len(outRules) - 1
    i = 1
    while i < lastRule:
        if outRules[i]:
            # don't shift up marks too close to start
            if i-offset < GESTURE_CHANGE_WORDS_MIN:
                outRulesShifted[i] = outRules[i]
            # swap question with starting auto gesture talk if one sentence volley
            elif GESTURE_QSTN in outRules[i] and not multiSentence:
                outRulesShifted[0] = outRules[i]
                outRulesShifted[i-offset] = outRules[0]
            # remove rules at tail end
            elif lastRule-(i-offset) < GESTURE_CHANGE_WORDS_MIN:
                break
            else:
                outRulesShifted[i-offset] = outRules[i]
        i += 1
    # add auto gesture talk to start if nothing there
    if not outRulesShifted[0]:
        outRulesShifted[0] = outRules[0]
    # add last rule (AUTO_GESTURE_NONE)
    outRulesShifted[lastRule] = outRules[lastRule]
    # End shift

    logging.debug("Behavior markup rules")
    for r in outRulesShifted:
        logging.debug("    {}".format(r))

    return outRulesShifted

def markup(words: List[str], orig_words: List[str]):
    """
    Markup gestural behaviors on the provided list of words. Returns a list of rules the same size
    as the list of words.

    Arguments:
        words - words in the sentence. Expects the last word to be special __EOL___ string
        orig_words - unmodified words in the original sentence
    """
    if words[-1] != mlparams.CHAR_EOL:
        words.append(mlparams.CHAR_EOL)

    # Initialize rules as None
    outRules = []
    for w in words:
        outRules.append(None)
    outRules[0] = MarkupBehavior(GESTURE_TALK).json()
    outRules[-1] = MarkupBehavior(GESTURE_NONE).json()

    return get_behaviors_from_str(words, orig_words, outRules)
