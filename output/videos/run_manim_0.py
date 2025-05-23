
import sys
sys.path.append("/Users/dariuskashani/CodeProjects/ai_tutor/output/scenes")
from manim import *
from pathlib import Path

config.media_dir = "/Users/dariuskashani/CodeProjects/ai_tutor/output/videos"
config.video_dir = "/Users/dariuskashani/CodeProjects/ai_tutor/output/videos"
config.output_file = "scene_0"

# Import scene file
scene_path = "/Users/dariuskashani/CodeProjects/ai_tutor/output/scenes/scene_0.py"
with open(scene_path, "r") as f:
    scene_code = f.read()

# Execute scene code
exec(scene_code)

# Run the scene
scene = UserAnimationScene()
scene.render()

# Print the output location for the parent process
print(f"RENDER_OUTPUT: {config.get_movie_file_path('UserAnimationScene', 'mp4')}")
