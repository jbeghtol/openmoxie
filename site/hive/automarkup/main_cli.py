"""
python3 and commandline access to auto-markup module.

Here you have options to use auto-markup as-is, retrain data module,
synthesize output .wav files, and debugging.

Please use embodied_chat_markup.py class for pythonic- and as-is integration.
"""

import argparse
import os
import sys
import time
import logging
import json
from typing import Dict, List

from . import markup
#sfrom . import synth
from .ml import mlassociation
from .ml import mlrules_utils
from .ml import mlparams

DEFAULT_INPUT_TEXT = "I need to store my conversations in different parts of my \"brain\" depending on how old the person I'm talking to is. If I don't my circuits might get scrambled."

def get_args():
    parser = argparse.ArgumentParser(description="Auto-markup! Pass in a string to get voice, behaviors, and mood markup. This module works with both python3 and python2, but output .wav files (and playback) are limited to python2 due to the Cereproc library. Note when generating output .wavs it assumes your voice and license files are in EmbodiedStaticData/, much like any Embodied workspace setup.")
    parser.add_argument("-m", "--mood", default="neutral"
                        , help="mood string. Use in conjunction with --mood_intensity. Default neutral")
    parser.add_argument("-mi", "--mood_intensity", type=float, default=0
                        , help="normalized intensity (0 to 1). Use in conjunction with --mood Default 0")
    parser.add_argument("-nr", "--no_rules", default=False, action="store_true"
                        , help="use no rules to markup (aka won't mark it up). Default False")
    parser.add_argument("-o", "--out_file", dest="out_file", metavar="out_file", type=str, default="output/out.wav", action="store"
                        , help="output file - default is the relative directory 'output/out.wav'")
    parser.add_argument("-p", "--pause", dest="pause", metavar="pause", type=float, default=None, action="store"
                        , help="pause - adds a pause/break in seconds between sentences. Default 0.0")
    parser.add_argument("-rt", "--retrain", default=False, action="store_true"
                        , help="retrain data model from CSV '{}', will take a while. Default False".format(mlparams.ML_DATA_PATH))
    parser.add_argument("-q", "--quiet", default=False, action="store_true"
                        , help="do not play generated markup (.wav will not generate), nor have nicely formatted final output. Default False")
    parser.add_argument("-v", "--verbose", default=False, action="store_true"
                        , help="verbose debugging output. Default False")
    parser.add_argument("-s", "--strip", default=False, action="store_true"
                        , help="strip markup")
    parser.add_argument("-b", "--batch", default=False, action="store_true", help="inputText is path to batch of NLP JSON file to automarkup")
    parser.add_argument("--version", default=False, action="store_true"
                        , help="print version number")
    parser.add_argument("inputText", default="", help="Text to auto-markup")
    args = parser.parse_args()
    return args

def run_markup(inputText, out_file, no_rules, rules, mood, mood_intensity, pause, quiet, verbose):
    # Markup line
    startTime = time.time()
    if no_rules:
        outMarkup = inputText.replace("\\!", "!")
        print(outMarkup)
    else:
        text_replacements: Dict[str, str] = markup.get_internal_text_replacements()
        outMarkup = markup.markup(inputText,
                                  rules,
                                  markVoice=True,
                                  markVoiceSpecialMarkGenre=True,
                                  markBehaviors=True,
                                  markMoodAndIntensity=(mood, mood_intensity),
                                  markup_pauses=pause,
                                  prettyPrint=not quiet,
                                  text_replacements=text_replacements,
                                  debug=verbose)
    markupTime = time.time() - startTime

    # Printing
    if quiet:
        print(outMarkup)  # Otherwise markup.py has nice output
    # Audio playback
    else:
        outPath = out_file
        if outPath is not None and len(outPath) > 0 and outPath[0] != "/":
            outPath = os.path.join(os.path.dirname(__file__), "..", outPath)
        # if not quiet:
        #     synth.main(outMarkup, outPath, quiet=quiet)

    return markupTime

def main():
    args = get_args()
    inputText = DEFAULT_INPUT_TEXT
    if args.inputText != "":
        inputText = args.inputText

    mood = args.mood
    mood_intensity = args.mood_intensity
    no_rules = args.no_rules
    out_file = args.out_file
    retrain = args.retrain
    quiet = args.quiet
    verbose = args.verbose
    pause = args.pause
    batch = args.batch

    if args.version:
        print(markup.__version__)
        sys.exit(0)
    elif args.strip:
        print(markup.strip(inputText))
        sys.exit(0)

    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    # Generate/load rules
    startTime = time.time()
    rules: Dict[str, Dict[str, List[mlassociation.Rule]]] = {}
    if not no_rules:
        MODE_IS_LOAD = not retrain
        if MODE_IS_LOAD:
            rules = mlrules_utils.load_rules()
        else:
            import mlrules
            rules = mlrules.generate_rules()
    processTime = time.time() - startTime

    # Generate markup
    #   batch mode
    if batch:
        for root, dirs, files in os.walk(inputText, topdown=False):
            for name in files:
                if name.lower().endswith(".json"):
                    with open(os.path.join(root, name), 'r') as f:
                        try:
                            data = json.load(f)
                            markupTime = run_markup(data[mlparams.NLP_JSON_UTTERANCE], out_file, no_rules, rules, mood, mood_intensity, data, pause, quiet, verbose)
                            if not quiet:
                                logging.info("Process took {:.5}s, markup took {:.5}ms".format(processTime, markupTime/1000))
                        except:
                            if not quiet: print("Failed to convert markup in file '{}'".format(os.path.join(root, name)))
    #   one off
    else:
        markupTime = run_markup(inputText, out_file, no_rules, rules, mood, mood_intensity, pause, quiet, verbose)
        if not quiet:
            logging.info("Process took {:.5}s, markup took {:.5}ms".format(processTime, markupTime/1000))
