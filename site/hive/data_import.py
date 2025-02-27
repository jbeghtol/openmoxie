from .models import MoxieSchedule, SinglePromptChat,GlobalResponse

# Compare content data from import_data against existing content and add meta_state with this status
def update_import_status(import_data:dict):
    for rec in import_data.get("globals", []):            
        try:
            def_gr = GlobalResponse.objects.get(name=rec["name"])
            if def_gr.source_version < rec["source_version"]:
                rec["meta_state"] = f"Upgrade from v{def_gr.source_version}"
            else:
                rec["meta_state"] = f"Replace v{def_gr.source_version}"
        except GlobalResponse.DoesNotExist:
            rec["meta_state"] = "New"
    for rec in import_data.get("schedules", []):
        try:
            def_sched = MoxieSchedule.objects.get(name=rec["name"])
            if def_sched.source_version < rec["source_version"]:
                rec["meta_state"] = f"Upgrade from v{def_sched.source_version}"
            else:
                rec["meta_state"] = f"Replace v{def_sched.source_version}"
        except MoxieSchedule.DoesNotExist:
            rec["meta_state"] = "New"
    for rec in import_data.get("conversations", []):
        try:
            def_chat = SinglePromptChat.objects.get(module_id=rec["module_id"], content_id=rec["content_id"])
            if def_chat.source_version < rec["source_version"]:
                rec["meta_state"] = f"Upgrade from v{def_chat.source_version}"
            else:
                rec["meta_state"] = f"Replace v{def_chat.source_version}"
        except SinglePromptChat.DoesNotExist:
            rec["meta_state"] = "New"

# Import content data from import_data into the database, using only the indexes provided for each type
def import_content(import_data:dict, global_indexes:list, schedule_indexes:list, conversation_indexes:list):
    message = "Imported:"
    gnames = []
    for idx in global_indexes:
        rec = import_data["globals"][int(idx)]
        try:
            def_gr = GlobalResponse.objects.get(name=rec["name"])
            def_gr.__dict__.update(rec)
            def_gr.save()
        except GlobalResponse.DoesNotExist:
            model_fields = [f.name for f in GlobalResponse._meta.get_fields()]
            filtered_rec = {k: v for k, v in rec.items() if k in model_fields}
            GlobalResponse.objects.create(**filtered_rec)
        gnames.append(rec["name"])

    snames = []
    for idx in schedule_indexes:
        rec = import_data["schedules"][int(idx)]
        try:
            def_sched = MoxieSchedule.objects.get(name=rec["name"])
            def_sched.source_version = rec["source_version"]
            def_sched.schedule = rec["schedule"]
            def_sched.save()
        except MoxieSchedule.DoesNotExist:
            MoxieSchedule.objects.create(name=rec["name"], schedule=rec["schedule"], source_version=rec["source_version"])
        snames.append(rec["name"])

    cnames = []
    for idx in conversation_indexes:
        rec = import_data["conversations"][int(idx)]
        try:
            def_chat = SinglePromptChat.objects.get(module_id=rec["module_id"], content_id=rec["content_id"])
            def_chat.__dict__.update(rec)
            def_chat.save()
        except SinglePromptChat.DoesNotExist:
            def_chat = SinglePromptChat.objects.create(module_id=rec["module_id"], content_id=rec["content_id"])
            def_chat.__dict__.update(rec)
            def_chat.save()
        cnames.append(f"{rec['module_id']}:{rec['content_id']}")

    if gnames:
        message += f"\nGlobalResponses[{', '.join(gnames)}]"
    if snames:
        message += f"\nSchedules[{', '.join(snames)}]"
    if cnames:
        message += f"\nConversations[{', '.join(cnames)}]"
    if not gnames and not snames and not cnames:
        message += "\nNothing to import."
    return message
