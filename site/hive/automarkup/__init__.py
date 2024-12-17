from typing import Tuple
from typing import Dict

from .ml import mlrules_utils
from . import markup
from . import main_cli
from ._version import __version__


def main():
    return main_cli.main()


def initialize_rules():
    return mlrules_utils.load_rules()


def process(input_string, rules, mood_and_intensity: Tuple[str, float] = None, settings: Dict = None):
    """
    Markup an unmarked string. Returns marked up string.

    input_string (str) - base string to pass in
    mood_and_intensity (tuple) - two-length tuple for (str, float) to specify mood and normalized intensity
    """
    text_replacements = markup.get_internal_text_replacements()

    if settings and settings["props"]:
        props = settings["props"]
        print(f"Passed in a dictionary with {len(props)} settings.")

    result = markup.markup(input_string,
                           rules=rules,
                           markVoice=True,
                           markBehaviors=True,
                           markMoodAndIntensity=mood_and_intensity,
                           prettyPrint=False,
                           text_replacements=text_replacements,
                           debug=False)
    return result


def remove_quotes(input_string: str):
    return markup.remove_quotes(input_string)

