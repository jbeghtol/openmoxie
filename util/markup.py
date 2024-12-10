import re

def strip_markup(markup, trim_leading=True, replacement=""):
    stripped = re.sub("<[^<]*>", replacement, markup)
    return stripped.lstrip() if trim_leading else stripped

def extract_text_note(match_obj):
    print(match_obj)
    if match_obj.group(1) is not None:
        return " " + match_obj.group(1) + " "

def extract_key_note(match_obj):
    return " [" + match_obj.group(1) + ":" + match_obj.group(2) + "] "

def expand_notes(markup):
    first_pass = re.sub("<note\\s+text\\s*=\\s*\"([^\"]*)\"[^>]*>", extract_text_note, markup)
    second_pass = re.sub("<note\\s+([a-zA-Z0-9_\\-]+)\\s*=\\s*\"([^\"]*)\"[^>]*>", extract_key_note, first_pass)
    return second_pass

def alt_text(markup):
    # remove markup
    no_markup = strip_markup(expand_notes(markup), trim_leading=False, replacement=" ")
    # remove uuids, weird quotes spaces and random .
    user_sanitized_input = re.sub("(u[0-9a-fA-F]{32})|(\" \")|( \\.)", "", no_markup)
    # remote any blocks of spaces
    final_text = re.sub("  +", " ", user_sanitized_input)
    return final_text.strip()


if __name__ == "__main__":
    sample_markup = 'Justin<note text=" Beghtol"/><note animation="birding"/><mark name="cmd:playaudio,data:{+SoundToPlay+:+Sfx_CorrectResponse01+,+LoopSound+:false,+playInBackground+:false,+channel+:1,+ReplaceCurrentSound+:false,+PlayImmediate+:true,+ForceQueue+:false,+Volume+:1.0,+FadeInTime+:0.0,+FadeOutTime+:0.0,+AudioTimelineField+:+none+}"/><break time="1s"/>'
    print(alt_text(sample_markup))