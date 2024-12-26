from openai import OpenAI
import logging

logger = logging.getLogger(__name__)

_OPENAPI_KEY=None

def set_openai_key(key):
    global _OPENAPI_KEY
    _OPENAPI_KEY = key

def create_openai():
    global _OPENAPI_KEY
    return OpenAI(api_key=_OPENAPI_KEY)
