#!/usr/bin/env python3
"""
Manim Explorer - A utility to extract and compile information about Manim

This script extracts information about Manim's classes, functions, and their 
documentation using Python's introspection capabilities. It outputs this information
to a text file for use with AI code generation.
"""

import os
import sys
import inspect
import importlib
import re
import json
import pkgutil
from pathlib import Path

# Hardcoded list of key Manim modules to explore if automatic discovery fails
KNOWN_MODULES = [
    'manim',
    'manim.animation',
    'manim.animation.animation',
    'manim.animation.creation',
    'manim.animation.fading',
    'manim.animation.movement',
    'manim.animation.numbers',
    'manim.animation.rotation',
    'manim.animation.transform',
    'manim.camera.camera',
    'manim.mobject.geometry',
    'manim.mobject.mobject',
    'manim.mobject.svg.svg_mobject',
    'manim.mobject.text.text_mobject',
    'manim.mobject.three_d.three_dimensions',
    'manim.mobject.value_tracker',
    'manim.scene.scene',
    'manim.utils.color',
    'manim.utils.config_ops',
    'manim.utils.space_ops',
    'manim.utils.rate_functions',
]

def check_manim_installed():
    """Check if Manim is installed."""
    try:
        import manim
        print(f"Manim version {manim.__version__} found.")
        return True
    except ImportError:
        print("Manim is not installed. Please install it with 'pip install manim'.")
        return False

def get_all_modules(package_name='manim'):
    """Get all submodules of a package recursively."""
    try:
        package = importlib.import_module(package_name)
        path = getattr(package, '__path__', [None])[0]
        if not path:
            return [package_name]
        
        modules = [package_name]
        for finder, name, ispkg in pkgutil.iter_modules([path]):
            full_name = package_name + '.' + name
            modules.append(full_name)
            if ispkg:
                modules.extend(get_all_modules(full_name))
        return modules
    except (ImportError, AttributeError) as e:
        print(f"Error exploring module {package_name}: {e}")
        return []

def get_module_members(module_name):
    """Get all classes and functions from a module."""
    try:
        module = importlib.import_module(module_name)
        members = inspect.getmembers(module)
        classes = []
        functions = []
        
        for name, obj in members:
            # Skip private members
            if name.startswith('_'):
                continue
                
            # Filter out imported members
            try:
                if inspect.getmodule(obj) != module:
                    continue
            except:
                # If we can't determine the module, assume it's part of this module
                pass
                
            if inspect.isclass(obj):
                classes.append((name, obj))
            elif inspect.isfunction(obj):
                functions.append((name, obj))
                
        return classes, functions
    except (ImportError, AttributeError) as e:
        print(f"Error getting members from {module_name}: {e}")
        return [], []

def get_class_methods(cls):
    """Get all methods of a class."""
    methods = []
    try:
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            # Skip private methods
            if name.startswith('_') and not name.startswith('__'):
                continue
            methods.append((name, method))
        return methods
    except Exception as e:
        print(f"Error getting methods from {cls.__name__}: {e}")
        return []

def format_parameters(params):
    """Format parameter information."""
    result = []
    for name, param in params.items():
        if name == 'self' or name == 'cls':
            continue
            
        if param.default is inspect.Parameter.empty:
            result.append(name)
        else:
            # Format default value
            default = param.default
            if default is None:
                default_str = 'None'
            elif isinstance(default, str):
                default_str = f"'{default}'"
            elif isinstance(default, bool):
                default_str = str(default)
            else:
                try:
                    default_str = str(default)
                except:
                    default_str = "???"
            result.append(f"{name}={default_str}")
            
    return ", ".join(result)

def get_docstring_summary(doc):
    """Extract the first line or paragraph from a docstring."""
    if not doc:
        return "No documentation available."
    
    # Clean the docstring
    doc = re.sub(r'\n\s+', ' ', doc)
    
    # Get the first sentence or paragraph
    match = re.search(r'^(.*?\.)\s', doc)
    if match:
        return match.group(1)
    
    # If no period found, return the first line
    lines = doc.strip().split('\n')
    return lines[0] if lines else "No summary available."

def process_module(module_name, manim_info):
    """Process a single module and add information to manim_info."""
    short_name = module_name.split('.')[-1]
    print(f"Exploring module: {short_name}")
    
    classes, functions = get_module_members(module_name)
    
    module_info = {
        'classes': {},
        'functions': {}
    }
    
    # Process classes
    for name, cls in classes:
        print(f"  Class: {name}")
        
        # Get inheritance info
        base_classes = []
        for base in cls.__bases__:
            if base.__name__ != 'object':
                base_classes.append(base.__name__)
        
        # Get methods
        methods = get_class_methods(cls)
        methods_info = {}
        
        for method_name, method in methods:
            try:
                # Get method signature
                sig = inspect.signature(method)
                params = format_parameters(sig.parameters)
                
                # Get docstring summary
                doc = inspect.getdoc(method)
                summary = get_docstring_summary(doc)
                
                methods_info[method_name] = {
                    'signature': f"{method_name}({params})",
                    'summary': summary,
                    'doc': doc
                }
            except Exception as e:
                print(f"    Error processing method {method_name}: {e}")
        
        # Get class docstring
        doc = inspect.getdoc(cls)
        summary = get_docstring_summary(doc)
        
        module_info['classes'][name] = {
            'bases': base_classes,
            'methods': methods_info,
            'summary': summary,
            'doc': doc
        }
    
    # Process functions
    for name, func in functions:
        print(f"  Function: {name}")
        try:
            # Get function signature
            sig = inspect.signature(func)
            params = format_parameters(sig.parameters)
            
            # Get docstring summary
            doc = inspect.getdoc(func)
            summary = get_docstring_summary(doc)
            
            module_info['functions'][name] = {
                'signature': f"{name}({params})",
                'summary': summary,
                'doc': doc
            }
        except Exception as e:
            print(f"    Error processing function {name}: {e}")
    
    manim_info['modules'][module_name] = module_info

def explore_manim(output_file='stored_data/manim_complete_reference.txt'):
    """Explore Manim and save information to a file."""
    if not check_manim_installed():
        return None
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Create dictionary to store all information
    manim_info = {
        'modules': {},
        'common_patterns': []
    }
    
    # Try automatic module discovery first
    print("Attempting automatic module discovery...")
    modules = get_all_modules()
    print(f"Found {len(modules)} modules automatically.")
    
    # If automatic discovery fails, use the hardcoded list
    if len(modules) <= 1:
        print("Automatic discovery failed. Using hardcoded module list...")
        modules = KNOWN_MODULES
        print(f"Using {len(modules)} hardcoded modules.")
    
    # Process each module
    for module_name in modules:
        try:
            process_module(module_name, manim_info)
        except Exception as e:
            print(f"Error processing module {module_name}: {e}")
    
    # Extract common patterns and usage examples
    print("Adding common patterns and usage examples...")
    
    # These would typically be hardcoded based on knowledge of the library
    # or extracted from example code
    manim_info['common_patterns'] = [
        {
            'pattern': 'Creating a basic scene',
            'code': '''
class MyScene(Scene):
    def construct(self):
        # Create objects
        circle = Circle()
        # Add objects to the scene
        self.add(circle)
        # Animate objects
        self.play(Create(circle))
''',
            'explanation': 'Every Manim animation is a Scene subclass with a construct method.'
        },
        {
            'pattern': 'Animating objects',
            'code': '''
# Animation basics
self.play(Create(circle))  # Create animation
self.play(FadeOut(circle))  # Fade out animation
self.play(Transform(object1, object2))  # Transform one object into another
''',
            'explanation': 'Animations are played using the self.play method.'
        },
        {
            'pattern': 'Positioning objects',
            'code': '''
# Absolute positioning
circle.move_to([1, 2, 0])  # Move to coordinates
# Relative positioning
square.next_to(circle, RIGHT)  # Position relative to another object
triangle.align_to(square, UP)  # Align with another object
''',
            'explanation': 'Objects can be positioned absolutely or relative to other objects.'
        },
        {
            'pattern': 'Creating text',
            'code': '''
# Basic text
text = Text("Hello Manim")
# Mathematical text
math = MathTex(r"e^{i\pi} + 1 = 0")
# Different fonts and styling
styled_text = Text("Styled", font="Times New Roman", color=BLUE)
''',
            'explanation': 'Manim provides various text objects for regular text and mathematical expressions.'
        },
        {
            'pattern': 'Using coordinates and vectors',
            'code': '''
# Points and vectors
point = np.array([1, 2, 0])  # 3D point (z=0 for 2D)
dot = Dot(point)  # Create a dot at the point
arrow = Arrow(ORIGIN, point)  # Arrow from origin to point
''',
            'explanation': 'Manim uses 3D coordinates with z=0 for 2D animations.'
        },
        {
            'pattern': 'Colors and styling',
            'code': '''
# Built-in colors
red_circle = Circle(color=RED)
# RGB colors
custom_color = Circle(color="#FF00FF")
# Fill vs stroke
filled_circle = Circle(color=BLUE, fill_opacity=0.5)
thick_circle = Circle(color=GREEN, stroke_width=10)
''',
            'explanation': 'Objects can be styled with colors, fill opacity, and stroke properties.'
        }
    ]
    
    # Write to file
    print(f"Writing information to {output_file}...")
    with open(output_file, 'w') as f:
        # Write header
        f.write("# Manim Complete Reference\n\n")
        f.write("This document contains a complete reference of the Manim library, extracted programmatically.\n\n")
        
        # Write modules
        f.write("## Modules\n\n")
        for module_name, module_info in manim_info['modules'].items():
            short_name = module_name.split('.')[-1]
            f.write(f"### {module_name}\n\n")
            
            # Write classes
            if module_info['classes']:
                f.write("#### Classes\n\n")
                for class_name, class_info in module_info['classes'].items():
                    f.write(f"##### {class_name}\n\n")
                    
                    # Write class summary and inheritance
                    f.write(f"{class_info['summary']}\n\n")
                    if class_info['bases']:
                        f.write(f"Inherits from: {', '.join(class_info['bases'])}\n\n")
                    
                    # Write methods
                    if class_info['methods']:
                        f.write("Methods:\n\n")
                        for method_name, method_info in class_info['methods'].items():
                            f.write(f"- `{method_info['signature']}`: {method_info['summary']}\n")
                        f.write("\n")
            
            # Write functions
            if module_info['functions']:
                f.write("#### Functions\n\n")
                for func_name, func_info in module_info['functions'].items():
                    f.write(f"- `{func_info['signature']}`: {func_info['summary']}\n")
                f.write("\n")
        
        # Write common patterns
        f.write("## Common Patterns\n\n")
        for pattern in manim_info['common_patterns']:
            f.write(f"### {pattern['pattern']}\n\n")
            f.write(f"{pattern['explanation']}\n\n")
            f.write("```python\n")
            f.write(pattern['code'])
            f.write("```\n\n")
    
    print(f"Done! Information saved to {output_file}")
    return manim_info

def explore_key_classes():
    """Explore just a few key classes for a minimal reference."""
    manim_info = {
        'modules': {},
        'key_classes': {},
        'common_patterns': []
    }
    
    # Key classes to explore directly
    key_classes = [
        ('Scene', 'manim.scene.scene'),
        ('Mobject', 'manim.mobject.mobject'),
        ('Circle', 'manim.mobject.geometry.arc'),
        ('Square', 'manim.mobject.geometry.polygram'),
        ('Text', 'manim.mobject.text.text_mobject'),
        ('MathTex', 'manim.mobject.text.tex_mobject'),
        ('Animation', 'manim.animation.animation'),
        ('Create', 'manim.animation.creation'),
        ('FadeOut', 'manim.animation.fading'),
        ('Transform', 'manim.animation.transform')
    ]
    
    # Explore each key class
    for class_name, module_name in key_classes:
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, class_name):
                cls = getattr(module, class_name)
                methods = get_class_methods(cls)
                methods_info = {}
                
                for method_name, method in methods:
                    try:
                        sig = inspect.signature(method)
                        params = format_parameters(sig.parameters)
                        doc = inspect.getdoc(method)
                        summary = get_docstring_summary(doc)
                        
                        methods_info[method_name] = {
                            'signature': f"{method_name}({params})",
                            'summary': summary,
                            'doc': doc
                        }
                    except Exception as e:
                        print(f"Error processing method {method_name}: {e}")
                
                doc = inspect.getdoc(cls)
                summary = get_docstring_summary(doc)
                
                # Get base classes
                base_classes = []
                for base in cls.__bases__:
                    if base.__name__ != 'object':
                        base_classes.append(base.__name__)
                
                manim_info['key_classes'][class_name] = {
                    'module': module_name,
                    'summary': summary,
                    'bases': base_classes,
                    'methods': methods_info,
                    'doc': doc
                }
                
                print(f"Processed key class: {class_name}")
        except Exception as e:
            print(f"Error processing key class {class_name} from {module_name}: {e}")
    
    return manim_info

def save_json(manim_info, output_file='stored_data/manim_reference.json'):
    """Save the collected information as JSON for programmatic use."""
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(manim_info, f, indent=2)
    print(f"JSON data saved to {output_file}")

if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Extract and compile information about Manim.")
    parser.add_argument('--output', '-o', default='stored_data/manim_complete_reference.txt', 
                        help='Output file for the text reference (default: stored_data/manim_complete_reference.txt)')
    parser.add_argument('--json', '-j', default='stored_data/manim_reference.json', 
                        help='Output file for the JSON data (default: stored_data/manim_reference.json)')
    parser.add_argument('--key-classes-only', '-k', action='store_true',
                        help='Only explore key classes (faster but less comprehensive)')
    args = parser.parse_args()
    
    # Run the explorer
    if args.key_classes_only:
        print("Exploring key Manim classes only...")
        manim_info = explore_key_classes()
        
        # Add common patterns
        manim_info['common_patterns'] = [
            {
                'pattern': 'Creating a basic scene',
                'code': '''
class MyScene(Scene):
    def construct(self):
        # Create objects
        circle = Circle()
        # Add objects to the scene
        self.add(circle)
        # Animate objects
        self.play(Create(circle))
''',
                'explanation': 'Every Manim animation is a Scene subclass with a construct method.'
            },
            {
                'pattern': 'Animating objects',
                'code': '''
# Animation basics
self.play(Create(circle))  # Create animation
self.play(FadeOut(circle))  # Fade out animation
self.play(Transform(object1, object2))  # Transform one object into another
''',
                'explanation': 'Animations are played using the self.play method.'
            },
            {
                'pattern': 'Positioning objects',
                'code': '''
# Absolute positioning
circle.move_to([1, 2, 0])  # Move to coordinates
# Relative positioning
square.next_to(circle, RIGHT)  # Position relative to another object
triangle.align_to(square, UP)  # Align with another object
''',
                'explanation': 'Objects can be positioned absolutely or relative to other objects.'
            },
            {
                'pattern': 'Creating text',
                'code': '''
# Basic text
text = Text("Hello Manim")
# Mathematical text
math = MathTex(r"e^{i\pi} + 1 = 0")
# Different fonts and styling
styled_text = Text("Styled", font="Times New Roman", color=BLUE)
''',
                'explanation': 'Manim provides various text objects for regular text and mathematical expressions.'
            }
        ]
    else:
        manim_info = explore_manim(args.output)
    
    # Save as JSON if needed
    if manim_info:
        save_json(manim_info, args.json)