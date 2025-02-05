# Global Responses

Remote global responses are "global scope" patterns that can handle inputs in any Moxie
context.  They are the means by which you could add a new global entry pattern like
"Moxie tell me the time".

*WARNING* Global scope can interrupt a lot of great interactions, so any global responses
should have narrow patterns to match inputs so they don't disrupt conversations.  Take care
here, as it is a very easy way to break free form chat.

## Action Types

Global responses can be in one of these action types:

* RESPONSE - Moxie will say this response
* LAUNCH - Moxie will say this respopnse, and launch into a different module
* CONFIRM_LAUNCH - Moxie will ask if you want to switch activities, and if user confirms launch a diff module (response isn't played but needs exist)
* METHOD - The most complex, Moxie's response will be produced by a custom python method provided

## METHOD type

By far the most powerful and scary, this method allows you to store a custom python method to produce the response.  The
method must use the following signature, and no global level imports are allowed.

```
# request - the full remote chat request from the robot
# response - the response object, you should return it filled out OR a simple string with response text
# entities - any groups extracted from the regex input
def get_response(request, response, entities):
    resp = { "what": "Chicken Butt", "why": "Chicken Thigh", "how": "Chicken Cow" }    
    return resp.get(entities[0], "Error")
```

The above example is a simple method to pair with a simple regex: `^moxie (what|why|how)$`.  It has a group for the adverb, which is the first and only group.

### How this regex works

1. User says "moxie what" or "moxie why" or "moxie how", which are all valid.  The regex groups these options inside () which makes them a "group".  It is the first group, so we set `entity_groups=1` in the setup.
2. The regex matches, and the METHOD is queued to run.  Because we asked to extract groups, the method is passed `entities=['why']` if we say `why`.
3. The method then looks up a fun response based on the adverb, and returns it as a string
4. This string is then marked-up and played as the response for the input

### Another Example, ask Moxie the time

* pattern = `^moxie (time|what(?:'s| is) the time|what time is it)$`
* action = `METHOD`
* code = (see below)

```
def get_response(request, response, entities):
    def get_current_time():
        from datetime import datetime
        now = datetime.now()
        current_time = now.strftime("The time is %I %M %p")
        return current_time
    return get_current_time()
```

Note: You can use import from within the method scope.  Any exceptions in processing this will produce a response
with an error and the name of the exception.

## OMG How does one make a regex anyway?

If you aren't familiar with them, do some googling.  But, AIs are often pretty good if you describe what you want.  I used
this prompt to generate the time regex above:

```
i want to write a regular expression to catch phrases like "moxie time" "moxie what's the time" and "moxie what time is it" and i want only whole phrases, not substrings, accepted
```