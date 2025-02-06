'''
REMOTE GLOBAL COMMANDS - Handles global commands for OpenMoxie

Global commands are regular expression patterns that are checked on input speech
and bound to either responses, responses w/ actions, or responses that are generated from
custom methods.

Global commands are GLOBAL, so if you make a global command that hadles .*, it will usurp
ALL inputs and make your bot non-functional.  It is best to make patterns as NARROW as
possible to avoid triggering them when you don't intend to.  Matching uses searching,
but can be constrained to whole sentence matching using ^moxie time$ for instance to 
catch "moxie time" but ignore "moxie time is something i dont have"
'''
from concurrent.futures import ThreadPoolExecutor,TimeoutError
from ..models import GlobalResponse, GlobalAction
import re
import logging
from .rchat import make_response,add_response_action
from functools import partial
import traceback

logger = logging.getLogger(__name__)

# Action Patterns - these produce a single response, with or without an attached action
class ActionPattern:
    _re : re.Pattern
    _source: GlobalResponse
    def __init__(self, source, action=None):
        self._source = source
        self._re = re.compile(source.pattern)
        self._action = action

    def response_functor(self, speech, rcr):
        matches = self._re.match(speech)
        if matches:
            return partial(self.create_response, matches, rcr)
        return None
    
    def create_response(self, matches, rcr):
        resp = make_response(rcr, output_type='GLOBAL_COMMAND')
        resp['output']['text'] = self._source.response_text
        resp['output']['markup'] = self._source.response_markup
        if self._action:
            add_response_action(resp, self._action, output_type='GLOBAL_COMMAND', module_id=self._source.module_id, content_id=self._source.content_id)
        return resp

# Action Patterns - these produce a single response generated on the fly from a custom method
class MethodPattern(ActionPattern):
    _re : re.Pattern
    def __init__(self, source):
        super().__init__(source)
        self._entity_groups = [int(x) for x in source.entity_groups.split(',') if x] if source.entity_groups else None

    def create_response(self, matches, rcr):
        resp = make_response(rcr)
        loc = locals()
        try:
            exec(self._source.code, globals(), loc)
            func = loc.get('get_response')
            if func:
                # get_response(request, response, entities)
                entities = [matches.group(x) for x in self._entity_groups] if self._entity_groups else None
                # run background, limited at 10s
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(func, rcr, resp, entities)
                    result = future.result(timeout=10.0)
                if isinstance(result, str):
                    # if string, overwrite text in canned response
                    resp['output']['text'] = result
                else:
                    # other option, full response is the result - return it as is
                    return result
            else:
                resp['output']['text'] = "Script error: Could not locate method get_response"
        except TimeoutError:
            logger.error("Method code exceeded time limit.")
            resp['output']['text'] = f"Script error: Timeout exceeded"
        except Exception as e:
            exc_info = traceback.format_exc()
            logger.error(exc_info)
            resp['output']['text'] = f"Script error: {e}"

        return resp

# The object owning ALL active Global Responses.  It loads them from the database only on
# startup and request.  All response handling must be executed in the returned functor.
class GlobalResponses:
    _patterns: list[ActionPattern]

    def __init__(self):
        self._patterns = []

    def update_from_database(self):
        self._patterns = []
        for gr in GlobalResponse.objects.all().order_by('-sort_key'):
            if gr.action == GlobalAction.LAUNCH.value:
                logger.info(f'Loading GlobalResponse LAUNCH type {gr}')                
                self._patterns.append(ActionPattern(gr, action="launch"))
            elif gr.action == GlobalAction.CONFIRM_LAUNCH.value:
                logger.info(f'Loading GlobalResponse CONFIRM_LAUNCH type {gr}')                
                self._patterns.append(ActionPattern(gr, action="launch_if_confirmed"))
            elif gr.action == GlobalAction.RESPONSE.value:
                logger.info(f'Loading GlobalResponse RESPONSE type {gr}')
                self._patterns.append(ActionPattern(gr))
            elif gr.action == GlobalAction.METHOD.value:
                logger.info(f'Loading GlobalResponse CUSTOM METHOD type {gr}')
                self._patterns.append(MethodPattern(gr))
            else:
                logger.warning(f"Unsupported type {gr.action} in GlobalResponse {gr.name}")

    def check_global(self, rcr):
        speech = rcr.get('speech')
        if speech:
            # all global commands match at lowercase
            speech = speech.lower()
            for p in self._patterns:
                f = p.response_functor(speech, rcr)
                if f:
                    return f
        return None