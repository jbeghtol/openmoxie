# Moxie Overview

Moxie is pretty complex and the goal of this overview is to hit the highlights
of what the cloud services can do to get Moxie into an interactive mode and run
interactive local content and cloud-based content, of which is there is very little.

# Life Cycle

Moxie follows this general life cycle in its software stack.

1. Boot
2. Wifi App (QR codes, wifi credentials, cloud connectivity/configuration check)
3. Running (Sleep, In-session)
4. Light Sleep (Screen off, network active)
5. Suspend (Screen off, disconnected, suspended)

Cloud connectivity is key to get past step 2.  And cloud connectivity means WiFi connected,
connected to an MQTTS service that tells Moxie is ready and cleared for use. Without this
step, Moxie's will remain stuck at step 2.  By design, the MQTTS service is bound to a set
of fixed known addresses, and the SSL certificate is peer verified.  This makes it difficult
to do until our 24.10.801 release which enabled a custom cloud services endpoint configuration
to relocate Moxie to alternate and even unverified MQTTS services.

## Do I Have to Live in this cycle?

Yep.  Moxie's OS is still locked down.  Every bot has a locked bootloader, Android Verified Boot,
and SE Linux making it really difficult (by design) to alter any part of the OS and embedded software.  If you
want to try, go for it!  But this is about what you can do without changing the core OS and software.

# In-Session

Interactive sessions are driven by a cloud-based schedule, a set of cloud-provided data records for
history, and a descriptor of cloud-based content modules.  If these things are provided by the cloud,
Moxie will wake up into session based on any of the wake phrases (Moxie wake up), all of which is handled
by a local ASR.

Sessions are driven by blocks of content which have a module_id and usually a content_id or many content IDs.
Moxie attempts to go through each of the content blocks in the schedule in order, but can be interrupted
through global commands to transition to other modules.  If modules are requested that are in the future schedule,
they are removed from the schedule so they are not done twice.

# Schedule Schema

```
{
    "provided_schedule": [
        {
        "module_id": "OPENMOXIE_CHAT",
        "content_id": "default"
        },
        {
        "module_id": "AB"
        },
        {
        "module_id": "OPENMOXIE_CHAT",
        "content_id": "default"
        }
    ],
    "chat_request":
    {
      "module_id": "OPENMOXIE_CHAT",
      "content_id": "default"
    },
    "end_of_session": {
      "chat_count": 2,
      "chat_module": {
        "module_id": "OPENMOXIE_CHAT",
        "content_id": "default"
      },
      "end_module": {
        "module_id": "DAILY_WRAPUP",
        "content_id": "default"
      }
    },
}
```

## Keys

* provided_schedule - a list of module_ids with or without content_ids
* chat_request - the module/content ID when user asks "moxie let's chat"
* end_of_session - a block describing what to do when the schedule is done, where you do the `end_module` followed by `chat_count` of the `chat_module` before being forced to sleep








