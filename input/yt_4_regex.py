import re

# Extracting emails from text
text = "Contact us at support@example.com or sales@test.org"
pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'

emails = re.findall(pattern, text)
print(emails)
