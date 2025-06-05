from dotenv import load_dotenv
import os
import re
import yaml
from dataclasses import dataclass
from typing import List
import json
# ---------------------------
# Settings and Config
# ---------------------------
from config.settings import WORDS_PER_MINUTE
from config.paths import SCENE_EXAMPLES_PATH, SCRIPT_GEN_PROMPT_PATH
from config.llm import LLMClient

# ---------------------------
# New Problem-Solving Specific Settings
# ---------------------------
DETAIL_LEVEL_DESCRIPTIONS = {
    1: "Basic level - show main steps only with minimal explanation",
    2: "Standard level - show all steps with brief explanations", 
    3: "Detailed level - show all steps with full reasoning and alternative approaches"
}

# ---------------------------
# Load Prompt Components  
# ---------------------------
SCENE_EXAMPLES = yaml.safe_load(SCENE_EXAMPLES_PATH.read_text(encoding="utf-8"))

# New problem-solving prompt template
PROBLEM_SOLVING_PROMPT_TEMPLATE = """
You are an expert mathematics tutor creating step-by-step problem-solving videos. Generate a structured solution script for the problem: {problem} at a {detail_level_desc} that would be about {duration_minutes} minutes long when read aloud (approximately {expected_words} words total).

### Problem-Solving Rules:
1. Divide the solution into exactly {step_count} solution steps of approximately {words_per_step} words each.
2. Each step should represent one logical solution step (e.g., "subtract 5 from both sides").
3. Mark the beginning of each step with [NEW STEP].
4. End each step with [END STEP|| Scene description: ...] using the structure below.
5. Mathematical expressions should be written in words (e.g., "x squared" instead of "x^2").
6. Always show your work and explain the reasoning for each step.
7. Include verification/checking at the end when appropriate.

### Detail Levels:
- **Basic (1)**: Show main steps only, minimal explanation
- **Standard (2)**: Show all steps with brief explanations  
- **Detailed (3)**: Show all steps with full reasoning and alternative approaches

### Scene Description Format:
Each scene should show the mathematical work being done:
- Problem setup or current equation state
- Highlight the operation being performed
- Show the result after the operation
- Duration estimate (e.g., [duration: 12s])

Example for "Solve: 2x + 5 = 13":

[NEW STEP]
Let's start by writing down our equation clearly. We have two x plus five equals thirteen. Our goal is to isolate x on one side of the equation. We can do this by performing the same operation on both sides to maintain equality.

[END STEP|| Scene description: 
Static state 1: Show the equation "2x + 5 = 13" centered on screen [duration: 3s]
Animation 1: Highlight the goal "Solve for x" appearing below the equation [duration: 2s]  
Static state 2: Display "Strategy: Isolate x by undoing operations" [duration: 4s]
]

Generate a complete solution with {step_count} steps, each approximately {words_per_step} words.
"""

# ---------------------------
# LLM Client Setup
# ---------------------------
load_dotenv()
llm = LLMClient(model="claude-sonnet-4-20250514", temperature=0.7, max_tokens=8000)

# ---------------------------
# Data Models (Updated)
# ---------------------------
@dataclass
class SolutionStep:
    narration: str
    scene_description: str

@dataclass
class ProblemSolutionScript:
    problem: str
    duration_minutes: int
    detail_level: int
    steps: List[SolutionStep]

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({
                "problem": self.problem,
                "duration_minutes": self.duration_minutes,
                "detail_level": self.detail_level,
                "steps": [
                    {
                        "narration": s.narration,
                        "scene_description": s.scene_description
                    } for s in self.steps
                ]
            }, f, indent=2)

    @staticmethod
    def load(path: str) -> "ProblemSolutionScript":
        with open(path) as f:
            data = json.load(f)
        return ProblemSolutionScript(
            problem=data["problem"],
            duration_minutes=data["duration_minutes"],
            detail_level=data["detail_level"],
            steps=[
                SolutionStep(s["narration"], s["scene_description"])
                for s in data["steps"]
            ]
        )

# ---------------------------
# Updated Parsing Functions
# ---------------------------
def extract_solution_steps(script: str) -> List[SolutionStep]:
    """
    Extract solution steps from LLM output
    """
    print(f"🔍 DEBUG: Analyzing solution script structure...")
    print(f"🔍 DEBUG: Script length: {len(script)} characters")
    print(f"🔍 DEBUG: First 200 chars: {script[:200]}")
    
    steps = []
    
    # Split by [NEW STEP] markers
    step_blocks = script.split('[NEW STEP]')[1:]  # Skip first empty part
    
    print(f"🔍 DEBUG: Found {len(step_blocks)} step blocks")
    
    for i, block in enumerate(step_blocks, 1):
        block = block.strip()
        if not block:
            print(f"🔧 Step {i} is empty, skipping")
            continue
            
        print(f"🔧 Processing step {i}: {block[:100]}...")
        
        # Look for the END STEP marker
        if '[END STEP|| Scene description:' in block:
            # Split into narration and scene description
            parts = block.split('[END STEP|| Scene description:', 1)
            if len(parts) == 2:
                narration = parts[0].strip()
                scene_description = parts[1].strip()
                
                # Clean up scene description (remove any trailing brackets)
                scene_description = scene_description.rstrip(']')
                
                steps.append(SolutionStep(narration, scene_description))
                print(f"✅ Successfully parsed step {i}")
            else:
                print(f"❌ Failed to split step {i} properly")
        else:
            print(f"❌ No END STEP marker found in step {i}")
            # Create a fallback with default scene description
            narration = block.strip()
            default_scene = f"Show mathematical work for: {narration[:100]}..."
            steps.append(SolutionStep(narration, default_scene))
            print(f"🔧 Created step {i} with default scene description")
    
    print(f"🔍 DEBUG: Final result: {len(steps)} steps extracted")
    for i, step in enumerate(steps):
        word_count = len(step.narration.split())
        print(f"  Step {i+1}: {word_count} words narration, {len(step.scene_description)} chars description")
    
    return steps

# ---------------------------
# Problem-Solving Script Generation
# ---------------------------
def generate_problem_solution_script(problem: str, duration_minutes: int = 3, detail_level: int = 2) -> ProblemSolutionScript:
    """
    Generate a step-by-step solution script for a specific problem
    """
    if detail_level < 1 or detail_level > 3:
        detail_level = 2

    expected_words = duration_minutes * WORDS_PER_MINUTE
    
    # Calculate reasonable step count based on problem complexity and duration
    # For problem solving, we typically want 3-6 steps
    step_count = max(3, min(8, duration_minutes + 1))
    words_per_step = expected_words // step_count

    detail_level_desc = DETAIL_LEVEL_DESCRIPTIONS.get(detail_level)

    system_prompt = PROBLEM_SOLVING_PROMPT_TEMPLATE.format(
        problem=problem,
        detail_level_desc=detail_level_desc,
        duration_minutes=duration_minutes,
        expected_words=expected_words,
        step_count=step_count,
        words_per_step=words_per_step
    )

    user_prompt = (
        f"Create a detailed step-by-step solution for the problem: {problem} "
        f"at a {detail_level_desc}. "
        f"The solution should have exactly {step_count} steps, each approximately {words_per_step} words. "
        f"Target total length: {expected_words} words ({duration_minutes} minutes when spoken). "
        f"Use [NEW STEP] and [END STEP|| Scene description: ...] markers for each solution step."
    )

    try:
        full_script = llm.chat(system_prompt, user_prompt)
        
        # Debug output to track what's happening
        print(f"🔍 DEBUG: Raw solution script length: {len(full_script)} characters")
        print(f"🔍 DEBUG: Requested {step_count} steps with ~{words_per_step} words each")
        print(f"🔍 DEBUG: Target: {expected_words} words = {duration_minutes} minutes")
        
        # Extract solution steps
        steps = extract_solution_steps(full_script)
        print(f"🔍 DEBUG: Extracted {len(steps)} solution steps")
        
        if steps:
            total_words = sum(len(step.narration.split()) for step in steps)
            estimated_duration = total_words / WORDS_PER_MINUTE
            print(f"🔍 DEBUG: Actual: {total_words} words = {estimated_duration:.1f} minutes")
            
            # Show word count per step
            for i, step in enumerate(steps, 1):
                word_count = len(step.narration.split())
                print(f"  Step {i}: {word_count} words")
        else:
            print("🔍 DEBUG: No steps extracted - this should not happen!")
            print(f"🔍 DEBUG: Raw script preview:\n{full_script[:500]}...")

        return ProblemSolutionScript(
            problem=problem,
            duration_minutes=duration_minutes,
            detail_level=detail_level,
            steps=steps
        )

    except Exception as e:
        raise RuntimeError(f"Problem solution script generation failed: {str(e)}")

# ---------------------------
# Integration Function (Convert to existing Script format)
# ---------------------------
def generate_problem_script_for_pipeline(problem: str, duration_minutes: int = 3, detail_level: int = 2):
    """
    Generate problem solution script and convert to existing Script format for pipeline compatibility
    """
    from backend.generate_script import Script, ConceptSegment
    
    # Generate problem solution
    problem_script = generate_problem_solution_script(problem, duration_minutes, detail_level)
    
    # Convert to existing Script format
    concepts = [
        ConceptSegment(step.narration, step.scene_description)
        for step in problem_script.steps
    ]
    
    return Script(
        topic=f"Problem: {problem}",  # Use problem as topic
        duration_minutes=duration_minutes,
        sophistication_level=detail_level,  # Map detail_level to sophistication_level
        concepts=concepts
    )

# ---------------------------
# CLI Entry Point
# ---------------------------
def main():
    problem = input("What problem would you like me to solve? (e.g., 'Solve: 2x + 5 = 13'): ")

    try:
        duration_minutes = int(input("Enter desired video length in minutes (max: 10): "))
        if not (1 <= duration_minutes <= 10):
            print("Using default duration of 3 minutes.")
            duration_minutes = 3
    except ValueError:
        print("Using default duration of 3 minutes.")
        duration_minutes = 3

    try:
        detail_level = int(input("Enter detail level (1=Basic, 2=Standard, 3=Detailed): "))
        if not (1 <= detail_level <= 3):
            print("Using default level: 2 (Standard).")
            detail_level = 2
    except ValueError:
        print("Using default level: 2 (Standard).")
        detail_level = 2

    print(f"Generating solution for '{problem}' ({duration_minutes} minutes, level {detail_level})...")
    script = generate_problem_solution_script(problem, duration_minutes, detail_level)

    print("\n--- SOLUTION STEPS ---")
    for i, step in enumerate(script.steps, 1):
        print(f"\nStep {i}:")
        print(step.narration)

    print("\n\n--- SCENE DESCRIPTIONS ---")
    for i, step in enumerate(script.steps, 1):
        print(f"\nStep {i} Visualization:")
        print(step.scene_description)

    print(f"\n\nGenerated {len(script.steps)} solution steps with narrations and scene descriptions")

if __name__ == "__main__":
    main()