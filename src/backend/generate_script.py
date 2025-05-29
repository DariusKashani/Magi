from dotenv import load_dotenv
import os
import re
import json
from dataclasses import dataclass
from typing import List

# ---------------------------
# Settings and Config
# ---------------------------
from config.settings import WORDS_PER_MINUTE, WORDS_PER_CONCEPT, SOPHISTICATION_DESCRIPTIONS
from config.paths import SCENE_EXAMPLES_PATH, SCRIPT_GEN_PROMPT_PATH
from config.llm import LLMClient

# ---------------------------
# Load Prompt Components
# ---------------------------
SCENE_EXAMPLES = json.loads(SCENE_EXAMPLES_PATH.read_text(encoding="utf-8"))
SCRIPT_GEN_PROMPT_TEMPLATE = SCRIPT_GEN_PROMPT_PATH.read_text(encoding="utf-8")

# ---------------------------
# LLM Client Setup
# ---------------------------
load_dotenv()
llm = LLMClient(model="claude-sonnet-4-20250514", temperature=0.7, max_tokens=8000)

# ---------------------------
# Data Models
# ---------------------------
@dataclass
class ConceptSegment:
    narration: str
    scene_description: str

@dataclass
class Script:
    topic: str
    duration_minutes: int
    sophistication_level: int
    concepts: List[ConceptSegment]

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({
                "topic": self.topic,
                "duration_minutes": self.duration_minutes,
                "sophistication_level": self.sophistication_level,
                "concepts": [
                    {
                        "narration": c.narration,
                        "scene_description": c.scene_description
                    } for c in self.concepts
                ]
            }, f, indent=2)

    @staticmethod
    def load(path: str) -> "Script":
        with open(path) as f:
            data = json.load(f)
        return Script(
            topic=data["topic"],
            duration_minutes=data["duration_minutes"],
            sophistication_level=data["sophistication_level"],
            concepts=[
                ConceptSegment(c["narration"], c["scene_description"])
                for c in data["concepts"]
            ]
        )

# ---------------------------
# Utility Functions
# ---------------------------
def extract_concepts(script: str) -> List[ConceptSegment]:
    pattern = r'\[NEW CONCEPT\](.*?)\[END CONCEPT\|\| Scene description:\s*(.*?)\](?=\n\[NEW CONCEPT\]|\Z)'
    matches = re.findall(pattern, script, flags=re.DOTALL)
    segments = [ConceptSegment(n.strip(), s.strip()) for n, s in matches]
    return segments


# ---------------------------
# Script Generation
# ---------------------------
def generate_script(topic: str, duration_minutes: int = 5, sophistication_level: int = 2) -> Script:
    
    if sophistication_level < 1 or sophistication_level > 3:
        sophistication_level = 2

    expected_words = duration_minutes * WORDS_PER_MINUTE
    concept_count = max(20, expected_words // WORDS_PER_CONCEPT)

    level_desc = SOPHISTICATION_DESCRIPTIONS.get(sophistication_level)
    scene_example = SCENE_EXAMPLES.get(str(sophistication_level))

    system_prompt = SCRIPT_GEN_PROMPT_TEMPLATE.format(
        topic=topic,
        level_desc=level_desc,
        duration_minutes=duration_minutes,
        expected_words=expected_words,
        concept_count=concept_count,
        scene_example=scene_example
    )

    user_prompt = (
        f"Create a detailed educational script about {topic} at a {level_desc} sophistication level. "
        f"The script should have exactly {concept_count} concepts, each with [NEW CONCEPT] and [END CONCEPT|| Scene description: ...] markers."
    )

    try:
        full_script = llm.chat(system_prompt, user_prompt)
        segments = extract_concepts(full_script)

        return Script(
            topic=topic,
            duration_minutes=duration_minutes,
            sophistication_level=sophistication_level,
            concepts=segments
        )

    except Exception as e:
        raise RuntimeError(f"Script generation failed: {str(e)}")

# ---------------------------
# CLI Entry Point
# ---------------------------
def main():
    topic = input("What educational question do you have? ")

    try:
        duration_minutes = int(input("Enter desired video length in minutes (max: 15): "))
        if not (2 <= duration_minutes <= 10):
            print("Using default duration of 5 minutes.")
            duration_minutes = 5
    except ValueError:
        print("Using default duration of 5 minutes.")
        duration_minutes = 5

    try:
        sophistication_level = int(input("Enter sophistication level (1=Beginner, 2=Intermediate, 3=Advanced): "))
        if not (1 <= sophistication_level <= 3):
            print("Using default level: 2 (Intermediate).")
            sophistication_level = 2
    except ValueError:
        print("Using default level: 2 (Intermediate).")
        sophistication_level = 2

    print(f"Generating script for '{topic}' ({duration_minutes} minutes, level {sophistication_level})...")
    script = generate_script(topic, duration_minutes, sophistication_level)

    print("\n--- NARRATIONS ---")
    for i, concept in enumerate(script.concepts, 1):
        print(f"\nNarration {i}:")
        print(concept.narration)

    print("\n\n--- SCENE DESCRIPTIONS ---")
    for i, concept in enumerate(script.concepts, 1):
        print(f"\nScene {i}:")
        print(concept.scene_description)

    print(f"\n\nGenerated {len(script.concepts)} concept segments with narrations and scene descriptions")

if __name__ == "__main__":
    main()