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