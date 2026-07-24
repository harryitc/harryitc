"""Static profile content.

EDIT THIS FILE to change what shows up on the profile README.
Everything here is hand-written; live numbers come from today.py.

Each entry in a section is (label, value). Set a value to None to hide the row.
"""

# Shown after the "@" in the header line, and used for all API lookups.
USER_NAME = "harryitc"

# Used to compute the "Uptime" row. Format: YYYY-MM-DD.
# Set to None to show account age (time since you joined GitHub) instead.
BIRTHDAY = "2000-01-01"

SYSTEM = [
    ("OS", "Windows 11, WSL2 Ubuntu 24.04, Android 15"),
    ("Uptime", None),  # filled in by today.py
    ("Host", "HUTECH University"),
    ("Kernel", "Fullstack Developer"),
    ("IDE", "VSCode 1.108, IntelliJ IDEA 2025.1"),
]

LANGUAGES = [
    ("Languages.Programming", "TypeScript, JavaScript, Java, Python"),
    ("Languages.Computer", "HTML, CSS, SQL, JSON, YAML"),
    ("Languages.Real", "Vietnamese, English"),
]

HOBBIES = [
    ("Hobbies.Software", "Open Source, Automation"),
    ("Hobbies.Hardware", "PC Building"),
]

CONTACT = [
    ("Email.Personal", "harryitc.dev@gmail.com"),
    ("LinkedIn", "harryitc"),
    ("GitHub", "harryitc"),
]

# Repos to leave out of the Lines of Code count, as "owner/name".
EXCLUDED_REPOS = set()
