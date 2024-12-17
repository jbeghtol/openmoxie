"""Assembles the list of tagged words into an ElementTree or XML string.

Sub-module to markup.py as the final step.
"""

import collections
import logging
import xml.etree.ElementTree as ET
from typing import List, Union, Tuple
import xml.dom.minidom

from .tagspan import TagSpan
from ..utils import bcolors
from .. import markup
from ..ml import mlparams
from ..ml import mlrules_utils
from .._version import __package_version__

def append_text(element, s, colorize=False):
    """Appends text to Element.text"""
    logging.debug("append_text({})".format(s))
    if element.text is None:
        element.text = ""
    space_char_if_need = ' ' if len(element.text) > 0 else ''

    # Commented out since this messes with pretty-xml parsing
    # if colorize:
    #     element.text = element.text.replace(markup.XML_OUTPUT_COLORIZE_COLOR, "").replace(bcolors.ENDC, "")
    #     element.text = "{}{}{}{}{}".format(markup.XML_OUTPUT_COLORIZE_COLOR, element.text, space_char_if_need, s, bcolors.ENDC)
    # else:
    element.text = "{}{}{}".format(element.text, space_char_if_need, s)


def append_tail(element, s, colorize=False):
    """Appends text to Element.tail"""
    logging.debug("append_tail({})".format(s))
    if element.tail is None:
        element.tail = ""

    # Commented out since this messes with pretty-xml parsing
    # if colorize:
    #     element.tail = element.tail.replace(markup.XML_OUTPUT_COLORIZE_COLOR, "").replace(bcolors.ENDC, "")
    #     element.tail = "{}{} {}{}".format(markup.XML_OUTPUT_COLORIZE_COLOR, element.tail, s, bcolors.ENDC)
    # else:
    element.tail = "{} {}".format(element.tail, s)


def is_word_tagged(tag_index: int, tags_for_insert_staging: List[TagSpan], word_index: int) -> Tuple[bool, int]:
    """Returns (bool) if-word_has_tag, (int) out_tag-index-in-tagsForInsertStagingList"""
    logging.debug("is_word_tagged(iTag={}, tagsForInsertStagingList={}, iWord={})".format(tag_index,
                                                                                          len(tags_for_insert_staging),
                                                                                          word_index))
    word_has_tag: bool = False
    out_tag: int = -1
    while tag_index < len(tags_for_insert_staging):
        span = tags_for_insert_staging[tag_index]
        logging.debug(f"    {span.associated_str}, span_index={bcolors.OKGREEN}[{span.start_index}, {span.end_index}]{bcolors.ENDC}, size={bcolors.OKGREEN}{span.size}{bcolors.ENDC}")
        word_has_tag = word_index >= span.start_index and word_index <= span.end_index
        if word_has_tag:
            out_tag = tag_index
            logging.debug("        {}BREAKING out? word_has_tag={}, out_tag={}{}".format(bcolors.FAIL, word_has_tag, out_tag, bcolors.ENDC))
            break
        tag_index += 1

    logging.debug("        {}Returning word_has_tag={}, out_tag={}{}".format(bcolors.WARNING, word_has_tag, out_tag, bcolors.ENDC))
    return word_has_tag, out_tag


def spans_to_tree(tags_for_insert_staging: List[TagSpan], words: List[str], debug_colors=False) -> ET.Element:
    """Processes TagSpan()s into XML tree"""
    xml_string = "<root></root>"
    root = ET.fromstring(xml_string)
    root.text = "<{} version=\"{}\"/>".format(markup.AUTO_GEN_ATTRIB_NAME, __package_version__)

    element_stack = collections.deque()
    tag_span_stack = collections.deque()
    element_stack.append(root)
    tag_span_stack.append(markup.TagSpan("root", 0, len(words)))

    word_index: int = 0
    current_tag: int = 0
    last_element_above_root: Union[ET.Element, None] = None
    word_had_a_tag = False
    inject_to_text_not_tail = False
    while word_index < len(words):
        word = words[word_index]
        logging.debug("{}({}){}, {}{}{}".format(bcolors.OKGREEN, word_index, bcolors.ENDC, bcolors.FAINT, word, bcolors.ENDC))

        # Check if last element is done; remove from deque if so
        iTagCheck = len(tag_span_stack) - 1
        while iTagCheck > 0: # > 0 since we are not getting rid or root node
            logging.debug("words[{}]={}, tag_span_stack[{}]=[{}, {}] {}({}){}".format(word_index, word, iTagCheck, tag_span_stack[iTagCheck].start_index, tag_span_stack[iTagCheck].end_index, bcolors.FAINT, tag_span_stack[iTagCheck].associated_str, bcolors.ENDC))
            if word_index > tag_span_stack[iTagCheck].end_index:
                logging.debug("    Popping")
                e = element_stack.pop()
                t = tag_span_stack.pop()
                inject_to_text_not_tail = False
                last_element_above_root = e # Store for "tail"ing
            logging.debug("    len(element_stack)={}".format(len(element_stack)))
            iTagCheck -= 1

        # Check word for tag scope
        word_has_tag, tag_index = is_word_tagged(current_tag, tags_for_insert_staging, word_index)
        if word_has_tag:
            current_tag = tag_index
        word_had_a_tag = word_has_tag  # Store this once

        iCheckMoreTags = current_tag
        while word_has_tag:
            # Add tree element as long as a tag is found at this word index
            span = tags_for_insert_staging[tag_index]
            if span.start_index == word_index:
                new_element = mlrules_utils.deserialize_element(span.associated_str)
                element_stack[-1].append(new_element)
                element_stack.append(new_element)
                tag_span_stack.append(span)

            iCheckMoreTags += 1 # Advance in the stack
            word_has_tag, tag_index = is_word_tagged(iCheckMoreTags, tags_for_insert_staging, word_index)
            if word_has_tag:
                current_tag = tag_index

        if current_tag > len(tags_for_insert_staging):
            logging.debug("{}current_tag/span={}{} ({})".format(bcolors.OKBLUE, current_tag, bcolors.ENDC, tags_for_insert_staging[current_tag].associated_str))
        # Add word to tag text or previous' tail
        if word_had_a_tag:
            last_e = element_stack[-1]
            if last_e.tag in mlparams.UNSCOPED_TAGS:
                append_tail(last_e, word, colorize=debug_colors)
            else:
                append_text(last_e, word, colorize=debug_colors)
        else:
            if last_element_above_root is None:
                append_text(root, word, colorize=debug_colors)
            else:
                append_tail(last_element_above_root, word, colorize=debug_colors)

        # Pretty tree view
        debug_xml = xml.dom.minidom.parseString(ET.tostring(root).decode("UTF-8"))
        logging.debug(f'{bcolors.FAIL}XML-TREE{bcolors.ENDC}:\n{debug_xml.toprettyxml(indent="---|")}')

        logging.debug("{}CURRENTLY{}: {}".format(bcolors.FAIL, bcolors.ENDC, ET.tostring(root).decode("UTF-8")))
        word_index += 1
    return root


def spans_to_xml(tags_for_insert_staging: List[TagSpan], words: List[str], debug_colors: bool = False):
    """Processes TagSpans into XML tree, and then returns an XML string"""
    root = spans_to_tree(tags_for_insert_staging, words, debug_colors=debug_colors)

    # Clean result string
    result = ET.tostring(root).decode("UTF-8")
    result = result.replace("<root>", "").replace("</root>", "")
    result = result.replace("&gt;", ">").replace("&lt;", "<")
    result = result.replace(" {}".format(mlparams.CHAR_EOL), "").replace(mlparams.CHAR_EOL, "")
    return result
