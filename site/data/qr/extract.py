import qrcode

# List of modules
modules = [
    {"module_id": "AFFIRM", "description": "Positive affirmations for self-regulation"},
    {"module_id": "AB", "description": "A/B exercise for self-regulation"},
    {"module_id": "ANIMALEXERCISE", "description": "Movement exercise inspired by animals"},
    {"module_id": "BODYSCAN", "description": "Body scan for relaxation and self-regulation"},
    {"module_id": "RDL", "description": "Random daily laugh for fun"},
    {"module_id": "BREATHINGSHAPES", "description": "Breathing exercises for self-regulation"},
    {"module_id": "COMPOSING", "description": "Composing music for creativity"},
    {"module_id": "FACES", "description": "Facial recognition game for playful learning"},
    {"module_id": "FF", "description": "Fun fact of the day"},
    {"module_id": "GUIDEDVIS", "description": "Guided visualization for relaxation"},
    {"module_id": "JOKE", "description": "Daily joke for laughter"},
    {"module_id": "JUKEBOX", "description": "Music listening exercise"},
    {"module_id": "MENTORSAYS", "description": "Mentor's words of wisdom for playful learning"},
    {"module_id": "NONSENSE", "description": "Nonsense words for fun"},
    {"module_id": "DANCE", "description": "Dance movement exercise"},
    {"module_id": "DRAW", "description": "Drawing exercise for creativity"},
    {"module_id": "STORYTELLING", "description": "Storytelling exercise for creativity"},
    {"module_id": "PASSWORDGAME", "description": "Password guessing game for problem-solving"},
    {"module_id": "READ", "description": "Reading exercise"},
    {"module_id": "SCAVENGERHUNT", "description": "Scavenger hunt game for playful learning"},
    {"module_id": "STORY", "description": "Story listening exercise"},
    {"module_id": "AUDMED", "description": "Audio meditation for relaxation"},
    {"module_id": "WHIMSY", "description": "Whimsical fun for the day"},
    {"module_id": "DM", "description": "Whimsical fun for the day"},
]

# Create QR codes
for module in modules:
    text = f"GO<launch:{module['module_id']}>"
    img = qrcode.make(text)
    img.save(f"launch_{module['module_id']}.png")

print("QR codes generated!")
