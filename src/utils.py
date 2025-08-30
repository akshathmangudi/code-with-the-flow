"""
This module provides utility functions for the Vibe Coder application,
including project name generation and network utilities.
"""
import re
import os
import random
import socket

ADJECTIVES = [
    "autumn", "hidden", "bitter", "misty", "silent", "empty", "dry", "dark",
    "summer", "icy", "delicate", "quiet", "white", "cool", "spring", "winter",
    "patient", "twilight", "dawn", "crimson", "wispy", "weathered", "blue",
    "billowing", "broken", "cold", "damp", "falling", "frosty", "green",
    "long", "late", "lingering", "bold", "little", "morning", "muddy", "old",
    "red", "rough", "still", "small", "sparkling", "throbbing", "shy",
    "wandering", "withered", "wild", "black", "young", "holy", "solitary",
    "fragrant", "aged", "snowy", "proud", "floral", "restless", "divine",
    "polished", "ancient", "purple", "lively", "nameless", "sexy"
]

NOUNS = [
    "waterfall", "river", "breeze", "moon", "rain", "wind", "sea", "morning",
    "snow", "lake", "sunset", "pine", "shadow", "leaf", "dawn", "glitter",
    "forest", "hill", "cloud", "meadow", "sun", "glade", "bird", "brook",
    "butterfly", "bush", "dew", "dust", "field", "fire", "flower", "firefly",
    "feather", "grass", "haze", "mountain", "night", "pond", "darkness",
    "snowflake", "silence", "sound", "sky", "shape", "surf", "thunder",
    "violet", "water", "wildflower", "wave", "water", "resonance", "sun",
    "wood", "dream", "cherry", "tree", "fog", "frost", "voice", "paper",
    "frog", "smoke", "star", "pumpkin", "falcon"
]

def generate_random_project_name() -> str:
    """
    Generates a random, memorable project name from a list of adjectives and nouns.
    
    Returns:
        A string representing the random project name.
    """
    adj = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    num = random.randint(1000, 9999)
    return f"{adj}-{noun}-{num}"

def get_unique_project_name(base_name: str, base_dir: str = ".") -> str:
    """
    Generates a unique project name by appending a number if the directory already exists.

    Args:
        base_name: The initial desired name for the project.
        base_dir: The directory where projects are stored.

    Returns:
        A unique project name.
    """
    from pathlib import Path
    
    project_name = base_name
    project_dir = Path(base_dir) / project_name
    counter = 2
    while project_dir.exists():
        project_name = f"{base_name}-{counter}"
        project_dir = Path(base_dir) / project_name
        counter += 1
    return project_name


def is_port_in_use(port: int) -> bool:
    """
    Checks if a TCP port is already in use on the local machine.

    Args:
        port: The port number to check.

    Returns:
        True if the port is in use, False otherwise.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


def sanitize_project_name(name: str) -> str:
    """
    Sanitizes a string to be a valid project/directory name.
    
    Args:
        name: The string to sanitize.
        
    Returns:
        The sanitized string.
    """
    name = name.lower()
    name = re.sub(r'[\s_]+', '-', name)
    name = re.sub(r'[^a-z0-9-]', '', name)
    name = name.strip('-')
    return name