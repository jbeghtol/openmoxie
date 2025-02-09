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
* Prompt - The prompt itself, the language directing the AI how to have this conversation
* Max History - this limits how much of the conversation is sent to the AI in each inference. more history, better memory, but also can degrade AI performance and uses more tokens and you can run into token limits if the history gets too long
* Max Volleys - how long the conversation can go before Moxie calls it quits.  If set to 0, module will exit immediately after the line into the next scheduled activity.
* Vendor - The AI vendor (only OpenAI currently)
* Model - the openAI (or other) model, pick one you like for latency, quality, and cost
* Max Tokens - this is output tokens, usually better to limit in the prompt with things like "keep responses short" as moxie talking forever is usually dull, but if you find it truncating responses increase this
* Temperature - The level of randomness in the model, from 0-1, with 1 having maximum randomness.
* Source version - The last version imported, used to allow new OpenMoxie versions to update the stock content

## AI Response Tags

OpenMoxie supports special xml like tags from the AI.  Tags are structured like unterminated xml tags, e.g. `<exit>`.  All text like this is removed so it doesn't play, but the special tags may be included in the
prompt so that the AI can do things like exit before the max volleys is reached using prompt text like:

```
If the user asks to stop or quit, respond with '<exit>'.
```

### Special Tags

There is only one, but this table may grow.

|Tag|Function|
|---|--------|
|`<exit>`|Completes the module and moves to the next scheduled activity|

