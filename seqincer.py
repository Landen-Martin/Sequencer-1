#!/usr/bin/env python3
"""
Seqincer-1: Context-Aware Procedural Sentence Engine.

A deterministic-yet-varied, grammar-driven text generator. Not an AI:
every sentence is assembled from an explicit, hand-curated lexicon using
weighted structural templates, a repetition-avoiding memory stack, and a
lightweight coreference tracker (pronoun reuse, possessives, discourse
openers, and paragraph-level topic continuity).

Features
--------
* ~600-word curated lexicon across 16 grammatical categories
* 7 sentence templates with weighted, non-repeating selection
* Pronoun coreference ("The knight ... He ...") and possessive binding
* Discourse openers ("Suddenly,", "By nightfall,", "Beyond the ridge,")
* Prompt-aware completion (verbs, prepositions, determiners, adjectives,
  nouns, and linking verbs are all handled grammatically)
* Per-paragraph repetition suppression + sliding recency window
* Seeded RNG for reproducible output; typewriter streaming with jitter
* Pure standard library — no third-party dependencies

Usage
-----
    python seqincer.py                          # interactive REPL
    python seqincer.py "The old cartographer"   # one-shot completion
    python seqincer.py "The knight" -n 4 --seed 42 --no-stream
    python seqincer.py --check                  # validate lexicon + smoke test
"""

from __future__ import annotations

import argparse
import io
import logging
import random
import sys
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Sequence, Set, Tuple, TypedDict

LOG = logging.getLogger("Seqincer-1")

# ---------------------------------------------------------------------------
# Lexicon (hand-curated; no external data files required)
# ---------------------------------------------------------------------------

class NounEntry(TypedDict):
    word: str
    gender: str   # "m" | "f" | "n"
    proper: bool

# (word, gender, is_proper)
_ACTORS: Tuple[Tuple[str, str, bool], ...] = (
    ("alchemist", "f", False), ("apothecary", "m", False), ("archer", "f", False),
    ("architect", "n", False), ("artist", "f", False), ("bard", "m", False),
    ("blacksmith", "m", False), ("botanist", "f", False), ("cartographer", "m", False),
    ("courier", "m", False), ("elder", "m", False), ("farmer", "m", False),
    ("fisherman", "m", False), ("forager", "f", False), ("gardener", "f", False),
    ("guardian", "n", False), ("healer", "f", False), ("herbalist", "f", False),
    ("hunter", "m", False), ("innkeeper", "m", False), ("jeweler", "f", False),
    ("knight", "m", False), ("librarian", "f", False), ("mason", "m", False),
    ("merchant", "m", False), ("minstrel", "m", False), ("monk", "m", False),
    ("navigator", "n", False), ("oracle", "f", False), ("pilgrim", "m", False),
    ("ranger", "m", False), ("sailor", "m", False), ("scribe", "f", False),
    ("sculptor", "f", False), ("seer", "f", False), ("shepherd", "m", False),
    ("smuggler", "n", False), ("soldier", "n", False), ("stranger", "n", False),
    ("swordsmith", "m", False), ("tailor", "f", False), ("tinker", "n", False),
    ("traveler", "n", False), ("vagrant", "n", False), ("wandere", "n", False),
    ("watchman", "m", False), ("weaver", "f", False), ("woodcutter", "m", False),
    ("Arthur", "m", True), ("Bob", "m", True), ("Cedric", "m", True),
    ("Finn", "m", True), ("Roland", "m", True), ("Elena", "f", True),
    ("Greta", "f", True), ("Isolde", "f", True), ("Lyra", "f", True),
    ("Mira", "f", True),
)

_ANIMALS: Tuple[Tuple[str, str, bool], ...] = tuple(
    (w, "n", False) for w in (
        "adder", "badger", "bat", "bear", "beetle", "boar", "crow", "deer",
        "dog", "dove", "eagle", "falcon", "finch", "fox", "frog", "goat",
        "hare", "hawk", "heron", "hound", "jackdaw", "lizard", "moth", "otter",
        "owl", "ox", "panther", "rabbit", "raven", "robin", "serpent",
        "sparrow", "spider", "stag", "swallow", "toad", "trout", "weasel",
        "wolf", "wren",
    )
)

_LOCATIONS: Tuple[Tuple[str, str, bool], ...] = tuple(
    (w, "n", False) for w in (
        "abbey", "alcove", "archway", "atoll", "avenue", "bank", "barn",
        "basin", "bay", "beach", "bridge", "brook", "cabin", "canyon",
        "castle", "cavern", "chapel", "clearing", "cliff", "coast", "cottage",
        "courtyard", "cove", "creek", "dell", "dock", "dune", "estate",
        "field", "forge", "fountain", "garden", "gate", "glade", "gorge",
        "grove", "harbor", "hill", "hollow", "inn", "island", "jetty",
        "labyrinth", "lake", "marsh", "meadow", "mill", "moor", "mountain",
        "orchard", "outpost", "pass", "path", "pier", "plain", "plateau",
        "pond", "quarry", "ravine", "ridge", "river", "road", "ruin",
        "shrine", "shore", "stairway", "temple", "thicket", "tower", "trail",
        "valley", "vault", "village", "well", "wharf", "woodland",
    )
)

_OBJECTS: Tuple[Tuple[str, str, bool], ...] = tuple(
    (w, "n", False) for w in (
        "amulet", "anchor", "arrow", "axe", "banner", "barrel", "basket",
        "bell", "blade", "bottle", "chalice", "charm", "chest", "coin",
        "compass", "crown", "dagger", "drum", "feather", "flute", "gauntlet",
        "gem", "goblet", "grimoire", "hammer", "harp", "helm", "horn",
        "hourglass", "idol", "inkwell", "jar", "journal", "key", "lantern",
        "locket", "map", "mask", "medallion", "mirror", "necklace", "orb",
        "pendant", "prism", "quill", "relic", "ribbon", "ring", "rope",
        "saddle", "scroll", "shard", "shield", "sigil", "spectacles", "staff",
        "stone", "sword", "talisman", "torch", "totem", "vial", "wand",
    )
)

_ABSTRACT: Tuple[Tuple[str, str, bool], ...] = tuple(
    (w, "n", False) for w in (
        "clamor", "cry", "dirge", "dream", "echo", "glow", "hush", "hum",
        "lament", "melody", "memory", "murmur", "omen", "refrain", "rumor",
        "shadow", "shimmer", "sigh", "silence", "stillness", "thunder",
        "toll", "warning", "whisper",
    )
)

_AMBIENT: Tuple[Tuple[str, str, bool], ...] = tuple(
    (w, "n", False) for w in (
        "breeze", "cloud", "darkness", "fog", "haze", "mist", "moonlight",
        "rain", "snow", "starlight", "storm", "sunlight", "wind",
    )
)

_TIME: Tuple[Tuple[str, str, bool], ...] = tuple(
    (w, "n", False) for w in (
        "dawn", "daybreak", "dusk", "evening", "midnight", "morn", "morning",
        "nightfall", "noon", "sunrise", "sunset", "twilight",
    )
)


def _make_nouns(raw: Sequence[Tuple[str, str, bool]]) -> List[NounEntry]:
    return [{"word": w, "gender": g, "proper": p} for (w, g, p) in raw]


LEXICON: Dict[str, List] = {
    "ADJECTIVE": [
        "abandoned", "abundant", "aged", "alien", "ancient", "anguished", "arched",
        "arctic", "ashen", "austere", "azure", "barren", "battered", "billowing",
        "bleak", "blessed", "blinding", "boundless", "brazen", "breathless", "brittle",
        "broken", "burnished", "calm", "candlelit", "carved", "chiseled", "chilly",
        "cloaked", "cobalt", "cold", "crooked", "crimson", "cryptic", "curious",
        "damp", "dappled", "dazzling", "deep", "defiant", "delicate", "derelict",
        "desolate", "distant", "dreary", "dreaded", "dusty", "eager", "eerie",
        "elder", "elusive", "embossed", "endless", "ethereal", "faded", "faint",
        "feral", "ferocious", "feverish", "fitful", "flecked", "forgotten", "forlorn",
        "frail", "frosted", "frozen", "gilded", "gleaming", "glimmering", "gloomy",
        "glowing", "golden", "granite", "grave", "gray", "grizzled", "haggard",
        "hallowed", "hazy", "hidden", "hollow", "holy", "hushed", "idle",
        "immense", "indigo", "infinite", "inlaid", "iron", "ivory", "jagged",
        "jeweled", "joyless", "keen", "kindled", "lone", "lonely", "looming",
        "luminous", "majestic", "marbled", "meager", "misty", "moonlit", "mossy",
        "mournful", "muted", "narrow", "nimble", "northern", "oaken", "obscure",
        "old", "open", "pale", "parched", "patient", "peculiar", "porcelain",
        "primordial", "quiet", "radiant", "ragged", "ravenous", "ravaged", "remote",
        "restless", "reverent", "ruined", "rusted", "ruthless", "sacred", "scarred",
        "secluded", "shadowed", "shadowy", "shattered", "shimmering", "shrouded", "silent",
        "silver", "sinuous", "sleeping", "slender", "solemn", "somber", "sorrowful",
        "sparse", "spectral", "splintered", "starlit", "stern", "still", "stony",
        "stricken", "sunken", "sunless", "swift", "tall", "tarnished", "thunderous",
        "timeworn", "tranquil", "unbroken", "uncertain", "uncharted", "undisturbed", "unearthly",
        "unlit", "unseen", "vast", "veiled", "verdant", "violet", "waning",
        "watchful", "weathered", "whispering", "wild", "windswept", "withered", "wondrous",
        "wooden", "worn", "wretched", "yawning", "zealous",
    ],
    "ADVERB": [
        "abruptly", "aimlessly", "briskly", "calmly", "carefully", "cautiously",
        "closely", "coldly", "curiously", "deliberately", "desperately", "dreamily",
        "eagerly", "faintly", "fiercely", "gently", "gladly", "gradually", "grimly",
        "hastily", "hesitantly", "hurriedly", "lightly", "listlessly", "loudly",
        "narrowly", "patiently", "quickly", "quietly", "restlessly", "secretly",
        "slowly", "softly", "solemnly", "steadily", "sternly", "suddenly", "swiftly",
        "tenderly", "thoughtfully", "uneasily", "urgently", "vaguely", "warily",
        "wearily", "willingly",
    ],
    "NOUN:ACTOR": _make_nouns(_ACTORS),
    "NOUN:ANIMAL": _make_nouns(_ANIMALS),
    "NOUN:LOCATION": _make_nouns(_LOCATIONS),
    "NOUN:OBJECT": _make_nouns(_OBJECTS),
    "NOUN:ABSTRACT": _make_nouns(_ABSTRACT),
    "NOUN:AMBIENT": _make_nouns(_AMBIENT),
    "NOUN:TIME": _make_nouns(_TIME),
    "VERB:MOVE": [
        "advanced", "ambled", "bolted", "crept", "darted", "descended", "drifted",
        "escaped", "fled", "floated", "hurried", "journeyed", "limped", "marched",
        "meandered", "paced", "prowled", "rambled", "retreated", "roamed", "rushed",
        "sauntered", "scrambled", "slipped", "sprinted", "staggered", "stalked",
        "stepped", "strode", "strolled", "stumbled", "tiptoed", "traipsed",
        "traveled", "trekked", "trudged", "veered", "wandered", "wove",
    ],
    # Movement verbs that take a direct location object (no preposition).
    "VERB:MOVE_DIRECT": ["approached", "entered", "crossed", "reached",
                         "circled", "climbed", "followed"],
    "VERB:TRANSITIVE": [
        "acquired", "brandished", "carried", "claimed", "clutched", "collected",
        "concealed", "cradled", "discovered", "drew", "examined", "fetched",
        "found", "gathered", "grasped", "hid", "hoisted", "lifted", "lowered",
        "obtained", "opened", "pilfered", "pocketed", "pulled", "raised",
        "recovered", "retrieved", "revealed", "seized", "snatched", "studied",
        "took", "touched", "traced", "uncovered", "unfolded", "unearthed",
        "unwrapped", "wielded",
    ],
    "VERB:PERCEIVE": [
        "beheld", "detected", "glimpsed", "heard", "heeded", "noticed",
        "observed", "overheard", "regarded", "saw", "sensed", "spied",
        "spotted", "watched", "witnessed",
    ],
    "VERB:SPEECH": [
        "boasted", "cautioned", "complained", "dreamed", "joked", "murmured",
        "sang", "spoke", "warned", "whispered",
    ],
    "VERB:STATE": [
        "appeared", "became", "felt", "grew", "hung", "loomed", "looked",
        "remained", "rested", "sat", "seemed", "shone", "stayed", "towered",
        "waited",
    ],
    "VERB:AMBIENT": [
        "deepened", "faded", "fell", "gathered", "lifted", "lingered",
        "returned", "rose", "settled", "spread", "stirred", "thickened",
        "vanished",
    ],
    "PREPOSITION": [
        "above", "across", "against", "along", "among", "around", "atop",
        "before", "behind", "below", "beneath", "beside", "beyond", "down",
        "from", "into", "near", "onto", "outside", "over", "past", "through",
        "toward", "under", "upon", "within",
    ],
    "CONJUNCTION": ["and", "as", "before", "while"],
    "SENTENCE_OPENER": [
        "Suddenly,", "Just then,", "Moments later,", "Before long,",
        "Without warning,", "At last,", "In silence,", "Somewhere nearby,",
        "Far away,", "High above,", "Soon after,", "Once more,",
        "In the distance,", "All the while,", "By then,", "Little by little,",
        "As dawn broke,", "As dusk settled,", "As night fell,",
    ],
}

# ---------------------------------------------------------------------------
# Derived indexes (built once at import; no per-call scanning of the lexicon)
# ---------------------------------------------------------------------------

VERB_CATEGORIES = ("VERB:MOVE", "VERB:MOVE_DIRECT", "VERB:TRANSITIVE",
                   "VERB:PERCEIVE", "VERB:SPEECH", "VERB:STATE", "VERB:AMBIENT")

ALL_VERBS: Set[str] = set().union(*(set(LEXICON[c]) for c in VERB_CATEGORIES))
MOVE_ALL: List[str] = LEXICON["VERB:MOVE"] + LEXICON["VERB:MOVE_DIRECT"]
MOVE_DIRECT_SET: Set[str] = set(LEXICON["VERB:MOVE_DIRECT"])
PERCEIVE_SET: Set[str] = set(LEXICON["VERB:PERCEIVE"])
LINKING_SET: Set[str] = set(LEXICON["VERB:STATE"]) | {
    "was", "is", "were", "am", "are"}
DETERMINER_SET: Set[str] = {"the", "a", "an", "this", "that"}
ADJECTIVE_SET: Set[str] = set(LEXICON["ADJECTIVE"])
PREPOSITION_SET: Set[str] = set(LEXICON["PREPOSITION"])
CONJUNCTION_LIST: List[str] = LEXICON["CONJUNCTION"]
TIME_SET: Set[str] = {e["word"] for e in LEXICON["NOUN:TIME"]}

# word -> (entry, kind) for noun-based coreference from user prompts
NOUN_INDEX: Dict[str, Tuple[NounEntry, str]] = {}
_NOUN_KINDS = {
    "NOUN:ACTOR": "actor", "NOUN:ANIMAL": "animal",
    "NOUN:LOCATION": "location", "NOUN:OBJECT": "object",
    "NOUN:ABSTRACT": "abstract", "NOUN:AMBIENT": "ambient",
    "NOUN:TIME": "time",
}

for _cat, _kind in _NOUN_KINDS.items():
    for _entry in LEXICON[_cat]:
        NOUN_INDEX[_entry["word"].lower()] = (_entry, _kind)

PRONOUN: Dict[str, str] = {"m": "he", "f": "she", "n": "it"}
POSSESSIVE: Dict[str, str] = {"m": "his", "f": "her", "n": "its"}

TEMPLATES: List[str] = ["MOVEMENT", "TRANSITIVE", "PERCEPTION",
                        "DESCRIPTIVE", "AMBIENT", "SPEECH", "COMPOUND"]
TEMPLATE_WEIGHTS: List[int] = [26, 22, 16, 12, 10, 8, 6]

_KIND_BY_CATEGORY: Dict[str, str] = dict(_NOUN_KINDS)

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------
DET_THE_PROB = 0.70
DET_THIS_PROB = 0.08          # remainder goes to indefinite article
EXCLAMATION_PROB = 0.08
PRONOUN_REUSE_PROB = 0.55
POSSESSIVE_OBJECT_PROB = 0.25
POSSESSIVE_PLACE_PROB = 0.18
COMPOUND_PRONOUN_PROB = 0.60
PERCEPTION_TAIL_PROB = 0.40
AMBIENT_TAIL_PROB = 0.60
DESCRIPTIVE_TAIL_PROB = 0.45
TRANSITIVE_TAIL_PROB = 0.25
MEMORY_WINDOW = 12
MAX_SENTENCES = 10
MAX_TEMPERATURE = 2.0


def article(word: str) -> str:
    """Return the correct indefinite article for *word* ('a' or 'an')."""
    return "an" if word[:1].lower() in "aeiou" else "a"


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------

@dataclass
class GenConfig:
    """Runtime generation parameters."""
    sentences: int = 3
    speed: float = 0.03          # base seconds per token (0 = instant)
    stream: bool = True          # typewriter effect on/off
    temperature: float = 1.0     # scales adjective/openers/variety
    markers: bool = True         # emit <EOS>/<EOP> sentinels


@dataclass
class Entity:
    """A realized noun phrase, kept for coreference tracking."""
    word: str
    gender: str
    kind: str
    proper: bool


@dataclass
class SessionStats:
    paragraphs: int = 0
    sentences: int = 0
    words: int = 0
    templates: Counter = field(default_factory=Counter)
    started: float = field(default_factory=time.monotonic)

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def summary(self) -> str:
        uniq = len(self.templates)
        return (f"paragraphs={self.paragraphs}  sentences={self.sentences}  "
                f"words={self.words}  templates-used={uniq}/{len(TEMPLATES)}  "
                f"uptime={self.elapsed:.1f}s")


class MemoryTracker:
    """Sliding recency window + per-paragraph used-set for repetition control."""

    def __init__(self, window: int = MEMORY_WINDOW) -> None:
        self._window: Deque[str] = deque(maxlen=window)
        self.used: Set[str] = set()

    @staticmethod
    def _clean(word: str) -> str:
        return word.lower().strip(".,!?;:\"'")

    def record(self, word: str) -> None:
        clean = self._clean(word)
        if clean:
            self._window.append(clean)
            self.used.add(clean)

    def seen_recently(self, word: str) -> bool:
        return self._clean(word) in self._window

    def is_used(self, word: str) -> bool:
        return self._clean(word) in self.used

    def reset_paragraph(self) -> None:
        self.used.clear()   # keep the recency window across paragraphs


# ---------------------------------------------------------------------------
# Generation engine
# ---------------------------------------------------------------------------

class SeqincerEngine:
    """Rule-based sentence/paragraph generator with context tracking."""

    def __init__(self, config: Optional[GenConfig] = None,
                 seed: Optional[int] = None) -> None:
        self.cfg = config or GenConfig()
        self.rng = random.Random(seed)
        self.memory = MemoryTracker()
        self.stats = SessionStats()
        self._last_subject: Optional[Entity] = None
        self._last_template: Optional[str] = None

    # ----------------------------- output ---------------------------------

    def _write(self, text: str) -> None:
        sys.stdout.write(text)

    def stream_token(self, token: str, leading_space: bool = True,
                     capitalize: bool = False) -> None:
        """Emit one token with optional typewriter delay and capitalization."""
        if not token:
            return

        if capitalize:
            token = token[0].upper() + token[1:]

        self._write((" " if leading_space else "") + token)
        sys.stdout.flush()
        self.memory.record(token)
        if "<" not in token:
            self.stats.words += 1

        if self.cfg.stream and self.cfg.speed > 0:
            time.sleep(self.rng.uniform(self.cfg.speed * 0.5,
                                        self.cfg.speed * 1.5))

    # --------------------------- probability ------------------------------

    @property
    def _temp(self) -> float:
        return _clamp(self.cfg.temperature, 0.1, MAX_TEMPERATURE)

    def _adj_prob(self) -> float:
        return min(0.85, 0.45 * self._temp)

    def _adv_prob(self) -> float:
        return min(0.60, 0.35 * self._temp)

    def _opener_prob(self) -> float:
        return min(0.60, 0.22 * self._temp)

    # ----------------------------- selection ------------------------------

    def _pick_word(self, words: Sequence[str]) -> str:
        """Choose a word, preferring items unused this paragraph/recency."""
        fresh = [w for w in words
                 if not self.memory.is_used(w)
                 and not self.memory.seen_recently(w)]

        if fresh:
            return self.rng.choice(fresh)

        unused = [w for w in words if not self.memory.is_used(w)]
        return self.rng.choice(unused if unused else list(words))

    def _pick_template(self) -> str:
        pairs = [(t, w) for t, w in zip(TEMPLATES, TEMPLATE_WEIGHTS)
                 if t != self._last_template] or list(zip(TEMPLATES,
                                                          TEMPLATE_WEIGHTS))

        templates = [t for t, _ in pairs]
        weights = [w for _, w in pairs]
        return self.rng.choices(templates, weights=weights, k=1)[0]

    # --------------------------- phrase builders --------------------------

    def _noun_phrase(self, category: str, *, start: bool = False,
                     no_det: bool = False, no_adj: bool = False,
                     force_common: bool = False,
                     possessive: Optional[str] = None) -> Entity:
        """Emit a determiner (+adjective) + noun phrase; return the Entity."""
        entries = LEXICON[category]
        pool = [e for e in entries
                if (not force_common or not e["proper"])
                and not self.memory.is_used(e["word"])
                and not self.memory.seen_recently(e["word"])]

        if not pool:
            pool = [e for e in entries
                    if (not force_common or not e["proper"])
                    and not self.memory.is_used(e["word"])]

        if not pool:
            pool = [e for e in entries if not e["proper"]] or list(entries)

        entry = self.rng.choice(pool)
        word = entry["word"]

        if entry["proper"]:
            self.stream_token(word, capitalize=True)
            return Entity(word, entry["gender"],
                          _KIND_BY_CATEGORY[category], True)

        adjective = None
        if not no_adj and self.rng.random() < self._adj_prob():
            adjective = self._pick_word(LEXICON["ADJECTIVE"])

        determiner = None
        if not no_det:
            if possessive:
                determiner = POSSESSIVE.get(possessive)

            else:
                roll = self.rng.random()
                if roll < DET_THE_PROB:
                    determiner = "the"

                elif roll < DET_THE_PROB + (1.0 - DET_THE_PROB - DET_THIS_PROB):
                    determiner = article(adjective or word)

                else:
                    determiner = "this"

        if determiner:
            self.stream_token(determiner, capitalize=start)
            if adjective:
                self.stream_token(adjective)

            self.stream_token(word)

        else:
            self.stream_token(adjective or word, capitalize=start)
            if adjective:
                self.stream_token(word)

        return Entity(word, entry["gender"],
                      _KIND_BY_CATEGORY[category], False)

    def _maybe_adverb(self) -> None:
        if self.rng.random() < self._adv_prob():
            self.stream_token(self._pick_word(LEXICON["ADVERB"]))

    def _possessive_gender(self, subject: Optional[Entity],
                           prob: float) -> Optional[str]:
        if subject and subject.gender in ("m", "f") and self.rng.random() < prob:

            return subject.gender

        return None

    def _move_complement(self, subject: Optional[Entity]) -> None:
        verb = self.rng.choice(MOVE_ALL)
        self.stream_token(verb)
        if verb in MOVE_DIRECT_SET:
            self._noun_phrase("NOUN:LOCATION",
                              possessive=self._possessive_gender(
                                  subject, POSSESSIVE_PLACE_PROB))

        else:
            self.stream_token(self.rng.choice(LEXICON["PREPOSITION"]))
            self._noun_phrase("NOUN:LOCATION",
                              possessive=self._possessive_gender(
                                  subject, POSSESSIVE_PLACE_PROB))

    # --------------------------- coreference ------------------------------

    def _actor_or_pronoun(self, start: bool) -> Entity:
        """Reuse the tracked subject via pronoun, else introduce a new actor."""
        last = self._last_subject
        if (last and last.kind in ("actor", "animal")
                and self.rng.random() < PRONOUN_REUSE_PROB):
            self.stream_token(PRONOUN[last.gender], capitalize=start)
            return last

        entity = self._noun_phrase("NOUN:ACTOR", start=start)
        self._last_subject = entity
        return entity

    # ------------------------------ openers -------------------------------

    def _maybe_opener(self) -> bool:
        """Prepend a discourse/time/scene opener. Returns True if emitted."""
        if self.rng.random() >= self._opener_prob():
            return False

        variant = self.rng.random()
        if variant < 0.55:                                   # static phrase
            self.stream_token(self.rng.choice(LEXICON["SENTENCE_OPENER"]),
                              leading_space=False)

        elif variant < 0.80:                                 # "By nightfall,"
            self.stream_token(self.rng.choice(["By", "At", "Before"]),
                              leading_space=False, capitalize=True)
            self.stream_token(self._pick_word(
                [e["word"] for e in LEXICON["NOUN:TIME"]]))
            self.stream_token(",", leading_space=False)

        else:                                                # "Beyond the ridge,"
            self.stream_token(self.rng.choice(LEXICON["PREPOSITION"]),
                              leading_space=False, capitalize=True)
            self._noun_phrase("NOUN:LOCATION")
            self.stream_token(",", leading_space=False)

        return True

    # ---------------------------- templates -------------------------------

    def _render(self, template: str, start: bool) -> None:
        if template == "MOVEMENT":
            subject = self._actor_or_pronoun(start)
            self._maybe_adverb()
            self._move_complement(subject)

        elif template == "TRANSITIVE":
            subject = self._actor_or_pronoun(start)
            self._maybe_adverb()
            self.stream_token(self._pick_word(LEXICON["VERB:TRANSITIVE"]))
            self._noun_phrase("NOUN:OBJECT",
                              possessive=self._possessive_gender(
                                  subject, POSSESSIVE_OBJECT_PROB))

            if self.rng.random() < TRANSITIVE_TAIL_PROB:
                self.stream_token(self.rng.choice(LEXICON["PREPOSITION"]))
                self._noun_phrase("NOUN:LOCATION")

        elif template == "PERCEPTION":
            subject = self._actor_or_pronoun(start)
            self._maybe_adverb()
            self.stream_token(self._pick_word(LEXICON["VERB:PERCEIVE"]))
            self._noun_phrase(self.rng.choice(
                ["NOUN:ANIMAL", "NOUN:OBJECT", "NOUN:ABSTRACT"]))

            if self.rng.random() < PERCEPTION_TAIL_PROB:
                self.stream_token(self.rng.choice(LEXICON["PREPOSITION"]))
                self._noun_phrase("NOUN:LOCATION")

        elif template == "DESCRIPTIVE":
            if self._last_subject and self.rng.random() < 0.45:
                self.stream_token(PRONOUN[self._last_subject.gender],
                                  capitalize=start)

            else:
                self._last_subject = self._noun_phrase(
                    self.rng.choice(["NOUN:ACTOR", "NOUN:LOCATION"]),
                    start=start)

            self.stream_token(self._pick_word(LEXICON["VERB:STATE"]))
            self.stream_token(self._pick_word(LEXICON["ADJECTIVE"]))
            if self.rng.random() < DESCRIPTIVE_TAIL_PROB:
                self.stream_token(self.rng.choice(LEXICON["PREPOSITION"]))
                self._noun_phrase("NOUN:LOCATION")

        elif template == "AMBIENT":
            self._noun_phrase("NOUN:AMBIENT", start=start)
            self.stream_token(self._pick_word(LEXICON["VERB:AMBIENT"]))
            if self.rng.random() < AMBIENT_TAIL_PROB:
                self.stream_token(self.rng.choice(LEXICON["PREPOSITION"]))
                self._noun_phrase("NOUN:LOCATION")

        elif template == "SPEECH":
            self._actor_or_pronoun(start)
            self._maybe_adverb()
            self.stream_token(self._pick_word(LEXICON["VERB:SPEECH"]))
            self.stream_token(self.rng.choice(["of", "about", "of"]))
            self._noun_phrase(self.rng.choice(
                ["NOUN:OBJECT", "NOUN:ABSTRACT", "NOUN:LOCATION"]))

        elif template == "COMPOUND":
            subject = self._actor_or_pronoun(start)
            self._maybe_adverb()
            self._move_complement(subject)
            self.stream_token(",", leading_space=False)
            self.stream_token(self.rng.choice(CONJUNCTION_LIST))
            if subject.gender in ("m", "f") \
                    and self.rng.random() < COMPOUND_PRONOUN_PROB:

                second: Entity = subject
                self.stream_token(PRONOUN[subject.gender])
            else:
                second = self._noun_phrase("NOUN:ACTOR")
                self._last_subject = second

            self._maybe_adverb()
            verb = self.rng.choice(LEXICON["VERB:TRANSITIVE"]
                                   + LEXICON["VERB:PERCEIVE"])

            self.stream_token(verb)
            if verb in PERCEIVE_SET:
                self._noun_phrase(self.rng.choice(
                    ["NOUN:ANIMAL", "NOUN:OBJECT", "NOUN:ABSTRACT"]))

            else:
                self._noun_phrase("NOUN:OBJECT",
                                  possessive=self._possessive_gender(
                                      second, POSSESSIVE_OBJECT_PROB))

    # ----------------------------- sentences ------------------------------

    def _finish_sentence(self) -> None:
        punct = "!" if self.rng.random() < EXCLAMATION_PROB else "."
        tail = f"{punct} <EOS>" if self.cfg.markers else punct
        self.stream_token(tail, leading_space=False)

    def _emit_sentence(self, index: int) -> None:
        if index > 0:
            self._write("\n")

        template = self._pick_template()
        self._last_template = template
        start = True
        if index > 0 and template != "COMPOUND" and self._maybe_opener():
            start = False

        self._render(template, start)
        self._finish_sentence()
        self.stats.sentences += 1
        self.stats.templates[template] += 1
        LOG.debug("sentence %d template=%s", index + 1, template)

    # --------------------- prompt-aware continuation ----------------------

    def _continue_from_prompt(self, prompt: str) -> None:
        """Grammatically complete an arbitrary user prompt."""
        words = prompt.split()
        for w in words:                       # suppress echo of prompt words
            self.memory.record(w)

        last = words[-1].lower().strip(".,!?;:\"'") if words else ""
        prev = words[-2].lower().strip(".,!?;:\"'") if len(words) > 1 else ""

        def np_object() -> None:
            self._noun_phrase("NOUN:OBJECT")

        def np_location() -> None:
            self._noun_phrase("NOUN:LOCATION")

        if last in set(LEXICON["VERB:TRANSITIVE"]):
            np_object()

        elif last in PERCEIVE_SET:
            self._noun_phrase(self.rng.choice(
                ["NOUN:ANIMAL", "NOUN:OBJECT", "NOUN:ABSTRACT"]))

            if self.rng.random() < PERCEPTION_TAIL_PROB:
                self.stream_token(self.rng.choice(LEXICON["PREPOSITION"]))
                np_location()

        elif last in set(LEXICON["VERB:SPEECH"]):
            self.stream_token(self.rng.choice(["of", "about", "of"]))
            self._noun_phrase(self.rng.choice(
                ["NOUN:OBJECT", "NOUN:ABSTRACT", "NOUN:LOCATION"]))

        elif last in MOVE_DIRECT_SET:
            np_location()

        elif last in set(LEXICON["VERB:MOVE"]) or last in set(LEXICON["VERB:AMBIENT"]):
            self.stream_token(self.rng.choice(LEXICON["PREPOSITION"]))
            np_location()

        elif last in LINKING_SET:
            self.stream_token(self._pick_word(LEXICON["ADJECTIVE"]))

        elif last in PREPOSITION_SET:
            np_location()

        elif last in TIME_SET:
            self._render("DESCRIPTIVE", start=False)

        elif last in DETERMINER_SET:
            indefinite = last in ("a", "an")
            self._noun_phrase(
                self.rng.choice(["NOUN:ACTOR", "NOUN:OBJECT",
                                 "NOUN:LOCATION", "NOUN:ANIMAL"]),

                no_det=True,
                no_adj=(indefinite or prev in ADJECTIVE_SET),
                force_common=True)

        elif last in ADJECTIVE_SET:
            self._noun_phrase(self.rng.choice(
                ["NOUN:ACTOR", "NOUN:OBJECT", "NOUN:LOCATION",
                 "NOUN:ANIMAL"]),
                no_det=True, no_adj=True, force_common=True)

        else:
            # Treat prompt as a subject: optionally track it, then predicate.
            hit = NOUN_INDEX.get(last)
            if hit and hit[1] in ("actor", "animal", "location"):
                entry, kind = hit
                self._last_subject = Entity(entry["word"], entry["gender"],
                                            kind, entry["proper"])

            if hit:
                subject = self._last_subject
                self._maybe_adverb()
                if self.rng.random() < 0.5:
                    self.stream_token(self._pick_word(
                        LEXICON["VERB:TRANSITIVE"]))
                    self._noun_phrase("NOUN:OBJECT",
                                      possessive=self._possessive_gender(
                                          subject, POSSESSIVE_OBJECT_PROB))

                else:
                    self._move_complement(subject)

            else:
                self._maybe_adverb()
                self._move_complement(None)

        self._finish_sentence()
        self.stats.sentences += 1

    # ---------------------------- paragraphs ------------------------------

    def generate_paragraph(self, prompt: Optional[str] = None,
                           sentence_count: Optional[int] = None) -> None:
        """Generate one paragraph; first sentence may continue *prompt*."""
        n = _clamp(sentence_count or self.cfg.sentences, 1, MAX_SENTENCES)
        n = int(n)
        self.memory.reset_paragraph()
        self._last_subject = None
        self._last_template = None

        self._write("Output:")
        if prompt:
            self._write(f" {prompt}")
            sys.stdout.flush()
            self._continue_from_prompt(prompt)
        else:

            self._emit_sentence(0)

        for i in range(1, n):
            self._emit_sentence(i)

        self._write("\n<EOP>\n" if self.cfg.markers else "\n")
        sys.stdout.flush()
        self.stats.paragraphs += 1


# ---------------------------------------------------------------------------
# Validation / self-test
# ---------------------------------------------------------------------------

def validate_lexicon() -> List[str]:
    """Static checks: duplicates, empty categories, malformed entries."""
    problems: List[str] = []
    for category, items in LEXICON.items():
        if not items:
            problems.append(f"empty category: {category}")
            continue

        if category.startswith("NOUN:"):
            seen: Set[str] = set()
            for entry in items:  # type: ignore[union-attr]
                w = entry["word"].lower()
                if w in seen:
                    problems.append(f"duplicate '{w}' in {category}")

                seen.add(w)
                if entry["gender"] not in PRONOUN:
                    problems.append(f"bad gender '{entry['gender']}' "
                                    f"for '{w}' in {category}")

        else:
            seen = set()
            for w in items:  # type: ignore[union-attr]
                if w in seen:
                    problems.append(f"duplicate '{w}' in {category}")

                seen.add(w)

    return problems


def run_self_check() -> int:
    """Validate the lexicon and run a deterministic smoke test."""
    problems = validate_lexicon()
    smoke_ok = False
    try:
        engine = SeqincerEngine(GenConfig(speed=0.0, stream=False), seed=1234)
        buffer = io.StringIO()
        stdout = sys.stdout
        sys.stdout = buffer
        try:
            for _ in range(5):
                engine.generate_paragraph("The traveler")

        finally:
            sys.stdout = stdout

        smoke_ok = "<EOP>" in buffer.getvalue()
        if not smoke_ok:
            problems.append("smoke test: missing <EOP> sentinel")

    except Exception as exc:  # noqa: BLE001 — report any failure cleanly

        problems.append(f"smoke test raised: {exc!r}")

    if problems:
        print(f"SELF-CHECK FAILED ({len(problems)} issue(s)):")
        for p in problems:
            print(f"  - {p}")

        return 1

    print(f"SELF-CHECK PASSED — {sum(len(v) for v in LEXICON.values())} "
          f"lexical items across {len(LEXICON)} categories; "
          "smoke test OK.")

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="seqincer",
        description=f"Seqincer-1: rule-based procedural "
                    "sentence engine (stdlib only).")

    parser.add_argument("prompt", nargs="*", metavar="WORDS",
                        help="optional prompt to complete (else interactive)")

    parser.add_argument("-n", "--sentences", type=int, default=3,
                        help=f"sentence count 1-{MAX_SENTENCES} (default 3)")

    parser.add_argument("-c", "--count", type=int, default=1,
                        help="paragraphs to generate in one-shot mode")

    parser.add_argument("--seed", type=int, default=None,
                        help="RNG seed for reproducible output")

    parser.add_argument("--speed", type=float, default=0.03,
                        help="base streaming delay in seconds (default 0.03)")

    parser.add_argument("--no-stream", action="store_true",
                        help="print instantly instead of typewriter mode")

    parser.add_argument("-t", "--temperature", type=float, default=1.0,
                        help="variety knob 0.1-2.0 (default 1.0)")

    parser.add_argument("--clean", action="store_true",
                        help="omit <EOS>/<EOP> sentinels")

    parser.add_argument("--stats", action="store_true",
                        help="print session statistics on exit")

    parser.add_argument("--check", action="store_true",
                        help="validate lexicon and run smoke test, then exit")

    parser.add_argument("-v", "--verbose", action="store_true",
                        help="debug logging to stderr")

    parser.add_argument("--version", action="version",
                        version=f"Seqincer-1")
    return parser


HELP_TEXT = """commands:
  /help              show this help
  /stats             show session statistics
  /seed <int>        reseed the RNG (reproducible runs)
  /sentences <int>   sentences per paragraph (1-10)
  /temp <float>      variety knob 0.1-2.0
  /exit              quit (also: exit, quit, Ctrl-D, Ctrl-C)"""


def repl(engine: SeqincerEngine) -> None:
    """Interactive read-eval loop."""
    print("Welcome to Seqincer-1!")
    print("/help for commands.\n")
    while True:
        try:
            line = input(">>> ").strip()

        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break

        if not line:
            continue

        low = line.lower()
        if low in ("exit", "quit", "/exit", "/quit"):
            break

        if low in ("/help", "help"):
            print(HELP_TEXT)
            continue

        if low == "/stats":
            print(engine.stats.summary())
            continue

        try:
            if line.startswith("/seed"):
                engine.rng = random.Random(int(line.split()[1]))
                print(f"seed set: {line.split()[1]}")
                continue

            if line.startswith("/sentences"):
                engine.cfg.sentences = int(_clamp(
                    int(line.split()[1]), 1, MAX_SENTENCES))
                print(f"sentences per paragraph: {engine.cfg.sentences}")
                continue

            if line.startswith("/temp"):
                engine.cfg.temperature = _clamp(
                    float(line.split()[1]), 0.1, MAX_TEMPERATURE)
                print(f"temperature: {engine.cfg.temperature}")
                continue

        except (IndexError, ValueError):
            print("usage: /seed <int> | /sentences <int> | /temp <float>")
            continue

        try:
            engine.generate_paragraph(line)
            print()

        except Exception as exc:  # noqa: BLE001 — keep the REPL alive
            LOG.exception("generation failed")
            print(f"[error] {exc}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s",
                        stream=sys.stderr)

    if args.check:
        return run_self_check()

    config = GenConfig(
        sentences=int(_clamp(args.sentences, 1, MAX_SENTENCES)),
        speed=0.0 if args.no_stream else max(0.0, args.speed),
        stream=not args.no_stream,
        temperature=_clamp(args.temperature, 0.1, MAX_TEMPERATURE),
        markers=not args.clean,
    )

    engine = SeqincerEngine(config, seed=args.seed)
    if args.prompt:
        prompt = " ".join(args.prompt)
        try:
            for _ in range(max(1, args.count)):
                engine.generate_paragraph(prompt)
                if args.count > 1:
                    print()

        except (KeyboardInterrupt, EOFError):
            print()

        if args.stats:
            print(engine.stats.summary(), file=sys.stderr)

        return 0

    repl(engine)
    if args.stats:
        print(engine.stats.summary(), file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())