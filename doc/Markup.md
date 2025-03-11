# Moxie Markup Language

This is one of the most important parts of the system, as "markup" is the language Moxie uses to process outputs.
Markup supports some subset of SSML.  There is a discussion with a link to the voice synth engine documentation
which explains the parts of SSML that are supported.  In addition to general voice customization parameters, 
Markup can make Moxie move, dance, put icons on the screen, play sound effects, etc.  Unfortunately, this was
all rendered using a custom tool inside Embodied that was never released.

To be helpful, I have included  [Moxie Asset Manifest](doc/AssetBundleMasterManifest.csv) in the source.  This
file details every asset available inside Moxie's asset repository.

Columns
* Lbl - The label or name, used to reference the asset in markup
* Asset Bundle - The bundle name, rarely important
* Asset Type - The type of asset
* Default - True if the asset is loaded and available by default

Not all of these assets are guaranteed to work, I know at least some of the Moxie Customizations crash Unity and I removed
them from the Face Editor, but they are still in the robot and this manifest.  Use at your own risk.

Non-default Assets cannot be used until loaded.  They can (I hope) be loaded dynamically from a module using the
`eb_cache_assets_csv` method and passing a csv string with the Asset Bundle names to load, and can then be released
if needed (this happens automatically on module exit) using the `eb_release_assets_csv`.

## Markup is XML-JSON WHY?

It is ugly, and why?! I share your sentiment.  Markup uses XML tags that include attributes with JSON data using the + delimeter.  I do not know what they all do, or if they all work, but I very much doubt they *all* work.

## Sound Effects

This is an example of sound effect playback for the sound with Lbl `sfxmm_incoming02`

```
<mark name="cmd:playaudio,data:{+SoundToPlay+:+sfxmm_incoming02+,+LoopSound+:false,+playInBackground+:false,+channel+:1,+ReplaceCurrentSound+:false,+PlayImmediate+:true,+ForceQueue+:false,+Volume+:1.0,+FadeInTime+:0.0,+FadeOutTime+:2.0,+AudioTimelineField+:+none+}"/>
```

## Changing Behavior Trees

This puts Moxie into the eyes closed, upright pose behavior tree with Lbl `Bht_Sleeping_Zero_Pose`

```
<mark name="cmd:behaviour-tree,data:{+transition+:0.5,+duration+:1.0,+repeat+:1,+layerBlendInTime+:0.5,+layerBlendOutTime+:0.5,+blocking+:false,+action+:0,+variableName+:++,+variableValue+:++,+eventName+:+Gesture_None+,+lifetime+:0,+category+:+None+,+behaviour+:+Bht_Sleeping_Zero_Pose+,+Track+:++}"/>
```