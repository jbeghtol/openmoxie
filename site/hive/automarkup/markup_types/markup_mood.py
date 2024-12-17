# -*- coding: utf-8 -*-
"""Adds mood markups to input list of words.

Sub-module to markup.py.
"""

import json
import logging
from typing import Dict, List, Union

from ..utils import bcolors
from .. import markup as m
from ..ml import mlparams
from .._version import __package_version__

TAG = mlparams.ALIAS_TAG_MARK_MOOD

MOOD_NEUTRAL = "0"
MOOD_HAPPY = "1"
MOOD_SAD = "2"
MOOD_ANGRY = "3"
MOOD_SHY = "4"
MOOD_SURPRISED = "5"
MOOD_AFRAID = "6"
MOOD_CONCERNED = "7"
MOOD_CONFUSED = "8"
MOOD_CURIOUS = "9"
MOOD_EMBARRASSED = "10"


MOOD_MAP = {
    # preserving these already mapped moods for backward compatibility
    # toberemoved after remote chat is modified to send the originals
    "happy":        {"type": MOOD_HAPPY, "steps": [ 0, 0.333, 0.666 ]}, 
    "positive":     {"type": MOOD_HAPPY, "steps": [ 0, 0.333, 0.666 ]}, 
    "angry":        {"type": MOOD_ANGRY, "steps": [ 0, 0.333, 0.666 ]},
    "sad":          {"type": MOOD_SAD, "steps": [ 0, 0.333, 0.666 ]}, 
    "negative":     {"type": MOOD_SAD, "steps": [ 0, 0.333, 0.666 ]},
    "shy":          {"type": MOOD_SHY, "steps": [ 0, 0.333, 0.666 ]}, 
    "afraid":       {"type": MOOD_AFRAID, "steps": [ 0, 0.333, 0.666 ]}, 
    "concerned":    {"type": MOOD_CONCERNED, "steps": [ 0, 0.333, 0.666 ]},
    "confused":     {"type": MOOD_CONFUSED, "steps": [ 0, 0.333, 0.666 ]},
    "curious":      {"type": MOOD_CURIOUS, "steps": [ 0, 0.333, 0.666 ]},
    "embarrassed":  {"type": MOOD_EMBARRASSED, "steps": [ 0, 0.333, 0.666 ]},

    # this is the mapping for actual original list
    "fear":         {"type": MOOD_AFRAID, "steps": [ 0, 0.333, 0.666 ]},
    "anger":        {"type": MOOD_ANGRY, "steps": [ 0, 0.333, 0.666 ]},
    "annoyance":    {"type": MOOD_CONCERNED, "steps": [ 0, 0.333, 0.666 ]},
    "disapproval":  {"type": MOOD_CONCERNED, "steps": [ 0, 0.5 ]},
    "disgust":      {"type": MOOD_CONCERNED, "steps": [ 0, 0.333, 0.666 ]},
    "confusion":    {"type": MOOD_CONFUSED, "steps": [ 0, 0.333, 0.666 ]},
    "curiosity":    {"type": MOOD_CURIOUS, "steps": [ 0, 0.333, 0.666 ]},
    "embarrassment": {"type": MOOD_EMBARRASSED, "steps": [ 0, 0.333, 0.666 ]},
    "love":         {"type": MOOD_HAPPY, "steps": [ 0, 0.333, 0.666 ]},
    "admiration":   {"type": MOOD_HAPPY, "steps": [ 0, 0.5 ]},
    "approval":     {"type": MOOD_HAPPY, "steps": [ 0, 0.5 ]},
    "joy":          {"type": MOOD_HAPPY, "steps": [ 0, 0.333, 0.666 ]},
    "gratitude":    {"type": MOOD_HAPPY, "steps": [ 0, 0.5 ]},
    "optimism":     {"type": MOOD_HAPPY, "steps": [ 0, 0.5 ]},
    "desire":       {"type": MOOD_HAPPY, "steps": [ 0, 0.5 ]},
    "amusement":    {"type": MOOD_HAPPY, "steps": [ 0, 0.333, 0.666 ]},
    "pride":        {"type": MOOD_HAPPY, "steps": [ 0, 0.5 ]},
    "caring":       {"type": MOOD_HAPPY, "steps": [ 0, 0.5 ]},
    "relief":       {"type": MOOD_NEUTRAL, "steps": [ 0, 0.333, 0.666 ]},
    "neutral":      {"type": MOOD_NEUTRAL, "steps": [ 0, 0.333, 0.666 ]},
    "sadness":      {"type": MOOD_SAD, "steps": [ 0, 0.333, 0.666 ]},
    "disappointment": {"type": MOOD_SAD, "steps": [ 0, 0.5 ]},
    "remorse":      {"type": MOOD_SAD, "steps": [ 0, 0.5 ]},
    "grief":        {"type": MOOD_SAD, "steps": [ 0, 0.333, 0.666 ]},
    "nervousness":  {"type": MOOD_SHY, "steps": [ 0, 0.333, 0.666 ]},
    "excitement":   {"type": MOOD_SURPRISED, "steps": [ 0, 0.5 ]},
    "realization":  {"type": MOOD_SURPRISED, "steps": [ 0, 0.5 ]},
    "surprise":     {"type": MOOD_SURPRISED, "steps": [ 0, 0.333, 0.666 ]}
}

class MarkupMood:
    mood: str = ""
    intensity: int = 0
    b_dict: Dict[str, Dict[str, str]] = {}

    def __init__(self, mood, intensity):
        self.mood = mood
        self.intensity = min(intensity, mlparams.MOOD_INTENSITY_MAX)
        self.b_dict[mlparams.ALIAS_TAG_MARK_MOOD] = {}
        self.b_dict[mlparams.ALIAS_TAG_MARK_MOOD]["name"] = 'cmd:playback-mood,data:{+mood+:' + self.mood + ',+intensity+:' + str(self.intensity) + '}'

    def json(self):
        return json.dumps(self.b_dict)

def get_intensity_level(intensity: float, steps: List[float]):
    # we expect normalized intensity in [0,1] range
    intensity = max(0.0, min(intensity, 1.0))
    # output intensity (default 0)
    out_intensity: int = 0
    i = 0
    while i < len(steps):
        if intensity > steps[i]:
            out_intensity = i
        else:
            break
        i += 1    
    return out_intensity

def get_emotion(mood: str, intensity: float):
    mood_info = MOOD_MAP["neutral"]
    if mood in MOOD_MAP:
        mood_info = MOOD_MAP[mood]
    else:
        logging.error("{}Invalid mood: {}. Using default: NEUTRAL{}".format(bcolors.WARNING, mood, bcolors.ENDC))

    return mood_info['type'], get_intensity_level(intensity, mood_info['steps'])



def markup(words: List[str], mood: str = None, intensity: float = 0) -> List[Union[MarkupMood, None]]:
    """
    Markup mood playback on the provided list of words. Returns a list of rules the same size
    as the list of words.

    Arguments:
        words - words in the sentence. Expects the last word to be special __EOL___ string
        mood (optional) - any one of the following: happy, sad, angry, shy, surprised, positive, negative
        intensity (optional) - normalized mood intensity, default 0
    """
    if words[-1] != mlparams.CHAR_EOL:
        words.append(mlparams.CHAR_EOL)

    out_rules: List[Union[MarkupMood, None]] = []
    for w in words:
        out_rules.append(None)

    emotion = get_emotion(mood, intensity)
    out_rules[0] = MarkupMood(*emotion).json()
    
    # always end with neutral
    out_rules[-1] = MarkupMood(MOOD_NEUTRAL, 0).json()

    return out_rules
