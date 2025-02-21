# Remote Module API

The internal workings of Moxie are rather complex, but the core of remote integration is through two key
messages, RemoteChatRequest and RemoteChatResponse.  These messages are used *even when Moxie is running
local modules*.

The simplified interaction pattern is show here:

1. The input is passed to remote modules via RemoteChatRequest and simulteneous processed the active local module.
2. The event handler generally waits for both responses, the local one and the RemoteChatResponse from the server, and uses the "best" based on some criteria, the most notable being the output_type of both responses.
3. Moxie accepts and plays the best response, sending the input/output on the "notify" channel for remote modules to monitor the outcome and accumulate a comprehensive history.

The GlobalResponse framework takes advantage of this by producing outputs with the highest type, GLOBAL_COMMAND, to ensure the output is taken over any local response.

When a Remote Module is running, for instance one of the custom converastions in OpenMoxie, local content always produces a FALLBACK (the lowest type), and thus the remote module's response plays as long as it
is any higher type, and by default we use GLOBAL_RESPONSE for this.

## Response Actions

The response action (and its plural) are action records attached to a response.  These actions are only
executed on Moxie if the response is accepted for playback.  Originally, there was a single block, but
the API was extended to include a plural version so that multiple action blocks can be included in a single
response.

Fields inside RemoteAction:

* action - (string) one of { launch, launch_if_confirmed, exit_module, abort_module, execute, sleep } 
* module_id - (string) for launch action, target module
* content_id - (string) for launch action, target content
* output_type - (string) usually GLOBAL_RESPONSE for normal responses, GLOBAL_COMMAND for global commands
* function_id - (string) for execute action, name of a function in the robot stack to invoke
* function_args - (list of strings) args to pass to the function
* action_args - (dictionary with string keys and values) params passed through to prompt on launch commands
* event_subscription - (object, see below) an event subscription record

Event subscription record:

* clear - (boolean) reset subscriptions first
* active - (list of strings) events to receive inputs for

## Event Handling

Moxie generates a number of internal events that are discarded by the application stack unless the active module is specifically interested.  If a module wants to field these responses, they must produce a response with an action including the event in the `event_subscription` block.

When an event is subscribed and the event occurs, it is provided to the module as the speech input, so instead of the modules receiving something the user said, it receives a special event string like "eb-found-face".  The remote module must produce some response for this input to continue the interaction.  Some events also include parameters in the `input_vars` field of the request.

### Unsubscribing from Events

Events are automatically unsubscribed when the module exits, but otherwise remain active for the full run 
of the module, unless the event subscription block in a response contains `"clear": true`.


## Execute Methods

### Face Search

The face search methods can trigger the local stack to search for a face to target.  This generally
happens automatically if you say "Moxie look at me" or "Moxie listen to me".  The custom version
allows specification of the size of face to target, which enables patterns where interaction begins
as soon as someone is close enough.  Both generate an `eb-found-face` event when they detect a face.
Once a face is found, the `eb-lost-target` event is generated when the face is lost from view for too long.

* eb_start_binned_face_search : start searching for any face
* eb_custom_face_search (min_width, min_height, unused_float, unused_bool, unused_bool): EXPERIMENTAL start searching for a custom sized face to target.  This was used in some demos but never fully completed.  As such, it requires 4 parameters, but the only two that work are min_width/height which are in float units of how much of the image view they occupy.  This was used for detecting a person in close range: ` "function_args": ["0.15", "0", "0", "true", "true"]`

### Visual Detectors

Custom visual detectors may be run to activate searching for different data using Moxie's camera.  Each 
detector activation remains active only until an item of this type is detected.  If you want to keep the
detector active, the detection event handler response should call the enabler function again.  Users should
also be sure to subscribe to the matching even to receive the detection event properly.

* eb_enable_book(bool) : enable book recognition for moxie trained book covers
* eb_enable_draw(bool) : enable aruco code recognition
* eb_enable_qr(bool) : enable QR reading

### Wait Timers

Moxie's timer model allows timer hooks to fire events.  Timers only run *when no one is speaking*, meaning they begin after Moxie has completed playing the response line.  The shortest timer is the monologue timer,
which is (irrc) a quarter second long and is useful to have Moxie play a series of lines in a row.  The other timers vary and are adjusted by user input timing selections, but the longest is around 10s.  Each of these generates the same event, `eb-wait-complete`.

* eb_wait_monologue : sets a really short wait timer
* eb_wait_short : sets a short wait timer
* eb_wait_medium : sets a medium wait timer
* eb_wait_long : sets a long wait timer
* eb_wait_reprompt : sets a reprompt timer

### Schedule Interaction

These methods adjust or alter the way the current schedule functions.  It is possible to direct moxie to
re-query the schedule from OpenMoxie, to disable global commands, or to create a timer to wake Moxie up
at a specific time.

* eb_reload_schedule : re-query the schedule from the cloud
* eb_set_override_gcs (string) : selectively disable the native global command signals, takes a csv string of the signals to disable (e.g. to disable quit and earmuffs use `"function_args": ["handleQuit,handleEarmuffs"]`), see Global Command Signal Names below.
* eb_timer_request (alarm_number, timestamp_ms) : EXPERIMENTAL start a single fixed real-time timer to expire in the future.  A timestamp_ms of 0 stops any timer with this alarm_number.  See Timer Handler below for details.

#### Global Command Signal Names

* handleRepeat : "moxie please repeat that"
* handleInterrupt : "Moxie/Moxie hold on"
* handleExitEarmuff : "moxie listen to me (while in earmuffs)"
* handleSleep : "moxie go to sleep"
* handleLook : "Moxie look at me/moxie listen to me"
* handleLouder : "moxie speak up"
* handleQuieter : "moxie speak softer"
* handleEarmuffs : "moxie earmuffs"
* handleQuit : "moxie do something else"

## Events

Minor note: Some variable names have a leading $ and some do not.

* eb-br-event : a moxie book was visually detected, book name in `input_vars['$eb_br_value']`
* eb-dr-event : an aruco code was detected, aruco code in `input_vars['$eb_dr_value']`
* eb-qr-event : a QR code was read, QR string in `input_vars['$eb_qr_value']`
* eb-found-face : a face matching the search params was found
* eb-lost-face : our target face was lost from view
* eb-wait-complete : a wait timer has expired

## Timer Handler

When a real-time timer expires on the robot, Moxie wakes up if needed and launches the timer module defined in the `alarm_module` key of the schedule.  By default there is none, so this must be defined and this module needs to exist.

```
"alarm_module": { "module_id": "ALARM", "content_id": "alert"}
```

Multiple timers may exist.  The specific timer number is passed in `input_vars['eb_timer_id']` when the alarm module fires.
