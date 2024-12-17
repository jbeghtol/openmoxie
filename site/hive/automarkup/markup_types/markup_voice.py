"""Adds voice markups to input list of words based on data module (rules).

Sub-module to markup.py.
"""

import logging
import random
import xml.etree.ElementTree as ET
from typing import List

from ..utils import bcolors
from ..ml import mlparams
from ..ml import mlrules_utils

CLAMP_MAX_USEL_VARIANT = mlparams.CLAMP_MAX_USEL_VARIANT


def vocal_variant(genre: str, variant: int = 0, specialMark: bool = False) -> str:
    tag = mlrules_utils.clean_dict_key_str(mlparams.TAG_USEL)
    element = ET.Element(tag)
    element.attrib["genre"] = genre
    element.attrib["variant"] = str(variant)
    if specialMark:
        element.attrib['source'] = 'mark'
    return mlrules_utils.serialize_element(element)



def markup(words: List[str], orig_words: List[str], rules: dict, markVoiceSpecialMarkGenre: bool = True, 
           synthRate: float = mlparams.SYNTH_RATE_DEFAULT, debug=False):
    """
    Generate a nested list of rules-per-word

    Params
    origWords (string list) - Original words, with punctuation et al. to test for "?"
    markVoiceSpecialMarkGenre (bool) - Checks for '?' or '!' chars and marks sub-phrase with 
                                        corresponding "question" or "excited/motivational" vocalVariant genre. 
                                        Default is True.
    """
    def markup_synth_rate(synthRate: float, words: List[str]) ->  dict:
        sigTag = mlparams.TAG_SIG + "{{\"rate\": \"{}\"}}}}".format(synthRate)
        return {} if synthRate == mlparams.SYNTH_RATE_DEFAULT \
                  else  {"sig": [sigTag]*(len(words)-1) + [None] }

    rulesPerWordDict = markup_synth_rate(synthRate=synthRate, words=words)
    for tag in rules.keys():
        if tag in mlparams.IGNORE_TAGS_LIST:
            logging.debug("Skipping tag '{}' since it is marked in the IGNORE list".format(tag))
            continue
        tagRules = rules[tag]
        tagRulesApplied = []

        isUselTag = tag == mlrules_utils.clean_dict_key_str(mlparams.TAG_USEL)
        isProsodyTag = tag == mlrules_utils.clean_dict_key_str(mlparams.TAG_PROSODY)
        if debug:
            if isUselTag: print("{}Check usel variants and clamping{}".format(bcolors.PURPLE, bcolors.ENDC))
            if isProsodyTag: print("{}Check prosody rates and clamping{}".format(bcolors.PURPLE, bcolors.ENDC))

        lastUselRule = None
        for w in words:
            wordRule = None
            if w in tagRules.keys():
                # TODO: Mechanism to CHOOSE a rule. For now default to the first one
                wordRule = tagRules[w][0].associated_str

                # This is where some higher-level rules are applied, based on observed style
                # Check usel variants and clamping
                if isUselTag:
                    e = mlrules_utils.deserialize_element(wordRule)
                    varAttrib = int(e.attrib["variant"])
                    logging.debug("    word={}, tag={}, variant={}".format(w, mlrules_utils.clean_dict_key_str(mlparams.TAG_USEL), varAttrib))
                    if varAttrib > CLAMP_MAX_USEL_VARIANT:
                        newVarAttrib = random.randint(0, CLAMP_MAX_USEL_VARIANT)
                        e.attrib["variant"] = str(newVarAttrib)
                        logging.debug("        Variant ({}) larger than max-constrained-value per this script of {}. Variant now set to {}".format(varAttrib, CLAMP_MAX_USEL_VARIANT, newVarAttrib))
                        wordRule = mlrules_utils.serialize_element(e)

                    if lastUselRule is not None and lastUselRule["genre"] == e.attrib["genre"]:
                        e.attrib["variant"] = lastUselRule["variant"]
                        logging.debug("        Modifying usel variant to match last word's rule ({}), to reduce choppiness ".format(e.attrib["variant"]))
                        wordRule = mlrules_utils.serialize_element(e)

                    lastUselRule = e.attrib
                else:
                    lastUselRule = None
                
                # Check prosody playback speed, clamp very-fast/slow speeds
                if isProsodyTag:
                    e = mlrules_utils.deserialize_element(wordRule)
                    rateAttrib = e.attrib["rate"]
                    volAttrib = e.attrib["volume"]
                    logging.debug("    word={}, tag={}, rate={}, volume={}".format(w, mlrules_utils.clean_dict_key_str(mlparams.TAG_PROSODY), rateAttrib, volAttrib))

                    if rateAttrib == "x-slow":
                        e.attrib["rate"] = "slow"
                        wordRule = mlrules_utils.serialize_element(e)
                        logging.debug("        Rate is 'x-slow', clamping to 'slow'")

                    if volAttrib != "medium":
                        e.attrib["volume"] = "medium"
                        wordRule = mlrules_utils.serialize_element(e)
                        logging.debug("        Rate is '{}', clamping to 'slow'".format(volAttrib))

            tagRulesApplied.append(wordRule)
        rulesPerWordDict[tag] = tagRulesApplied
    
    if markVoiceSpecialMarkGenre:
        # Initialize dict for this tag if needed
        uselTag = mlrules_utils.clean_dict_key_str(mlparams.TAG_USEL)
        if not uselTag in rulesPerWordDict.keys():
            rulesPerWordDict[uselTag] = []
            for w in words:
                rulesPerWordDict[uselTag].append(None)

        i = 0
        while i < len(words):
            w = orig_words[i]
            foundQuestionMark = "?" in w
            foundExclamationMark = "!" in w
            if foundQuestionMark or foundExclamationMark:
                # Find the index range until a punctuation is found, that will be our subphrase
                j = i-1
                while j >= 0:
                    prevW = orig_words[j]
                    if any(p in prevW for p in [ ",", ".", "?", "!" ]):
                        break
                    j -= 1
                k = j+1
                # Set this range of word indices to have question genre
                while k <= i:
                    rulesPerWordDict[uselTag][k] = vocal_variant(genre = "question" if foundQuestionMark  else "motivational",
                                                                 specialMark = True)
                    k += 1
            i += 1

    return rulesPerWordDict
