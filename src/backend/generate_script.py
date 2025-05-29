from dotenv import load_dotenv
import os
import re
import yaml
from dataclasses import dataclass
from typing import List

# ---------------------------
# Settings and Config
# ---------------------------
from config.settings import WORDS_PER_MINUTE, SOPHISTICATION_DESCRIPTIONS
from config.paths import SCENE_EXAMPLES_PATH, SCRIPT_GEN_PROMPT_PATH
from config.llm import LLMClient

# ---------------------------
# Load Prompt Components
# ---------------------------
SCENE_EXAMPLES = yaml.safe_load(SCENE_EXAMPLES_PATH.read_text(encoding="utf-8"))
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
# ---------------------------
# Utility Functions
# ---------------------------
def extract_concepts(script: str) -> List[ConceptSegment]:
    # More flexible regex pattern to match the actual LLM output
    pattern = r'\[NEW CONCEPT\]\s*(.*?)\s*\[END CONCEPT\|\| Scene description:\s*(.*?)\]\](?=\s*\[NEW CONCEPT\]|\s*$)'
    matches = re.findall(pattern, script, flags=re.DOTALL)
    
    print(f"🔍 DEBUG: Regex found {len(matches)} matches")
    
    segments = [ConceptSegment(n.strip(), s.strip()) for n, s in matches]
    return segments

# ---------------------------
# Script Generation
# ---------------------------
def generate_script(topic: str, duration_minutes: int = 5, sophistication_level: int = 2) -> Script:
    
    if sophistication_level < 1 or sophistication_level > 3:
        sophistication_level = 2

    expected_words = duration_minutes * WORDS_PER_MINUTE
    
    # Calculate reasonable scene count (aim for 2-3 minutes per scene)
    scene_count = max(3, min(8, duration_minutes // 2))
    words_per_scene = expected_words // scene_count

    level_desc = SOPHISTICATION_DESCRIPTIONS.get(sophistication_level)
    scene_example = SCENE_EXAMPLES.get(str(sophistication_level))

    system_prompt = SCRIPT_GEN_PROMPT_TEMPLATE.format(
        topic=topic,
        level_desc=level_desc,
        duration_minutes=duration_minutes,
        expected_words=expected_words,
        scene_count=scene_count,
        words_per_scene=words_per_scene,  # ADD THIS LINE
        scene_example=scene_example
    )

    user_prompt = (
        f"Create a detailed educational script about {topic} at a {level_desc} sophistication level. "
        f"The script should have exactly {scene_count} scenes, each approximately {words_per_scene} words. "
        f"Target total length: {expected_words} words ({duration_minutes} minutes when spoken). "
        f"Use [NEW CONCEPT] and [END CONCEPT|| Scene description: ...] markers for each scene."
    )

    try:
        full_script = llm.chat(system_prompt, user_prompt)
        
        # Debug output to track what's happening
        print(f"🔍 DEBUG: Raw script length: {len(full_script)} characters")
        print(f"🔍 DEBUG: Requested {scene_count} scenes with ~{words_per_scene} words each")
        print(f"🔍 DEBUG: Target: {expected_words} words = {duration_minutes} minutes")
        
        segments = extract_concepts(full_script)
        print(f"🔍 DEBUG: Extracted {len(segments)} segments")
        
        if segments:
            total_words = sum(len(seg.narration.split()) for seg in segments)
            estimated_duration = total_words / WORDS_PER_MINUTE
            print(f"🔍 DEBUG: Actual: {total_words} words = {estimated_duration:.1f} minutes")
            
            # Show word count per segment
            for i, seg in enumerate(segments, 1):
                word_count = len(seg.narration.split())
                print(f"  Scene {i}: {word_count} words")
        else:
            print("🔍 DEBUG: No segments extracted - check regex pattern!")
            print(f"🔍 DEBUG: Raw script preview:\n{full_script[:500]}...")

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