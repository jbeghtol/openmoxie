import re

# Daily Missing Sets, content_ids for DM grouped by Mission ID
DM_MISSION_CONTENT_IDS={'Understanding_Emotions': ['17_1_Therapy', '17_2_Mindfulness', '17_3_Mindfulness', '17_4_Drawing', '17_5_Report', '17_6_Reply'], 'Making_Friends': ['1_1_Therapy', '1_2_Drawing', '1_3_Therapy', '1_4_Mindfulness', '1_5_Fetch1', '1_5_Fetch2', '1_6_Fetch1', '1_6_Fetch2', '1_7_Therapy', '1_8_Report', '1_9_Reply'], 'Being_Kind': ['0_1_Therapy', '0_2_Drawing', '0_3_Therapy', '0_4_Fetch1', '0_4_Fetch2', '0_5_Therapy', '0_6_Therapy', '0_7_MakeAStory', '0_8_Therapy', '0_9_Report', '0_10_Reply'], 'Knowing_Your_Space': ['6_1_Drawing', '6_2_Drawing', '6_3_Therapy', '6_4_Therapy', '6_5_Therapy', '6_6_Therapy', '6_7_Fetch1', '6_7_Fetch2', '6_8_Therapy', '6_9_Report', '6_10_Reply'], 'Being_Helpful': ['5_1_Therapy', '5_2_Fetch1', '5_2_Fetch2', '5_3_Therapy', '5_4_Therapy', '5_5_Therapy', '5_6_MakeAStory', '5_7_Fetch1', '5_7_Fetch2', '5_8_Therapy', '5_9_Report', '5_9_Reply'], 'Making_Mistakes': ['8_1_Therapy', '8_2_Fetch1', '8_2_Fetch2', '8_3_Therapy', '8_4_Therapy', '8_5_Therapy', '8_6_Mindfulness', '8_7_Drawing', '8_8_Therapy', '8_9_Report', '8_10_Reply'], 'Missing_People': ['4_1_Therapy', '4_2_Drawing', '4_3_Therapy', '4_4_Fetch1', '4_4_Fetch2', '4_5_Therapy', '4_6_Therapy', '4_7_Drawing', '4_8_Therapy', '4_9_Report', '4_10_Reply'], 'Navigating_Nighttime': ['7_1_Therapy', '7_1_Fetch1', '7_2_Fetch2', '7_3_Therapy', '7_4_MakeAStory', '7_5_Therapy', '7_6_Mindfulness', '7_7_Fetch1', '7_7_Fetch2', '7_8_Therapy', '7_9_Report', '7_10_Reply'], 'Exploring_Your_Home': ['2_1_Therapy', '2_2_Drawing', '2_3_Therapy', '2_4_Mindfulness', '2_5_Therapy', '2_6_MakeAStory', '2_7_Fetch1', '2_7_Fetch2', '2_8_Therapy', '2_9_Report', '2_10_Reply'], 'Exploring_Your_World': ['3_1_Reflection', '3_2_Drawing', '3_3_Reflection', '3_4_Fetch1', '3_4_Fetch2', '3_5_Reflection', '3_6_Drawing', '3_7_MakeAStory', '3_8_Reflection', '3_9_Report', '3_10_Reply'], 'Learning_About_Family': ['10_1_Therapy', '10_2_Fetch1', '10_2_Fetch2', '10_3_Therapy', '10_4_Drawing', '10_5_Advice', '10_6_MakeAStory', '10_7_Therapy', '10_8_Advice', '10_9_Reflection', '10_10_Report', '10_11_Reply'], 'Feeling_Mad': ['11_1_Therapy', '11_2_Drawing', '11_3_Therapy', '11_4_Therapy', '11_5_Therapy', '11_6_Therapy', '11_7_Therapy', '11_8_Therapy', '11_9_Report', '11_10_Reply'], 'Being_Different': ['12_1_Reflection', '12_2_MakeAStory', '12_3_Reflection', '12_4_Therapy', '12_5_Reflection', '12_6_MakeAStory', '12_7_Fetch1', '12_8_Fetch2', '12_9_Reflection', '12_10_Report', '12_11_Reply'], 'Being_a_Good_Sport': ['13_1_Reflection', '13_2_Advice', '13_3_Reflection', '13_4_Advice', '13_5_Fetch1', '13_6_Fetch2', '13_7_Reflection', '13_8_Report', '13_9_Reply']}

# All the native/chatscript based modules that can be added to the schedule
RECOMMENDABLE_MODULES = [
{'module_id': 'AFFIRM', 'category': 'REGULATION'},
{'module_id': 'AB', 'category': 'REGULATION'},
{'module_id': 'ANIMALEXERCISE', 'category': 'MOVEMENT'},
{'module_id': 'BODYSCAN', 'category': 'REGULATION'},
{'module_id': 'RDL', 'category': 'FUN_TIDBIT'},
{'module_id': 'BREATHINGSHAPES', 'category': 'REGULATION'},
{'module_id': 'COMPOSING', 'category': 'CREATIVITY'},
{'module_id': 'FACES', 'category': 'PLAYFUL_GAME'},
{'module_id': 'FF', 'category': 'FUN_TIDBIT'},
{'module_id': 'GUIDEDVIS', 'category': 'REGULATION'},
{'module_id': 'JOKE', 'category': 'FUN_TIDBIT'},
{'module_id': 'JUKEBOX', 'category': 'LISTENING'},
{'module_id': 'MENTORSAYS', 'category': 'PLAYFUL_GAME'},
{'module_id': 'NONSENSE', 'category': 'FUN_TIDBIT'},
{'module_id': 'DANCE', 'category': 'MOVEMENT'},
{'module_id': 'DRAW', 'category': 'CREATIVITY'},
{'module_id': 'STORYTELLING', 'category': 'CREATIVITY'},
{'module_id': 'PASSWORDGAME', 'category': 'PUZZLE_GAME'},
{'module_id': 'READ', 'category': 'READING'},
{'module_id': 'SCAVENGERHUNT', 'category': 'PLAYFUL_GAME'},
{'module_id': 'STORY', 'category': 'LISTENING'},
{'module_id': 'AUDMED', 'category': 'REGULATION'},
{'module_id': 'WHIMSY', 'category': 'FUN_TIDBIT'},
]

TNT_CIDS = 9
SYSTEMSCHECK_CIDS = 4

# NOTE: These may not work.  In tested some were crashing Unity on Moxie
# If problem assets are found, they should be removed from this list so they
# do not get used.
MOXIE_CUSTOMIZATIONS = [
"MX_010_Eyes_Brown",
"MX_010_Eyes_Gold",
"MX_010_Eyes_Grey",
"MX_010_Eyes_Hazel",
"MX_010_Eyes_LightBlue",
"MX_010_Eyes_Purple",
"MX_010_Eyes_Turquoise",
"MX_020_Face_Colors_Green",
"MX_020_Face_Colors_Pink",
"MX_020_Face_Colors_Purple",
"MX_020_Face_Colors_Teal",
"MX_020_Face_Colors_Yellow",
"MX_030_Eye_Designs_BlueCircuits",
"MX_030_Eye_Designs_BlueClouds",
"MX_030_Eye_Designs_Circuits",
"MX_030_Eye_Designs_Clouds",
"MX_030_Eye_Designs_Gears",
"MX_030_Eye_Designs_GoldStars",
"MX_030_Eye_Designs_PurpleGears",
"MX_030_Eye_Designs_RedHearts",
"MX_030_Eye_Designs_Stars",
"MX_040_Face_Designs_Candies",
"MX_040_Face_Designs_Flowers01",
"MX_040_Face_Designs_Hearts",
"MX_040_Face_Designs_Leaves01",
"MX_040_Face_Designs_Stars",
"MX_050_Eyelid_Designs_GreenEyeShadow",
"MX_050_Eyelid_Designs_PurpleEyeShadow",
"MX_050_Eyelid_Designs_RainbowStars",
"MX_050_Eyelid_Designs_RedEyeShadow",
"MX_050_Eyelid_Designs_SmokeyLashes",
"MX_060_Mouth_BlackSmall",
"MX_060_Mouth_DarkRedMedium",
"MX_060_Mouth_PinkPointy",
"MX_060_Mouth_PurpleFull",
"MX_060_Mouth_RedMedium",
"MX_080_Head_Hair_BlackBob",
"MX_080_Head_Hair_BlackCenter",
"MX_080_Head_Hair_PinkShag",
"MX_080_Head_Hair_RedShag",
"MX_090_Facial_Hair_BlackAngled",
"MX_090_Facial_Hair_BlackDali",
"MX_090_Facial_Hair_BrownHandlebar",
"MX_090_Facial_Hair_OrangeBatWing",
"MX_090_Facial_Hair_YellowUpturn",
"MX_100_Brows_BrownCut",
"MX_100_Brows_GreyShort",
"MX_100_Brows_Purple",
"MX_100_Brows_WhiteBushy",
"MX_100_Brows_YellowThin",
"MX_120_Glasses_BlueHeart",
"MX_120_Glasses_GoldHalfRound",
"MX_120_Glasses_RedCat",
"MX_120_Glasses_RoundWhiteDot",
"MX_120_Glasses_SmallRound",
"MX_130_Nose_Cat",
"MX_130_Nose_Clown",
"MX_130_Nose_Dog",
"MX_130_Nose_Human01",
"MX_130_Nose_Pig",
]

_SPLIT_GROUPS = None

def get_moxie_customization_groups():
    global _SPLIT_GROUPS
    if not _SPLIT_GROUPS:
        pattern = r"MX_(\d{3})_([a-zA-Z]+)_(.*)"
        _SPLIT_GROUPS = []
        curr_layer = None
        for label in MOXIE_CUSTOMIZATIONS:
            match = re.match(pattern, label)
            if match:
                if match.group(3).startswith('Designs') or match.group(3).startswith('Colors') or match.group(3).startswith('Hair'):
                    layer_name = match.group(2) + "_" + match.group(3).split('_')[0]
                    detail = match.group(3).split('_')[1]
                else:
                    layer_name = match.group(2)
                    detail = match.group(3)[:-5] if match.group(3).endswith('_icon') else match.group(3)
                if layer_name != curr_layer:
                    _SPLIT_GROUPS.append({'layer': layer_name, 'labels': []})
                    curr_layer = layer_name
                _SPLIT_GROUPS[-1]['labels'].append({ 'name': detail, 'label': label })

    return _SPLIT_GROUPS

if __name__ == "__main__":
    get_moxie_customization_groups()