import random
import logging
import numpy
from .util import run_db_atomic
from ..models import MoxieDevice,MentorBehavior

logger = logging.getLogger(__name__)

# All the native/chatscript based modules that can be added to the schedule
_RECOMMENDABLE_MODULES = [
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

# Number of content IDs inside these FTUE modules
_TNT_CIDS = 9
_SYSTEMSCHECK_CIDS = 4

'''
Quick and dirty auto-scheduler; attempts to pick a random set of modules avoiding adjacencies
and preferring a broad range of categories
'''
def ransac_select(modules, count):
    count = len(modules) if count > len(modules) else count
    best_list = []
    best_score = 100

    for i in range(20):
        random_list = random.sample(modules, len(modules))
        cat_map = {}
        last_cat = None
        score = 0
        for m in range(count):
            cat = random_list[m].get('category', 'User')
            if cat == last_cat:
                score += 5 # penalty for two adjacent categories
            if cat in cat_map:
                cat_map[cat] += 1
                score += 1 # penalty for dupe category
            else:
                cat_map[cat] = 1
            last_cat = cat
        #logger.info(f'Run {i} - Score {score} - Best {best_score}')
        if score < best_score:
            best_score = score
            best_list = random_list[:count]

    return best_list

# mix list2 elements into list1
def distribute_elements(list2, list1):
    # swap lists so list2 is always larger
    if len(list1) > len(list2):
        list1,list2 = list2,list1
    result = list2[:]
    gap = len(list2) // (len(list1) + 1)
    offset = 0
    for elem in list1:
        result.insert(offset + gap, elem)
        offset += gap + 1
    return result

'''
A bit hokey, but these "training" (first time user experience) modules have content IDs in order but
the robot internal scheduler switches to a random cid once they exhaust, so they have to be removed
or TNT and SYSTEMSCHECK will still be in every session
'''
def ftue_remove(device_id):
    purge_list = []
    try:
        if MentorBehavior.objects.filter(device__device_id=device_id, module_id="TNT", action="COMPLETED").count() >= _TNT_CIDS:
            purge_list.append("TNT")
        if MentorBehavior.objects.filter(device__device_id=device_id, module_id="SYSTEMSCHECK", action="COMPLETED").count() >= _SYSTEMSCHECK_CIDS:
            purge_list.append("SYSTEMSCHECK")
    except Exception as e:
        logger.warning(f'Error checking FTUE completions {e}')
    return purge_list

'''
Schedule Generation - generates a set of additional modules according to the generate key
to make a random schedule for the session.
'''
def expand_schedule(schedule, device_id):
    if 'generate' in schedule:
        logger.info("Using generative schedule")
        # Update schedule data with automatic stuff
        chat_count = schedule['generate'].get('chat_count', 2)
        module_count = schedule['generate'].get('module_count', 6)
        chat_modules = schedule['generate'].get('chat_modules', [{'module_id': 'OPENMOXIE_CHAT', 'content_id': 'short'}])
        extra_modules = schedule['generate'].get('extra_modules', [])
        excluded_module_ids = schedule['generate'].get('excluded_module_ids', [])
        provided = schedule.get('provided_schedule', [])

        # TNT and SYSTEMSCHECK have to be removed manually, as robot will keep playing something
        ftue_remove_list = run_db_atomic(ftue_remove, device_id)
        if ftue_remove_list:
            provided = [item for item in provided if item.get('module_id') not in ftue_remove_list]

        # modules we can pick from, all recommmended unless excluded, plus any user defined extra modules
        auto_modules = [item for item in _RECOMMENDABLE_MODULES if item['module_id'] not in excluded_module_ids]
        auto_modules.extend(extra_modules)
        generated = ransac_select(auto_modules, module_count)

        # insert some random chats
        if chat_count > 0 and len(chat_modules) > 0:
            generated_chats = list(numpy.random.choice(chat_modules, size=chat_count, replace=True))
            generated = distribute_elements(generated, generated_chats)

        # add the gen list to the end
        provided.extend(generated)
        # assign it back just in case we created the list
        schedule['provided_schedule'] = provided

    return schedule
