"""Generates data model from input CSV and writes out a JSON to store."""

import json
import logging
import re
import random
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple, Union

from apyori import apriori
from pandas import read_csv

from ..utils import bcolors
from . import mlassociation
from . import mlparams
from . import mlrules_utils


def generate_rules() -> Dict[str, Dict[str, List[mlassociation.Rule]]]:
    rules = generate()
    f = open(mlparams.ML_DATA_PATH, "w")
    f.write(json.dumps(rules, indent=4, cls=mlassociation.RuleEncoder))
    f.close()
    return rules


def check_and_clean_text(element) -> Union[str, None]:
    """Removes special characters and reduces double-/n-spaces to single"""
    c_text: Union[str, None] = None
    has_tail_only = (element.text is None and element.tail is not None)
    if element.text is not None or has_tail_only:
        xml = element.text
        if has_tail_only:
            xml = element.tail

        c_text = re.sub(r'['+mlparams.SPECIAL_CHARS+']', ' ', xml)
        while "  " in c_text:  # Remove n-number of spaces
            c_text = c_text.replace("  ", " ")
        while '""' in c_text:  # Remove n-number of "
            c_text = c_text.replace('""', " ")
        if len(c_text) > 0 and c_text[0] == " ":  # Remove leading space
            c_text = c_text[1:]
    
    return c_text


def rand_string() -> str:
    """str(random.randint(-1000000, 1000000))"""
    return str(random.randint(-1000000, 1000000))


def append_data_to_list(result_list: List[Tuple[str, str]], element, word) -> List[Tuple[str, str]]:
    if word not in mlparams.IGNORE_WORDS_LIST and len(word) > mlparams.IGNORE_WORD_IF_SHORTER_THAN:
        result_list.append((element, word))
    return result_list


def xml_to_data_list(xml: str) -> List[Tuple[str, str]]:
    """
    Converts and returns XML string into a flat list of element-word pairs. For example:

    [<Element 'mark' at 0x12485c048>, 'Get']
    [<Element 'break' at 0x12485c278>, 'Get']
    [<Element 'mark' at 0x12485c318>, 'Get']
    [<Element 'lex' at 0x12485c138>, 'draw']
    [<Element 'usel' at 0x12485c228>, 'on']
    [<Element 'mark' at 0x12485c4a8>, 'your']
    [<Element 'mark' at 0x12485c4f8>, 'your']
    [<Element 'phoneme' at 0x12485c598>, 'draw']
    [<Element 'usel' at 0x12485c5e8>, 'with']
    [<Element 'mark' at 0x12485c638>, 'When']
    [<Element 'mark' at 0x12485c6d8>, 'say']
    [<Element 'usel' at 0x12485c728>, 'Moxie']
    [<Element 'mark' at 0x12485c778>, '__EOL__']
    [<Element 'mark' at 0x12485c7c8>, '__EOL__']
    [<Element 'mark' at 0x12485c818>, '__EOL__']
    """
    # Give it a root node, for that will make xml.etree happy
    xml = "<root>{} {}</root>".format(xml, mlparams.CHAR_EOL)
    logging.debug(len(xml))

    # Inspection
    logging.debug("{}{}{}".format(bcolors.OKGREEN, xml, bcolors.ENDC))
    root = None
    try:
        root = ET.fromstring(xml)
    except Exception as e:
        logging.debug(f"Ignored exception: {e}\n{xml}")
        return []

    result_list: List[Tuple[str, str]] = []

    for child in root.iter():
        logging.debug(str(child.tag) +
                      "'{}{}{}'".format(bcolors.OKGREEN if child.text is not None else bcolors.FAINT,
                                        child.text, bcolors.ENDC) +
                      "'{}{}{}'".format(bcolors.OKGREEN,
                                        child.tail if child.tail is not None else bcolors.FAINT, bcolors.ENDC))

        has_tail_only = (child.text is None and child.tail is not None)
        if child.text is not None or has_tail_only:
            c_text = check_and_clean_text(child)

            # For every word, add corresponding element for scoped markup
            words = c_text.split(" ")
            if has_tail_only:  # Un-scoped
                if len(words) > 0 and words[0] != mlparams.CHAR_EOL:
                    result_list = append_data_to_list(result_list, mlrules_utils.serialize_element(child), words[0])
            else:  # Scoped
                for w in words:
                    if len(w) > 0 and w != mlparams.CHAR_EOL:
                        result_list = append_data_to_list(result_list, mlrules_utils.serialize_element(child), w)

        elif child.text is None and child.tail is None:
            # These are usually un-scoped markup; Seek forward to find next element with text.
            found_self = False
            for child2 in root:
                if child2 == child:
                    found_self = True
                    pass
                elif not found_self:
                    pass

                if found_self:
                    if child2.text is not None or child2.tail is not None:
                        c_text = check_and_clean_text(child2)
                        words = c_text.split(" ")
                        if len(words) > 0 and words[0] != mlparams.CHAR_EOL:
                            result_list = append_data_to_list(result_list,
                                                              mlrules_utils.serialize_element(child),
                                                              words[0])
                        break

    for result in result_list:
        logging.debug(result)

    return result_list


def serialize_rules_to_dict(association_results) -> Dict[str, List[mlassociation.Rule]]:
    """
    Each word will have a list of rules. Return formats as follows:

    {
        "word": 
        [   # List of rules
            mlassociation.Rule(),
            mlassociation.Rule(),
            ...
        ]
        "another":
        [
            ...
        ]
    }
    """
    rules_dict: Dict[str, List[mlassociation.Rule]] = {}
    for item in association_results:
        # first index of the inner list
        # Contains base item and add item
        pair = item[0] 
        support = item[1]
        confidence = item[2][0][2]
        lift = item[2][0][3]

        items = [x for x in pair]
        word = items[0]
        markup = items[1]
        if items[0].startswith("{\""):
            word = items[1]
            markup = items[0]
        word = word.lower()

        logging.debug("Rule: {}{}{} -> {}{}{}".format(bcolors.OKBLUE, word, bcolors.ENDC,
                                                      bcolors.OKGREEN, markup, bcolors.ENDC))

        # second index of the inner list
        msg_s = "Support: {:.8f}".format(support)

        # third index of the list located at 0th of the third index of the inner list
        msg_c = "Confidence: {:.3f}%".format(confidence*100)
        msg_l = "Lift: {:.3f}".format(lift)
        logging.debug("{:25}{:25}{:25}\n".format(msg_s, msg_c, msg_l))

        if word not in rules_dict.keys():
            rules_dict[word] = []
        rules_dict[word].append(mlassociation.Rule(markup, support, confidence, lift))
    
    return rules_dict


def generate() -> Dict[str, Dict[str, List[mlassociation.Rule]]]:
    csv_data = read_csv(mlparams.CSV_PATH)

    # Collect data pairs from marked up CSVs. Expects format:
    # UUID,Output
    # AnyValue,"<node>Hello</node> World!"
    # ...
    data_sets_dict: Dict[str, List[Tuple[str, str]]] = {}
    for rowIndex in range(1, csv_data.shape[0]):
        xml_string = csv_data.loc[rowIndex, "Output"]
        data_list = xml_to_data_list(xml_string)
        found_tag = False
        for d in data_list:
            e_name = d[0]
            for tag in mlparams.TAGS:
                if tag not in data_sets_dict.keys():
                    data_sets_dict[tag] = []

                if e_name.startswith(tag):
                    data_sets_dict[tag].append(d)
                    found_tag = True
                elif not mlparams.RESTRICT_TO_DISTINCT_TAG:
                    # Add a non-value here for more accurate association-support
                    data_sets_dict[tag].append((rand_string(), d[1]))

            if not found_tag and mlparams.SHOW_MISSED_TAGS:
                logging.info("{}{}{}".format(bcolors.FAIL, d, bcolors.ENDC))

    # Run algorithm
    msg = ""
    total_count = 0
    total_r_count = 0
    output_dict: Dict[str, Dict[str, List[mlassociation.Rule]]] = {}
    for k in data_sets_dict.keys():
        if k == mlparams.TAG_ROOT:  # Ignore <root>
            continue

        logging.info("\n{}{:10}{}{}".format(bcolors.WARNING,
                                            mlrules_utils.clean_dict_key_str(k),
                                            "".rjust(40, '='),
                                            bcolors.ENDC))
        params_dict = mlparams.APRIORI_VALUES[k]
        association_rules = apriori(data_sets_dict[k],
                                    min_support=params_dict["min_support"],
                                    min_confidence=params_dict["min_confidence"],
                                    min_lift=params_dict["min_lift"],
                                    min_length=params_dict["min_length"])
        association_results = list(association_rules)

        # Output dict
        output_dict[mlrules_utils.clean_dict_key_str(k)] = serialize_rules_to_dict(association_results)

        # Pretty printing
        values_count = len(data_sets_dict[k])
        r_count = len(association_results)
        msg += "'{}' ({}, {}{}{} rules), ".format(mlrules_utils.clean_dict_key_str(k),
                                                  values_count,
                                                  bcolors.OKGREEN, r_count, bcolors.ENDC)
        total_count += values_count
        total_r_count += r_count

    logging.info("Processed data: {}\nTotal data entries: {}, {} rules.".format(msg, total_count, total_r_count))
    return output_dict
