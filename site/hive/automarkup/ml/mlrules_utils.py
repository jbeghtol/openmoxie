"""Utility class to mlrules.py for data serialization."""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from typing import Dict, List

from . import mlassociation
from . import mlparams


def load_rules() -> Dict[str, Dict[str, List[mlassociation.Rule]]]:
    data_path = mlparams.ML_DATA_PATH
    if not os.path.exists(mlparams.ML_DATA_PATH):
        data_path = mlparams.ML_DATA_EXE_PATH

    f = open(data_path, "r")
    rules = json.loads(f.read())
    f.close()

    for key in rules.keys():
        for ikey in rules[key].keys():
            json_list = rules[key][ikey]
            rules[key][ikey] = []
            for j in json_list:
                rules[key][ikey].append(mlassociation.Rule(**j))
    return rules


def serialize_element(element: ET.Element) -> str:
    """
    Serializes a TreeElement and returns json-string
    """
    data_dict = {}
    if mlparams.IGNORE_MARKUP_ATTRIB:
        data_dict[element.tag] = {}
    else:
        data_dict[element.tag] = element.attrib
    return json.dumps(data_dict)


def deserialize_element(s: str) -> ET.Element:
    """
    Returns an xml tree Element. Expects exactly one key and one value.
    ie: {"usel": {"variant": "1", "genre": "none"}}
    """
    d_dict = json.loads(s)
    tag = None
    counter = 0
    for k in d_dict.keys():
        tag = k
        counter += 1
    
    if counter != 1:
        print("WRONG NUMBER OF KEYS; cannot deserialize")
        sys.exit(1)

    # Clean any aliased tags
    checked_tag = tag
    if tag in mlparams.ALIAS_TAGS:
        checked_tag = mlparams.aliastotag(tag)

    e = ET.Element(checked_tag)
    e.attrib = d_dict[tag]

    return e


def clean_dict_key_str(key: str) -> str:
    """Formats key names from '{ root, ' to 'root'"""
    return re.sub(r'['+mlparams.SPECIAL_CHARS+' ]', '', key)
