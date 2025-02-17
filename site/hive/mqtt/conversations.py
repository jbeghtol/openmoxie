'''
CONVERSATIONS - Framework for Moxie remote applications / conversations
'''
import logging
import copy
import random
import re
from django.template import Template, Context
from .ai_factory import create_openai
from ..models import SinglePromptChat
from .volley import Volley

logger = logging.getLogger(__name__)

'''
Base type of a module that has a chat session interaction on Moxie.  It
manages the history, rotating out records to keep tokens more lean.
'''
class ChatSession:
    def __init__(self, max_history=20):
        self._history = []
        self._max_history = max_history
        self._total_volleys = 0
        self._local_data = {}

    def add_history(self, role, message, history=None):
        if not history:
            history = self._history
            self._total_volleys += 1
        if history and history[-1].get("role") == role:
            # same role, append text
            history[-1]["content"] =  history[-1].get("content", '') + ' ' + message
        else:
            history.append({ "role": role, "content": message })
            if len(history) > self._max_history:
                history = history[-self._max_history:]

    def is_empty(self):
        return len(self._history) == 0
    
    def reset(self):
        self._history = []
        
    @property
    def local_data(self):
        return self._local_data
    
    def get_opener(self, msg='Welcome to open chat'):
        self.reset()
        return msg,self.overflow()

    def ingest_notify(self, rcr):
        # RULES - speech field is what 'assistant' said, but we should skip the [animation]
        # 'user' speech comes from extra_lines[].text when .context_type=='input'
        for line in rcr.get('extra_lines', []):
            if line['context_type'] == 'input':
                self.add_history('user', line['text'])
        speech = rcr.get('speech')
        if speech and 'animation:' not in speech:
            self.add_history('assistant', speech)

    def next_response(self, speech, context):
        logger.debug(f'Inference using history:\n{self._history}')
        return f"chat history {len(self._history)}", None

    def overflow(self):
        return False
    
    def handle_volley(self, volley:Volley):
        pass

'''
Our simple Single Prompt conversation.  It uses the ChatSession to manage the history
of the conversation and focuses on keeping the conversation within volley limits and
make inferences to OpenAI.
'''
class SingleContextChatSession(ChatSession):
    def __init__(self, 
                 max_history=20, 
                 max_volleys=9999,
                 prompt="You are a having a conversation with your friend. Make it interesting and keep the conversation moving forward. Your utterances are around 30-40 words long. Ask only one question per response and ask it at the end of your response.",
                 opener="Hi there!  Welcome to Open Moxie chat!",
                 model="gpt-3.5-turbo",
                 max_tokens=70,
                 temperature=0.5,
                 exit_line="Well, that was fun.  Let's move on."
                 ):
        super().__init__(max_history)
        self._max_volleys = max_volleys        
        self._context = [ { "role": "system", 
            "content": prompt
            } ]
        self._opener = opener
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._exit_line = exit_line
        self._auto_history = False
        self._exit_requested = False
        self._pre_filter = None
        self._post_filter = None
        self._prompt_template = Template(prompt)

    def set_filters(self, pre_filter=None, post_filter=None):
        self._pre_filter = pre_filter
        self._post_filter = post_filter

    # For web-based, we have no Moxie and no Notify channel, so auto-history is used
    def set_auto_history(self, val):
        self._auto_history = val
    
    # Check if we exceed max volleys for a conversation
    def overflow(self):
        return self._total_volleys >= self._max_volleys or self._exit_requested
    
    # Render an updated prompt context for this volley
    def make_volley_context(self, volley:Volley):
        return [ { "role": "system", 
                    "content": self._prompt_template.render(Context({'volley': volley}))
                    } ]
    
    # Handle a volley, using its request and populating the response
    def handle_volley(self, volley:Volley):
        volley.assign_local_data(self._local_data)
        try:
            # preprocess, if filter returns True, we are done
            if self._pre_filter:
                logger.debug("Running volley pre-filter")
                if self._pre_filter(volley, self):
                    return
            
            # Handle prompt vs next response
            cmd = volley.request.get('command')
            if cmd == "prompt" or (cmd == "reprompt" and self.is_empty()):
                text,overflow = self.get_opener()
            else:
                speech = "hm" if volley.request.get("command")=="reprompt" else volley.request["speech"]
                text,overflow = self.next_response(speech, self.make_volley_context(volley))
            volley.set_output(text, None)
            if overflow:
                volley.add_launch_or_exit()
            # postprocess the volley
            if self._post_filter:
                logger.debug("Running volley post-filter")
                self._post_filter(volley, self)
        except Exception as e:
            #stack = traceback.format_exc()
            err_text = f"Error handling volley: {e}"
            logger.error(err_text)
            volley.create_response() # flush any pre-exception response changes
            volley.set_output(err_text,err_text)

    # Get the next thing we should say, given the user speech and the history
    def next_response(self, speech, context):
        of = self.overflow()
        if self._auto_history:
            # accumulating automatically, no interruptions or aborts
            self.add_history('user', speech)
            history = self._history
        else:
            # clone, add new input, official history comes from notify
            history = copy.deepcopy(self._history)
            self.add_history('user', speech, history)
        try:
            client = create_openai()
            resp = client.chat.completions.create(
                        model=self._model,
                        messages=context + history,
                        max_tokens=self._max_tokens,
                        temperature=self._temperature
                    ).choices[0].message.content
            # detect <exit> request from AI
            self._exit_requested = self._exit_requested or '<exit>' in resp
            if self._exit_requested:
                logger.info("Exit tag detected in response.")
                of = True
            # remove any random xml like tags
            resp = re.sub(r'<.*?>', '', resp)
        except Exception as e:
            logger.warning(f'Exception attempting inference: {e}')
            resp = "Oh no.  I have run into a bug"
        if of:
            resp += " " + self._exit_line
        if self._auto_history:
            self.add_history('assistant', resp)
        return resp, of
    
    # Prompt in this case is an opener line to say when we start the conversation module
    def get_opener(self):
        # Supports multiple random prompts separated by |, pick a random one
        opener = random.choice(self._opener.split('|'))
        resp,overflow = super().get_opener(msg=opener)
        if self._auto_history:
            self.add_history('assistant', resp)
        return resp,overflow

# A database backed version, the way we normally load them
class SinglePromptDBChatSession(SingleContextChatSession):
    def __init__(self, pk):
        source = SinglePromptChat.objects.get(pk=pk)
        super().__init__(max_history=source.max_history, max_volleys=source.max_volleys, model=source.model, prompt=source.prompt, opener=source.opener, max_tokens=source.max_tokens, temperature=source.temperature)
        if source.code:
            try:
                loc = locals()
                exec(source.code, globals(), loc)
                self.set_filters(pre_filter=loc.get('pre_process'), post_filter=loc.get('post_process'))
            except Exception as e:
                logger.error(f"Error loading code for chat session: {e}")