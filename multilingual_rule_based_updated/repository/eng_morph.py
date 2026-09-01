import re

def count_syllables(word):
    word = word.lower()
    # Count vowel groups as syllables
    syllables = re.findall(r'[aeiouy]+', word)
    return len(syllables)
