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

# Schedules

The system includes an initial `default` schedule which is automatically used for all Moxie's that connect.  The
default schedule uses the `provided_schedule` block to define the start of the scheduled day.  Some of the
modules in the start of the day may be skipped automatically if not appropriate.  For instance ENROLLCONVO only
plays if the mentor hasn't done an enrollment conversation recently and EVENTSANDHOLIDAYS only plays if there is
an active event for the current calendar day.

The default schedule includes a special block called `generate` that fills out the rest of the schedule using the
code in `site\hive\mqtt\scheduler.py`.  You may edit the `default` schedule in the Admin view or create a new
one and assign it to your Moxie.  Note: TNT and SYSTEMSCHECK are removed dynamically if already experienced when
you include the `generate` block.

```
{
    "provided_schedule": [
        {
          "module_id": "ENROLLCONVO"
        },
        {
          "module_id": "EVENTSANDHOLIDAYS"
        },
        {
          "module_id": "TNT"
        },
        {
          "module_id": "SYSTEMSCHECK"
        },
        {
          "module_id": "OPENMOXIE_CHAT",
          "content_id": "short"
        },
        {
          "module_id": "DM"
        }       
    ],
    "generate": {
      "chat_count": 2,
      "module_count": 6,
      "chat_modules": [ 
        {
          "module_id": "OPENMOXIE_CHAT",
          "content_id": "short"
        }
      ],
      "extra_modules": [],
      "excluded_module_ids": []
    },
    "chat_request":
    {
      "module_id": "OPENMOXIE_CHAT",
      "content_id": "default"
    }
}

```

## Extra Schedules

Schedules may be edited or created in the Admin view.  There are two additional schedules provided by default
which are `only_chat` which has only a long running conversation module, and `no_onboarding` which is identical
to the default schedule, but doesn't have Tips and Tricks or Systems Check modules.

## Keys

* provided_schedule - a list of module_ids with or without content_ids
* wake_module - the module ID for an alternate wakeup module (needs all wakeup content IDs)
* chat_request - the module/content ID when user asks "moxie let's chat"
* end_of_session - a block describing what to do when the schedule is done, where you do the `end_module` followed by `chat_count` of the `chat_module` before being forced to sleep
* generate - rules to automatically extend the schedule
* hub_config - If configured, hub modules are automatically scheduled in between most modules in the schedule (see below)

### Generation Keys

* chat_count - Number of random chats to inject into the schedule
* chat_modules - A list of module/content IDs to randomly pick `chat_count` conversations from
* module_count - Number of modules to append to the schedule
* extra_modules - A list of user created module/content IDs that can be scheduled in addition to the default content modules
* excluded_module_ids - A list of module_id values that should *not* end up in the schedule

### Wakeup Module

If you want to wake Moxie up directly into the schedule, without having to go through the normal
wakeup routine first, you may create or use a custom module.  A default version is provided called
WAKEUP_LAUNCHER.  To use this, add this to your schedule:

```
"wake_module": { "module_id": "WAKEUP_LAUNCHER" },
```

### Hub Module(s)

The schedule can also automatically inject a "hub" module in between most activities in the schedule.  The
term stems fro the "hub and spokes" navigation model, where after each activity, you return to a central
hub to find something to do next.

The scheduler loops repeatedly through the list of `hubs` each time it return to the hub, though only 
one is required in the list.

```
"hub_config": {"hubs": [{"module_id": "MOXIE_GO", "content_id": "default"}] }
```

# Configuration and Settings

Every robot is provided a configuration file with a number of configuration options.  There are also
a set of settings properties that can alter robot behavior.  The configuration and settings within
OpenMoxie are stored in the database.

There are *common* config and settings blocks inside the HiveConfiguration record, and each MoxieDevice
may also have its own `robot_config` and `robot_settings`.  The system overlays the robot versions
over the common versions, allowing `robot_config` to override or add to any values in `common_config` and
similarly allowing `robot_settings` to override `common_settings` values.

## Configuration - Important!

You can absolutely cause your Moxie to behave eratically changing configuration or settings.  Be careful
making changes, as violating the schema may cause your robot to reject the configuration entirely.

### Default Config

```
{ 
  "pairing_status": "paired", <-- ROBOT IS PAIRED, DO NOT REMOVE THIS!
  "audio_volume": "0.6", <-- AUDIO VOLUME FROM 0-1  
  "screen_brightness": "1.0", <-- SCREEN BRIGHTNESS from 0-1
  "audio_wake_set": "off",   <-- IF MOXIE CAN WAKE FROM SCREEN OFF FROM AUDIO: { off, low, high }
  "timezone_id": "America/Los_Angeles", <-- FOR ANY TIME RELATED ISSUES, THE TIMEZONE ID
  "child_pii": {   <-- MENTOR DETAILS
      "nickname": "Pat",  <-- MENTOR NICKNAME
      "input_speed": 0.0 <-- DELAYS TO WAIT LONGER ON USERS INPUT 0-1 (fastest - slowest )
  }
}
```

### Child Record Details

The "child_pii" record is the decrypted record about the child using Moxie.  Apologies, but for simplicity
I'm using the google protocol buffer schema (which is what the robot uses).  I have omitted fields that
have no function.

```
message child_pii {
	string first_name = 1;
	string last_name = 2;
	string nickname = 3;
	string birthday = 4;									// as an ISO8601 timestamp, midnight on bday in parent app timezone
	repeated string volume_preference = 10;					// volume_preference in {nohud,nosoundfx,novisualfx,lessmotion,slowoutput,slowinput}
	repeated string calendar_events = 11;					// a list of active non-holiday calendar events 
	repeated string holiday_events = 13;					// a list of active holiday events
	repeated string face_options = 17;
	float input_speed = 19;
}
```

The `birthday` is pertinent if you want the BIRTHDAY module to play on the mentor's birthday.  A timestamp
is in ISO8601 format specifically.  Example: `2023-10-27T10:00:00-07:00`

The `volume_preference` is a list of strings repesenting accessibility options previously available in the parent app. They are enabled by being added to the list.  The names are shown in the comment.

The `face_options` value is a list of strings representing custom face option assets.  There are a number of these and most of them require a single value per layer (e.g. one eye color, one face color, etc.).

#### Face Option Assets (Partial)

There are a number of face options. Face color and eye color were well tested and visible previously.  There are
a bunch of custom face assets created but they are not well tested!  In testing, found some would crash Unity,
and these were not listed, but many of them are listed and usable in the face editor.  Use them with caution
and undo if you run into any issues.

* Face colors
```
  yellow: 'MX_020_Face_Colors_Yellow'
  green: 'MX_020_Face_Colors_Green'
  teal: 'MX_020_Face_Colors_Teal'
  pink: 'MX_020_Face_Colors_Pink'
  purple: 'MX_020_Face_Colors_Purple'
```

* Eye Colors
```
  brown: 'MX_010_Eyes_Brown'
  gold: 'MX_010_Eyes_Gold'
  hazel: 'MX_010_Eyes_Hazel'
  purple: 'MX_010_Eyes_Purple'
  turquoise: 'MX_010_Eyes_Turquoise'
  light_blue: 'MX_010_Eyes_LightBlue'
  blue: 'MX_010_Eyes_LightBlue'
  teal: 'MX_010_Eyes_Turquoise'
```

### Extra Config Items of Note

```
  "wake_button_enabled": true, <-- IF SET, MOXIE WILL NEVER GO TO SUSPEND AND WILL REMAIN NETWORK CONNECTED
  "touch_wake_enabled": true, <-- USED WITH touch_wake setting, IF SET TOUCHING MOXIE FROM STANDBY WILL WAKE
```

## Settings - Important!

These can also be dangerous.  Settings are stored inside a props key and are all strings, even if they are numbers.

### Default Settings

```
{
    "props": {
      "touch_wake": "1", <-- CAN WAKE UP MOXIE FROM TOUCH ALONE (also requires touch_wake_enabled in config)
      "wake_alarms": "1", <-- CAN WAKE FROM SCHEDULED ALARMS
      "wake_button": "1", <-- SET TRUE TO ENABLE WAKE BUTTON SUPPORT (still needs wake_button_enabled)
      "doa_range": "80", <-- ASSUME TARGETS ARE IN FRONT 80 degrees
      "target_all": "1", <-- MOXIE WILL LISTEN TO ANYONE, "1" is ON, "0" is OFF
      "gcp_upload_disable": "1", <-- WILL NOT WORK, DO NOT CHANGE
      "local_stt": "on", <-- USE LOCAL SPEECH TO TEXT FOR WAKE PHRASES
      "max_enroll": "2", <-- MAX TIMES TO OFFER ENROLLMENT CONVERSATION PER SESSION, "0" to disable
      "audio_wake": "1", <-- CAN CONFIGURE MOXIE FOR AUDIO WAKEUP
      "cloud_schedule_reset_threshold": "5", <-- HOW LONG ASLEEP BEFORE ASKING FOR A NEW SCHEDULE
      "debug_whiteboard": "0", <-- TURN ON WHITEBOARD SHOWING USER SPEECH, "1" is ON
      "brain_entrances_available": "1" <-- ALLOW GLOBAL LAUNCH PATTERNS
    }
}
```

### Extra Setting Items of Note

```
  "stt": "4", <-- IF USING A GOOGLE SERVICE ACCOUNT KEY, SET TO "0", "4" USES ZMQ VIA MOXIE SERVER
  "no_reprompt": "1", <-- SET TO "0" to PREVENT MOXIE FROM AUTOMATICALLY REPROMPTING ONCE AFTER 10s
```

# Special Modes - Telehealth (Puppet Mode)

Moxie's software stack does have a special mode created for remote control.  This state is controlled through
a config option `moxie_mode` which when set to `TELEHEALTH` puts Moxie into an awake mode that doesn't use
the schedule or run any autonomous control.  In this mode, Moxie simple plays outputs by request.

In this mode, special messages arrive on the `telehealth` subtopic and may be send on the `telehealth` command topic. 
Reference code for this is in the Puppet Mode interaction.  The bulk of the fancy things you can do require more intimate
knowlege of Moxie's markup xml language, so a simple pure-automatic method is shown where an emotional state can be picked to go with the speech.

Almost all JSON data coming from and going to Moxie is parsed using Google Protocol buffers, which enforce that the data
conform to the schema.  Below is the schema for Telehealth messages.  All fields are optional in the schema, and some
are included only in robot->cloud and some only in cloud->robot.

The "session" convention serves little function in OpenMoxie, but practically it enables STT services that are ignored so
unless you have need to use them, it's better to stay out of session for local puppeteering to reduce STT cost.

```
message Output {
  string text = 3;        // text to say, used only if markup is empty
  string markup = 4;      // marked-up text to say, used by default
}

enum Action {
  UNKNOWN_ACTION = 0;     // specifically including UNKNOWN as the default enum

  START_SESSION = 1;      // direct moxie into session
  PLAY_OUTPUT = 2;        // say something
  END_SESSION = 3;        // direct moxie out of session
  UPDATE_STATE = 4;       // moxie state updates
  INTERRUPT = 5;          // interrupt current moxie playback
}

enum RobotState {
  UNKNOWN_STATE = 0;      // specifically including UNKNOWN as the default enum

  READY = 1;              // Moxie is ready to receive telehealth commands
  IN_SESSION = 2;         // Moxie has transitioned into active use
  EXITING = 3;            // Moxie is leaving telehealth state
}

message TelehealthMessage {
  uint64 timestamp = 1;
  Action action = 2;              // an action to process
  Output output = 3;              // optional attached output block
  RobotState state = 4;           // optional attached state
  string session_id = 5;          // optional, session id
}
```

An example of a simple playback message:

```
tmsg = { "action": "PLAY_OUTPUT", "output": { "text": "Moxie loves you!" } }
```