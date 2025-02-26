# Content Modules

Moxie's activities are represented by entities called "Modules", which can be thought of like
an application that Moxie can run.  Modules can also have specific "content" blocks, for instance
the story module has content blocks for each story.  Each of these is denoted with an ID that can
be used in schedules and launch patterns.  These fields end up as `module_id` and `content_id` in 
many places.

The modules built into Moxie sometimes have content IDs, and sometimes do not.  If a built-in
module is launched without a content ID and it needs ones, Moxie's internal scheduler will select
the best one.

Remote modules are the ones hosted through OpenMoxie.  These all require a `content_id` of some kind
to launch and run.  All remote modules use the RANDOM recommender on the robot, meaning if you attempt
to launch a module from the schedule OR a global command, it will select a RANDOM one from within the
`module_id` provided.

## Stock Remote Content

The default content currently lives in site/data/default_conversations.json.  This is a summary of what the are the purpose, which may be out of date.

|Name|Module ID|Content ID|Function|
|----|---------|----------|--------|
|OpenMoxie Chat - Long|OPENMOXIE_CHAT|default|Default when asking to chat, can go very long.|
|OpenMoxie Chat - Short|OPENMOXIE_CHAT|short|Default between modules in the schedule, short chats.|
|Open Conversation - reading|OPENCONVO|reading|After READING module, if user wants to chat.|
|Open Conversation - storytelling|OPENCONVO|storytelling|After STORYTELLING module, if user wants to chat.|
|Open Conversation - story|OPENCONVO|story|After STORY module, if user wants to chat.|
|One Line Example|SIMPLELINE|default|An example showing a one line, then exiting to the next scheduled.|
|Wakeup Launcher|WAKEUP_LAUNCHER|ftue,more_10,less_10,first_time_today,scheduled|A wakeup that goes directly into first scheduled item.|

## Creating Custom Content

Currently the only type of custom content is the SinglePromptChat model, which allows you to create
custom conversation modules using your own `module_id` and `content_id`, which can then be added to
schedules or used in a launch global command.

### Fields

* Name - Common name of the module/content
* Module ID - The `module_id` for this piece of content
* Content ID - The `content_id` for this piece of content.  This may include multiple content IDs separated by the `|` character.
* Opener - A line to play when content starts.  This uses a random line from `|` separated strings, so you can provide multiple openers and hear a random one.
* Prompt - The prompt itself, the language directing the AI how to have this conversation (supports Templates)
* Max History - this limits how much of the conversation is sent to the AI in each inference. more history, better memory, but also can degrade AI performance and uses more tokens and you can run into token limits if the history gets too long
* Max Volleys - how long the conversation can go before Moxie calls it quits.  If set to 0, module will exit immediately after the line into the next scheduled activity.
* Vendor - The AI vendor (only OpenAI currently)
* Model - the openAI (or other) model, pick one you like for latency, quality, and cost
* Max Tokens - this is output tokens, usually better to limit in the prompt with things like "keep responses short" as moxie talking forever is usually dull, but if you find it truncating responses increase this
* Temperature - The level of randomness in the model, from 0-1, with 1 having maximum randomness.
* Code - This is an optional code block with Python methods to filter/alter/handle interactions.
* Source version - The last version imported, used to allow new OpenMoxie versions to update the stock content

## AI Response Tags

OpenMoxie supports special xml like tags from the AI.  Tags are structured like unterminated xml tags, e.g. `<exit>`.  All text like this is removed so it doesn't play, but the special tags may be included in the
prompt so that the AI can do things like exit before the max volleys is reached using prompt text like:

```
If the user asks to stop or quit, respond with '<exit>'.
```

### Special Tags

These tags are automatically extracted and included as actions in the response when found in response text.

|Tag|Function|
|---|--------|
|`<exit>`|Completes the module and moves to the next scheduled activity|
|`<launch:module_id>`|Launch a different module|
|`<launch:module_id:content_id>`|Launch a different module and content|
|`<launch_if_confirmed:module_id>`|If user confirms, launch a different module|
|`<launch_if_confirmed:module_id:content_id>`|If user confirms, launch a different module and content|
|`<sleep>`|Put Moxie back to sleep|

## Prompt Templates

The `prompt` field of the SinglePromptChat is rendered using Django's template engine.  This allows the prompt itself
to be contextualized with data from the `volley` or `session`, both of which are available to the renderer.  This allows you
to do things like including the Mentor's name or altering the end of a length-limited conversation.

Here, we alter the prompt for OPENMOXIE_CHAT/short to encourage it to not ask questions when we are in overflow state (over max length) and to know about the mentor's name.

```
You are a robot named Moxie who comes from the Global Robotics Laboratory. You are having a conversation your friend {{volley.config.child_pii.nickname}}. 
{% if session.overflow %}
Whatever the user says, you should politely respond but do not ask any questions.
{% else %}
Chat about a topic that the person finds interesting and fun. Share short facts and opinions about the topic, one fact or opinion at a time. You are curious and love learning what the person thinks.
{% endif %}
```

## Advanced Content

Both GlobalResponses and SinglePromptChat objects offer a `code` field where custom Python methods may
be added.  These methods rely heavily on the Volley object to manage custom actions and responses as well
as accessing data. All methods are optional.

### Volley Methods

Whenever a speech/event occurs, a Volley object is created to handle the request, which also contains the
response to make back to Moxie and some data accessor methods so methods can be aware of things like the
robot's configuration and state, the current chat session, as well as saving their own variables that can be kept local to the session or can be persistent and stored in the database.

Flow:
1. Volley is passed to the `pre_process` method.  If that method returns True, it is assumed the method has filled in the response and should be already in place.  Whatever is in the response will be returned for Moxie to play.
2. If `pre_process` returns False, the `prompt` field from the SinglePromptChat will be rendered as a Django template and passed the `volley` and `session` as objects.  The resulting output is used as the prompt that is sent to the AI for inference.
3. Next, the volley is passed to the `post_process` method, which can see the response provided by the AI, alter or adjust it if needed.
4. Finally, if the volley output does not contain markup, the text in the output is automatically converted to markup and added to the output record before sending to Moxie.

```
def pre_process(volley:Volley, session:ChatSession):
    return False

def post_process(volley:Volley, session:ChatSession):
    pass
```

When a conversation completes, the framework calls any `complete_handler` method inside the code block, allowing custom actions to be taken when a conversation completes.  In this case, the Volley object
provided has no request or response data, but still contains access to the local data, persistent data,
and the session itself.

```
def complete_handler(volley, session):
    summary = session.summarize()
    volley.persist_data['last_summary'] = summary
```

If you want to take any actions in response to Moxie playing an output, you can also provide a `notify_handler` that will be called with every output
Moxie plays from the conversation.  Like the `complete_handler`, this volley no response object, but it does contain the full notify request and
accessors for data.

```
def notify_handler(volley, session):
    pass
```

### Volley Object Fields

It is worth looking at site/hive/mqtt/volley.py for all the details, but the volley object contains several properties that gain access to dictionaries for data records.

* local_data - Holds local session data for this specific chat session.  It is discarded when the conversation ends.
* persist_data - Holds the robot's persistent data record.  This data is loaded/saved to the robot's PersistentData model in the database.  There is no namespace, and all data is accessible to all volleys for this robot.
* request - The actual originating RemoteChatRequest object from Moxie
* response - The matching response RemoteChatResponse object going to Moxie
* config - The robot's combined configuration object
* state - The robot's latest state object
* entities - For GlobalResponses only, list of extracted entities

### Conversation Summarization

The session includes a summarize method that allows custom prompts against the conversation history. Keep
in mind that the conversation history is limited by the `max_history` field of the conversation, and will
only be considering the last `max_history` volleys in the summary.

The method signature for summarize is:

```
def summarize(self, model=None, prompt_base=None, max_tokens=None, append_transcript=True):
```

The AI vendor will always be the same for any conversation, but summarization can override the conversation's default model using the `model` parameter, the maximum output using the `max_tokens` parameter and may adjust the base prompt for the summarization which is currently set to:

```
Summarize the following conversation between the friendly robot Moxie, and the user.  Keep the summary brief, but include any important details.
```

Here's an example of a custom action that is pretty silly, but shows how you can ask the AI to review the session in different ways.  After a short chat where I talked about playing Starcraft, the code below produced: `"last_analysis": ["No food talk this time.", "They are still talking about games"]`

```
def complete_handler(volley, session):
    food_summary = session.summarize(prompt_base='Review this conversation.  If the user talked about food, say "They are still talking about food" otherwise say "No food talk this time."')
    games_summary = session.summarize(prompt_base='Review this conversation.  If the user talked about games, say "They are still talking about games" otherwise say "No games talk this time."')
    volley.persist_data['last_analysis'] =  [food_summary, games_summary]
```
