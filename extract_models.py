import re

input_file = r"C:\Users\Cila\Desktop\odysseus-main\core\database.py"
output_file = r"C:\Users\Cila\Desktop\amunty\backend\amunty\models\odysseus_models.py"

with open(input_file, "r", encoding="utf-8") as f:
    content = f.read()

models_to_extract = [
    "TimestampMixin",
    "Document",
    "DocumentVersion",
    "CrewMember",
    "ScheduledTask",
    "TaskRun",
    "CalendarCal",
    "CalendarEvent"
]

header = """\"\"\"Odysseus models ported to Amunty.\"\"\"

from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime, Integer, ForeignKey, JSON, Index, func, text
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declared_attr

from amunty.models.base import Base

"""

extracted = header

for model in models_to_extract:
    # Match the class definition and its body until the next class definition or end of file
    pattern = rf"class {model}.*?(?=\nclass |\Z)"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        class_body = match.group(0)
        # Fix foreign keys: replace "sessions.id" with "conversations.id"
        class_body = class_body.replace('"sessions.id"', '"conversations.id"')
        # Replace relationship backrefs to 'Session' with 'Conversation'
        class_body = class_body.replace('relationship("Session"', 'relationship("Conversation"')
        extracted += class_body + "\n\n"
    else:
        print(f"Model {model} not found.")

with open(output_file, "w", encoding="utf-8") as f:
    f.write(extracted)

print("Models extracted successfully.")
