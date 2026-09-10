# Seqincer-1

A lightweight, zero-dependency text engine that generates coherent, grammatically structured English sentences and paragraphs using weighted templates and a curated lexicon. Includes typewriter-style output streaming, context tracking to prevent repetition, and prompt completion logic.

> **Note:** This is a deterministic rule- and template-based generator, not a neural network or large language model.

---

## Table of Contents

* [Features](https://www.google.com/search?q=%23features)
* [Quick Start](https://www.google.com/search?q=%23quick-start)
* [Requirements](https://www.google.com/search?q=%23requirements)
* [Usage](https://www.google.com/search?q=%23usage)
* [Interactive REPL](https://www.google.com/search?q=%23interactive-repl)
* [One-Shot Mode](https://www.google.com/search?q=%23one-shot-mode)
* [REPL Commands](https://www.google.com/search?q=%23repl-commands)
* [CLI Reference](https://www.google.com/search?q=%23cli-reference)


* [Sample Output](https://www.google.com/search?q=%23sample-output)
* [How It Works](https://www.google.com/search?q=%23how-it-works)
* [Sentence Templates](https://www.google.com/search?q=%23sentence-templates)
* [Context & Memory](https://www.google.com/search?q=%23context--memory)


* [The Lexicon](https://www.google.com/search?q=%23the-lexicon)
* [Configuration](https://www.google.com/search?q=%23configuration)
* [Validation & Self-Check](https://www.google.com/search?q=%23validation--self-check)
* [Deployment](https://www.google.com/search?q=%23deployment)
* [Extending the Lexicon](https://www.google.com/search?q=%23extending-the-lexicon)
* [Project Structure](https://www.google.com/search?q=%23project-structure)

---

## Features

| Feature | Description |
| --- | --- |
| **600+ Curated Words** | 19 grammatical categories: adjectives, adverbs, 7 noun classes, 7 verb classes, prepositions, conjunctions, and discourse openers. |
| **7 Sentence Templates** | Weighted selection with immediate-repeat suppression to vary structure. |
| **Coreference Tracking** | Pronoun reuse (*The knight ... He ...*) and possessive binding (*his lantern*, *her grimoire*). |
| **Discourse Openers** | Time and scene-setting transition phrases (*Suddenly,*, *By nightfall,*, *Beyond the ridge,*). |
| **Prompt Completion** | Continuations based on prompt tokens (verbs, prepositions, determiners, adjectives, linking verbs, nouns). |
| **Repetition Suppression** | Per-paragraph used-word tracking paired with a sliding 12-token recency window. |
| **Seeded Reproducibility** | Pass `--seed` via CLI or `/seed` in REPL for exact byte-for-byte output reproduction. |
| **Typewriter Streaming** | Configurable per-token delay with timing jitter; disable via `--no-stream`. |
| **Variety Knob** | Temperature parameter (`0.1`–`2.0`) controlling modifier and transition frequencies. |
| **Self-Validation** | Built-in `--check` flag tests lexicon integrity and execution consistency. |
| **Zero Dependencies** | Built exclusively with the Python standard library. |

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/Landen-Martin/seqincer-1.git
cd seqincer-1

# Validate installation
python seqincer.py --check

# Run a quick single completion
python seqincer.py "The old cartographer" -n 4 --seed 42 --no-stream

# Launch interactive REPL
python seqincer.py

```

---

## Requirements

* **Python 3.8+** (Standard library only; no external package dependencies required)

---

## Usage

### Interactive REPL

Run the script without positional arguments to enter interactive mode:

```bash
python seqincer.py

```

```text
Welcome to Seqincer-1!
Type /help for available commands.

>>> The knight
Output: The knight approached the stern well. <EOS>
He willingly obtained the narrow gauntlet. <EOS>
Elena regarded the thunder outside the basin! <EOS>
<EOP>

```

### One-Shot Mode

Pass a prompt directly as CLI positional arguments:

```bash
# Standard generation
python seqincer.py "The old cartographer"

# Custom length and reproducible seed
python seqincer.py "A raven" -n 4 --seed 42 --no-stream

# Multi-paragraph production without output sentinels
python seqincer.py "The storm" -c 5 --clean

```

### REPL Commands

| Command | Action |
| --- | --- |
| `/help` | Print command reference |
| `/stats` | View session metrics (paragraphs, sentences, words, templates used, uptime) |
| `/seed <int>` | Set the RNG seed |
| `/sentences <int>` | Set sentences per paragraph (1–10) |
| `/temp <float>` | Adjust variety knob (`0.1`–`2.0`) |
| `/exit` | Exit the REPL (or use `exit`, `quit`, `Ctrl-D`, `Ctrl-C`) |

### CLI Reference

```text
usage: seqincer [-h] [-n SENTENCES] [-c COUNT] [--seed SEED] [--speed SPEED]
                [--no-stream] [-t TEMPERATURE] [--clean] [--stats]
                [--check] [-v] [--version] [WORDS ...]

```

| Flag | Default | Description |
| --- | --- | --- |
| `WORDS` | *(none)* | Initial prompt text. If omitted, starts REPL mode. |
| `-n, --sentences` | `3` | Number of sentences per paragraph (1–10). |
| `-c, --count` | `1` | Number of paragraphs to generate in one-shot mode. |
| `--seed <int>` | *random* | Seed integer for reproducible runs. |
| `--speed <float>` | `0.03` | Delay per token in seconds for streaming output. |
| `--no-stream` | `False` | Print output instantly instead of streaming. |
| `-t, --temperature` | `1.0` | Variety scaling factor (0.1–2.0). |
| `--clean` | `False` | Suppress `<EOS>` and `<EOP>` tokens. |
| `--stats` | `False` | Output execution statistics to `stderr` on exit. |
| `--check` | `False` | Run self-tests and exit immediately. |
| `-v, --verbose` | `False` | Output debug logging to `stderr`. |
| `--version` | — | Display version information and exit. |

---

## Sample Output

```text
>>> The wanderer
Output: The weary wanderer trudged across the desolate moor.
She carried a tarnished lantern toward the derelict abbey.
By nightfall, the silence deepened beneath a starlit sky.
<EOP>

>>> The storm
Output: The storm gathered above the forgotten watchtower.
Lightning splintered the ancient oak beside the flooded creek.
Moments later, a drenched falcon sheltered within the hollow ruin.
<EOP>

```

---

## How It Works

### Sentence Templates

Sentences are formed using weighted probability templates. The engine prevents consecutive duplicate templates to ensure structural variety.

| Template | Weight | Example Output |
| --- | --- | --- |
| `MOVEMENT` | 26 | *The ranger crept beneath the yawning archway.* |
| `TRANSITIVE` | 22 | *Elena retrieved a jeweled medallion from the vault.* |
| `PERCEPTION` | 16 | *The hermit overheard a faint melody near the fountain.* |
| `DESCRIPTIVE` | 12 | *The moonlit tower loomed silent above the ridge.* |
| `AMBIENT` | 10 | *A cold mist settled over the sleeping village.* |
| `SPEECH` | 8 | *The oracle murmured of an unearthly omen.* |
| `COMPOUND` | 6 | *Finn strode into the glade, and he found a silver key.* |

### Context & Memory

The system maintains context using three main mechanics:

1. **`MemoryTracker`**:
* **Per-paragraph used set:** Words selected in the current paragraph are deprioritized until `<EOP>`.
* **Sliding recency window:** Tracks the last 12 tokens to prevent local phrase duplication across sentence boundaries.


2. **Coreference Resolution**:
* Tracks active animate entities (`Entity` class with word, gender, and grammatical features).
* Dynamically substitutes subject pronouns (*he*, *she*, *it*) and possessive modifiers (*his*, *her*, *its*) based on prior subjects.


3. **Prompt Classification**:
* Analyzes the final token of custom user input to choose a grammatically appropriate continuation structure:



| Prompt Ending | Continuation Strategy |
| --- | --- |
| Transitive verb | Direct object noun phrase |
| Perception verb | Perceived subject + prepositional modifier |
| Speech verb | Prepositional phrase (*of* / *about* + abstract target) |
| Direct-object movement verb (*entered*, *crossed*) | Target location |
| Prepositional movement verb (*walked*, *wandered*) | Preposition + location |
| Linking verb (*was*, *seemed*) | Adjective complement |
| Preposition | Target noun phrase |
| Time noun (*dusk*, *midnight*) | Descriptive clause |
| Determiner (*a*, *an*, *the*) | Common noun (with indefinite article handling) |
| Adjective | Common noun |
| Known noun | Evaluates entity state, then adds predicate |

---

## The Lexicon

The vocabulary is defined inline as a structured Python dictionary for easy auditing and zero-dependency distribution.

| Category | Count | Sample Items |
| --- | --- | --- |
| `ADJECTIVE` | ~168 | *ancient, gilded, sunless, timeworn, verdant* |
| `ADVERB` | ~46 | *cautiously, dreamily, warily, swiftly* |
| `NOUN:ACTOR` | ~59 | *alchemist, cartographer, seer, Roland, Isolde* |
| `NOUN:ANIMAL` | ~40 | *falcon, stag, wren, panther* |
| `NOUN:LOCATION` | ~75 | *abbey, labyrinth, ravine, wharf* |
| `NOUN:OBJECT` | ~63 | *grimoire, sextant, amulet, sigil, hourglass* |
| `NOUN:ABSTRACT` | ~24 | *echo, omen, stillness, lament* |
| `NOUN:AMBIENT` | ~13 | *mist, starlight, storm, breeze* |
| `NOUN:TIME` | ~12 | *dusk, nightfall, twilight, daybreak* |
| `VERB:MOVE` | ~39 | *trudged, prowled, meandered, staggered* |
| `VERB:MOVE_DIRECT` | ~7 | *entered, crossed, approached, climbed* |
| `VERB:TRANSITIVE` | ~40 | *unearthed, brandished, pocketed, retrieved* |
| `VERB:PERCEIVE` | ~15 | *glimpsed, overheard, beheld, sensed* |
| `VERB:SPEECH` | ~10 | *murmured, warned, boasted, sang* |
| `VERB:STATE` | ~15 | *loomed, shimmered, seemed, towered, waited* |
| `VERB:AMBIENT` | ~13 | *thickened, lifted, lingered, vanished* |
| `PREPOSITION` | ~26 | *beneath, beyond, atop, within* |
| `CONJUNCTION` | ~4 | *and, as, before, while* |
| `SENTENCE_OPENER` | ~19 | *Suddenly,, By nightfall,, In the distance,* |

*Nouns include metadata for gender agreement (`m`/`f`/`n`) and proper noun flags to suppress default article generation.*

---

## Configuration

### Embedded Engine Integration (`GenConfig`)

```python
from seqincer import GenConfig, SeqincerEngine

# Initialize engine instance programmatically
config = GenConfig(
    sentences=4,
    speed=0.0,
    stream=False,
    temperature=1.4,
)

engine = SeqincerEngine(config=config, seed=1234)

# Generate text output
engine.generate_paragraph("The lighthouse keeper")

```

### Module Constants

Adjustable global defaults located at the top of `seqincer.py`:

```python
DET_THE_PROB = 0.70            # Chance of selecting 'the' vs 'a/an/this'
EXCLAMATION_PROB = 0.08        # Probability of sentence ending in '!'
PRONOUN_REUSE_PROB = 0.55      # Chance next sentence reuses subject pronoun
POSSESSIVE_OBJECT_PROB = 0.25  # Probability of using possessive for objects
POSSESSIVE_PLACE_PROB = 0.18   # Probability of using possessive for locations
MEMORY_WINDOW = 12             # Sliding window size for recency suppression
MAX_SENTENCES = 10             # Sentence generation upper bound

```

---

## Validation & Self-Check

Run the internal validation suite to verify word entries, tuple metadata, and deterministic output consistency:

```bash
python seqincer.py --check

```

Outputs verification confirmation upon passing:

```text
SELF-CHECK PASSED - 688 lexical items across 19 categories; smoke test OK.

```

---

## Deployment

### Command Line Execution

```bash
python seqincer.py --no-stream --clean "The midnight train" -n 5

```

### Python Library Usage

```python
import io
import contextlib
from seqincer import GenConfig, SeqincerEngine

engine = SeqincerEngine(GenConfig(speed=0, stream=False), seed=99)

buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    engine.generate_paragraph("The astronomer", sentence_count=4)

output_text = buffer.getvalue()

```

---

## Extending the Lexicon

1. Open `seqincer.py` in your text editor.
2. Locate the lexicon dictionary definitions.
3. Append new terms to the appropriate collection:
* For regular terms, add simple string entries.
* For noun classes, provide `(word, gender, proper_flag)` tuples (e.g., `("merlin", "m", True)`).


4. Run validation to test formatting:
```bash
python seqincer.py --check

```



*Note: Custom verbs should be supplied in simple past tense to match the engine's built-in template patterns.*

---

## Project Structure

```text
seqincer-1/
├── seqincer.py    # Complete application (engine, lexicon, CLI, REPL)
├── README.md      # Project documentation
└── LICENSE        # AGPL-3.0 License

```