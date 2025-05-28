import subprocess
import json
import time
import re
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from backend.generate_script import Script, generate_script
from config.paths import (
    MANIM_KNOWLEDGE_PATH, MANIM_PROMPT_PATH, VIDEO_OUTPUT_DIR, CODE_OUTPUT_DIR,
    DATA_PATH, PROMPTS_PATH
)
from config.llm import LLMClient

# Load environment variables
load_dotenv()

# Initialize the LLM client with higher token limit for analysis
llm = LLMClient(model="claude-sonnet-4-20250514", temperature=0.3, max_tokens=16000)

# Load Manim knowledge and initial prompt template
manim_knowledge = MANIM_KNOWLEDGE_PATH.read_text(encoding="utf-8")
math_tex_knowledge = (DATA_PATH / "math_tex_knowledge.txt").read_text(encoding="utf-8")

# 25 Different Mathematical Topics
MATH_TOPICS = [
    "Isosceles Triangle",
    "Pythagorean Theorem", 
    "Circle Area and Circumference",
    "Linear Equations",
    "Quadratic Functions",
    "Sine and Cosine Functions",
    "Exponential Growth",
    "Logarithmic Functions",
    "Polygon Interior Angles",
    "Coordinate Plane Basics",
    "Slope of a Line",
    "Distance Formula",
    "Factoring Polynomials",
    "Fraction Operations",
    "Percentage Calculations",
    "Mean, Median, Mode",
    "Probability Basics",
    "Prime Numbers",
    "Square Roots",
    "Geometric Sequences",
    "Arithmetic Sequences",
    "Angle Relationships",
    "Perimeter and Area",
    "Volume of Shapes",
    "Symmetry and Transformations"
]

class PromptImprover:
    def __init__(self, max_iterations=10):
        self.max_iterations = max_iterations
        self.current_prompt = MANIM_PROMPT_PATH.read_text(encoding="utf-8")
        self.improvement_log = []
        self.successful_renders = 0
        self.failed_renders = 0
        self.topic_results = {}  # Track results by topic
        
    def save_prompt_version(self, version_number, reason=""):
        """Save the current prompt with a version number"""
        filename = f"manim_prompt_v{version_number}.txt"
        prompt_dir = DATA_PATH / "prompt_versions"
        prompt_dir.mkdir(exist_ok=True)
        
        prompt_file = prompt_dir / filename
        with prompt_file.open("w", encoding="utf-8") as f:
            f.write(f"# Version {version_number}\n")
            f.write(f"# Reason: {reason}\n")
            f.write(f"# Success rate: {self.successful_renders}/{self.successful_renders + self.failed_renders}\n\n")
            f.write(self.current_prompt)
        
        print(f"💾 Saved prompt version {version_number} to: {prompt_file}")
        return prompt_file

    def analyze_error(self, error_message, failed_code, original_prompt, scene_description):
        """Send error details to LLM for analysis and prompt improvement"""
        analysis_prompt = f"""
You are a Manim expert. A Manim scene failed to render. Analyze the error and suggest a SHORT, SPECIFIC addition to fix this type of error.

**SCENE DESCRIPTION:**
{scene_description}

**FAILED CODE:**
```python
{failed_code}
```

**ERROR MESSAGE:**
{error_message}

Your task: Provide a concise addition (1-3 sentences) that would prevent this specific error type.

**Response format:**
ANALYSIS: [Brief analysis of what went wrong]

ADDITION: [Short, specific rule/guideline to add to the prompt - maximum 50 words]

Examples of good additions:
- "Always use raw strings for MathTex: MathTex(r'text') not MathTex('text')"
- "For Arc objects, ensure start_angle and angle parameters are valid: angle > 0"
- "Use Text() instead of MathTex() for simple labels to avoid LaTeX errors"
"""

        print("\n🔍 Analyzing error for targeted fix...")
        response = llm.chat(
            "You are a Manim expert providing concise error fixes.",
            analysis_prompt
        )
        
        return response

    def extract_addition(self, llm_response):
        """Extract the small addition from LLM response"""
        print("🔍 Extracting addition from LLM response...")
        
        # Look for the ADDITION section
        match = re.search(r'ADDITION:\s*(.*?)(?=\n\n|\n[A-Z]+:|$)', llm_response, re.DOTALL)
        if match:
            addition = match.group(1).strip()
            print(f"✅ Found addition: {addition[:100]}...")
            return addition
        
        print("❌ Could not extract addition from LLM response")
        print("🔍 LLM Response preview:")
        print(llm_response[:300] + "..." if len(llm_response) > 300 else llm_response)
        return None

    def update_prompt(self, llm_analysis, error_context):
        """Update the current prompt by appending a small addition"""
        original_length = len(self.current_prompt.split())
        addition = self.extract_addition(llm_analysis)
        
        if addition:
            # Append the addition to the existing prompt
            fix_number = len(self.improvement_log) + 1
            self.current_prompt += f"\n\n**Error Fix #{fix_number}:**\n{addition}"
            
            new_length = len(self.current_prompt.split())
            
            # Log the improvement
            improvement_entry = {
                "fix_number": fix_number,
                "error": error_context,
                "analysis": llm_analysis,
                "addition": addition,
                "prompt_length_before": original_length,
                "prompt_length_after": new_length
            }
            self.improvement_log.append(improvement_entry)
            
            print(f"✅ Prompt updated: {original_length} → {new_length} words")
            print(f"📝 Added: {addition[:100]}...")
            return True
        else:
            print("❌ Failed to extract valid addition")
            return False

    def generate_manim_code(self, scene_description: str) -> str:
        """Generate Manim code using current prompt"""
        prompt = f"Scene description:\n{scene_description}"
        
        print("\n--- Using Current Prompt ---")
        print(f"Prompt length: {len(self.current_prompt.split())} words")
        
        system_prompt = f"""
This is the full breakdown on how to use manim:
{manim_knowledge}

This is the full breakdown on how to use math_tex:
{math_tex_knowledge}

This is the task we would like you to accomplish with the given information:
{self.current_prompt}
"""
        raw_output = llm.chat(system_prompt, prompt)

        print("\n--- Raw LLM Output ---")
        print(raw_output[:500] + "..." if len(raw_output) > 500 else raw_output)
        print("--- End Raw Output ---")

        match = re.search(r"'''(.*?)'''", raw_output, flags=re.DOTALL)
        code = match.group(1).strip() if match else ""

        # Check if code appears incomplete (ends with truncation indicators)
        if code and (code.endswith('...') or len(raw_output) > 15000):
            print("⚠️ Code appears truncated, trying with higher max_tokens...")
            # Retry with higher limit
            raw_output = llm.chat(system_prompt, prompt, max_tokens=20000)
            match = re.search(r"'''(.*?)'''", raw_output, flags=re.DOTALL)
            code = match.group(1).strip() if match else ""

        print("\n--- Extracted Code ---")
        print(code[:300] + "..." if len(code) > 300 else code if code else "[No code found in triple quotes]")
        print("--- End Extracted Code ---")

        return code

    def render_code_with_error_capture(self, py_file: Path, scene_name: str, output_dir: Path):
        """Render Manim code and capture detailed error information"""
        print(f"🎬 Rendering {scene_name} from {py_file.name}...")
        try:
            result = subprocess.run(
                ["manim", str(py_file), scene_name, "-o", f"{py_file.stem}.mp4"],
                cwd=output_dir,
                capture_output=True,
                text=True,
                check=True
            )
            print("✅ Render complete.")
            self.successful_renders += 1
            return {"success": True, "stdout": result.stdout}
        except subprocess.CalledProcessError as e:
            print(f"❌ Render failed")
            self.failed_renders += 1
            error_info = {
                "success": False,
                "returncode": e.returncode,
                "stdout": e.stdout,
                "stderr": e.stderr,
                "full_error": str(e)
            }
            print(f"Error details: {error_info['stderr'][:200]}...")
            return error_info

    def process_topic_until_success(self, topic: str, topic_number: int):
        """Process a single topic until success or max iterations"""
        print(f"\n{'='*60}")
        print(f"🎯 TOPIC {topic_number}/25: {topic}")
        print(f"🔄 Max attempts: {self.max_iterations}")
        print(f"📊 Current Success Rate: {self.successful_renders}/{self.successful_renders + self.failed_renders}")
        print(f"{'='*60}")

        topic_slug = safe_slugify(topic)
        topic_code_dir = CODE_OUTPUT_DIR / topic_slug
        topic_video_dir = VIDEO_OUTPUT_DIR / topic_slug
        
        topic_code_dir.mkdir(parents=True, exist_ok=True)
        topic_video_dir.mkdir(parents=True, exist_ok=True)

        # Initialize topic tracking
        self.topic_results[topic] = {
            "attempts": 0,
            "success": False,
            "final_attempt": None,
            "errors_encountered": []
        }

        # Generate script for this topic
        try:
            print(f"📜 Generating script for {topic}...")
            script = generate_script(topic=topic, duration_minutes=2, sophistication_level=2)
            print(f"✅ Script generated with {len(script.concepts)} concepts")
            
            # Use the first concept's scene description for simplicity
            if not script.concepts:
                print(f"❌ No concepts generated for {topic}")
                return False
                
            scene_description = script.concepts[0].scene_description
            
        except Exception as e:
            print(f"❌ Failed to generate script for {topic}: {e}")
            return False

        # Attempt to render until success or max attempts
        for attempt in range(1, self.max_iterations + 1):
            print(f"\n--- 🔄 Attempt {attempt}/{self.max_iterations} for {topic} ---")
            self.topic_results[topic]["attempts"] = attempt
            
            # Generate code
            code = self.generate_manim_code(scene_description)
            
            if not code.strip():
                print("⚠️ Empty code generated, trying again...")
                continue

            # Save and test code
            filename = f"{topic_slug}_attempt_{attempt}"
            py_file = self.save_code(code, filename, topic_code_dir)
            scene_class = self.extract_scene_class(code)
            
            # Attempt render
            render_result = self.render_code_with_error_capture(py_file, scene_class, topic_video_dir)
            
            if render_result["success"]:
                print(f"🎉 SUCCESS! {topic} completed after {attempt} attempts!")
                self.topic_results[topic]["success"] = True
                self.topic_results[topic]["final_attempt"] = attempt
                
                # Save successful prompt version
                if len(self.improvement_log) > 0:
                    self.save_prompt_version(
                        len(self.improvement_log) + 1, 
                        f"Success on {topic} after {attempt} attempts"
                    )
                
                return True
            else:
                # Track error
                error_summary = render_result["stderr"][:100] + "..." if len(render_result["stderr"]) > 100 else render_result["stderr"]
                self.topic_results[topic]["errors_encountered"].append({
                    "attempt": attempt,
                    "error": error_summary
                })
                
                print(f"❌ Attempt {attempt} failed for {topic}")
                
                # Analyze error and improve prompt
                error_context = {
                    "topic": topic,
                    "attempt": attempt,
                    "scene_description": scene_description,
                    "failed_code": code,
                    "error_message": render_result["stderr"]
                }
                
                llm_analysis = self.analyze_error(
                    render_result["stderr"],
                    code,
                    self.current_prompt,
                    scene_description
                )
                
                if self.update_prompt(llm_analysis, error_context):
                    # Save improved prompt version
                    self.save_prompt_version(
                        len(self.improvement_log),
                        f"Fixed error in {topic}, attempt {attempt}"
                    )
                    print(f"🔄 Prompt improved, retrying...")
                else:
                    print(f"⚠️ Could not improve prompt, continuing...")
                
                # Small delay to avoid overwhelming the API
                time.sleep(2)

        print(f"❌ {topic} FAILED after {self.max_iterations} attempts")
        self.topic_results[topic]["final_attempt"] = self.max_iterations
        return False

    def save_code(self, code: str, filename: str, output_dir: Path):
        """Save code to file"""
        output_dir.mkdir(parents=True, exist_ok=True)
        py_file = output_dir / f"{filename}.py"
        with py_file.open("w", encoding="utf-8") as f:
            f.write(code)
        print(f"💾 Code saved to: {py_file}")
        return py_file

    def extract_scene_class(self, code: str) -> str:
        """Extract scene class name from code"""
        match = re.search(r'class\s+(\w+)\s*\(.*?Scene\)', code)
        if match:
            return match.group(1)
        return "Scene"

    def save_comprehensive_report(self):
        """Save a comprehensive report of all topics and improvements"""
        successful_topics = [topic for topic, result in self.topic_results.items() if result["success"]]
        failed_topics = [topic for topic, result in self.topic_results.items() if not result["success"]]
        
        report = {
            "experiment_summary": {
                "total_topics": len(MATH_TOPICS),
                "successful_topics": len(successful_topics),
                "failed_topics": len(failed_topics),
                "success_rate": len(successful_topics) / len(MATH_TOPICS),
                "total_improvements": len(self.improvement_log),
                "total_render_attempts": self.successful_renders + self.failed_renders,
                "overall_render_success_rate": self.successful_renders / (self.successful_renders + self.failed_renders) if (self.successful_renders + self.failed_renders) > 0 else 0
            },
            "successful_topics": successful_topics,
            "failed_topics": failed_topics,
            "topic_details": self.topic_results,
            "prompt_evolution": {
                "initial_length": len(MANIM_PROMPT_PATH.read_text(encoding="utf-8").split()),
                "final_length": len(self.current_prompt.split()),
                "improvements_made": len(self.improvement_log)
            },
            "improvements": self.improvement_log,
            "learning_summary": {
                "most_common_errors": self._analyze_common_errors(),
                "topics_by_difficulty": self._rank_topics_by_difficulty()
            }
        }
        
        report_file = DATA_PATH / "improvement_reports" / f"25_topics_report.json"
        report_file.parent.mkdir(exist_ok=True)
        
        with report_file.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"📊 FINAL EXPERIMENT REPORT")
        print(f"{'='*60}")
        print(f"✅ Successful topics: {len(successful_topics)}/25 ({len(successful_topics)/25:.1%})")
        print(f"❌ Failed topics: {len(failed_topics)}/25")
        print(f"🔧 Total prompt improvements: {len(self.improvement_log)}")
        print(f"📈 Overall render success rate: {report['experiment_summary']['overall_render_success_rate']:.1%}")
        print(f"📄 Final prompt length: {report['prompt_evolution']['final_length']} words")
        print(f"\n✅ Successful topics:")
        for topic in successful_topics[:10]:  # Show first 10
            attempts = self.topic_results[topic]["final_attempt"]
            print(f"   • {topic} ({attempts} attempts)")
        if len(successful_topics) > 10:
            print(f"   ... and {len(successful_topics) - 10} more")
        
        if failed_topics:
            print(f"\n❌ Failed topics:")
            for topic in failed_topics[:10]:  # Show first 10
                print(f"   • {topic}")
            if len(failed_topics) > 10:
                print(f"   ... and {len(failed_topics) - 10} more")
        
        print(f"\n📁 Full report saved to: {report_file}")
        return report_file
        
    def _analyze_common_errors(self):
        """Analyze the most common types of errors encountered"""
        error_types = {}
        for improvement in self.improvement_log:
            if "error_message" in improvement.get("error", {}):
                error_msg = improvement["error"]["error_message"]
                if "LaTeX" in error_msg or "latex" in error_msg:
                    error_types["LaTeX_errors"] = error_types.get("LaTeX_errors", 0) + 1
                elif "MathTex" in error_msg:
                    error_types["MathTex_errors"] = error_types.get("MathTex_errors", 0) + 1
                elif "compilation" in error_msg:
                    error_types["Compilation_errors"] = error_types.get("Compilation_errors", 0) + 1
                elif "ImportError" in error_msg or "ModuleNotFoundError" in error_msg:
                    error_types["Import_errors"] = error_types.get("Import_errors", 0) + 1
                elif "AttributeError" in error_msg:
                    error_types["Attribute_errors"] = error_types.get("Attribute_errors", 0) + 1
                else:
                    error_types["Other_errors"] = error_types.get("Other_errors", 0) + 1
        return error_types
    
    def _rank_topics_by_difficulty(self):
        """Rank topics by how many attempts they required"""
        topic_difficulty = []
        for topic, result in self.topic_results.items():
            difficulty_score = result["attempts"] if result["success"] else self.max_iterations + 1
            topic_difficulty.append({
                "topic": topic,
                "attempts_required": result["attempts"],
                "success": result["success"],
                "difficulty_score": difficulty_score
            })
        
        # Sort by difficulty (more attempts = more difficult)
        topic_difficulty.sort(key=lambda x: x["difficulty_score"])
        return topic_difficulty

def safe_slugify(text: str) -> str:
    """Convert text to safe filename"""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

def main():
    """Main function to process all 25 topics"""
    print("🚀 Starting 25-Topic Iterative Prompt Improvement Experiment")
    print(f"📋 Topics to process: {len(MATH_TOPICS)}")
    print(f"🔄 Max attempts per topic: 10")
    print(f"🎯 Goal: Achieve success on each topic or exhaust attempts")

    # Initialize improver
    improver = PromptImprover(max_iterations=10)
    
    successful_count = 0
    start_time = datetime.now()
    
    # Process each topic
    for i, topic in enumerate(MATH_TOPICS, 1):
        topic_start = datetime.now()
        
        if improver.process_topic_until_success(topic, i):
            successful_count += 1
        
        topic_elapsed = datetime.now() - topic_start
        total_elapsed = datetime.now() - start_time
        
        print(f"\n⏱️  Topic {i} completed in {topic_elapsed.total_seconds():.1f}s")
        print(f"📊 Running tally: {successful_count}/{i} topics successful")
        print(f"⏱️  Total elapsed: {total_elapsed.total_seconds()/60:.1f} minutes")
        
        # Save intermediate progress every 5 topics
        if i % 5 == 0:
            print(f"\n💾 Saving intermediate progress at topic {i}...")
            improver.save_comprehensive_report()

    # Save final results
    total_elapsed = datetime.now() - start_time
    
    print(f"\n🏁 EXPERIMENT COMPLETE!")
    print(f"⏱️  Total time: {total_elapsed.total_seconds()/60:.1f} minutes")
    print(f"✅ Final success rate: {successful_count}/{len(MATH_TOPICS)} ({successful_count/len(MATH_TOPICS):.1%})")
    
    # Generate comprehensive report
    report_file = improver.save_comprehensive_report()
    
    # Save the final improved prompt as the new default
    final_prompt_file = PROMPTS_PATH / "manim_prompt_25topics_improved.txt"
    with final_prompt_file.open("w", encoding="utf-8") as f:
        f.write(f"# Improved prompt after processing 25 math topics\n")
        f.write(f"# Success rate: {successful_count}/{len(MATH_TOPICS)} ({successful_count/len(MATH_TOPICS):.1%})\n")
        f.write(f"# Total improvements: {len(improver.improvement_log)}\n")
        f.write(f"# Total time: {total_elapsed.total_seconds()/60:.1f} minutes\n\n")
        f.write(improver.current_prompt)
    print(f"💾 Final improved prompt saved to: {final_prompt_file}")

if __name__ == "__main__":
    main()