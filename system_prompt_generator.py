"""
Automatic System Prompt Generator for Scico
Reads project files and generates an up-to-date LLM_INSTRUCTIONS.md
"""

import os
import tomllib
from pathlib import Path
from datetime import datetime
from directory_tree_generator import generate_src_tree_markdown


def read_file(filepath: str) -> str:
    """Read file content safely"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ""


def parse_pyproject_toml(filepath: str = "pyproject.toml") -> dict:
    """Extract key info from pyproject.toml"""
    try:
        with open(filepath, 'rb') as f:
            data = tomllib.load(f)
        project = data.get('project', {})
        return {
            'name': project.get('name', 'scico'),
            'version': project.get('version', '0.1.0'),
            'description': project.get('description', ''),
            'dependencies': project.get('dependencies', [])
        }
    except FileNotFoundError:
        return {}


def scan_src_directory(src_path: str = "src") -> dict:
    """Scan src directory for tool files and their status"""
    tools = {}
    src_dir = Path(src_path)
    
    if not src_dir.exists():
        return tools
    
    for file in src_dir.glob("*.py"):
        if file.name.startswith('__'):
            continue
            
        content = file.read_text(encoding='utf-8')
        # Check if file has substantial code (more than just imports)
        lines = [l.strip() for l in content.split('\n') if l.strip() and not l.strip().startswith('#')]
        non_import_lines = [l for l in lines if not l.startswith('import') and not l.startswith('from')]
        
        status = "✓ ready" if len(non_import_lines) > 5 else "⚠ empty/stub"
        
        # Extract docstring if available
        if '"""' in content:
            doc_start = content.find('"""') + 3
            doc_end = content.find('"""', doc_start)
            description = content[doc_start:doc_end].strip().split('\n')[0] if doc_end > doc_start else ""
        else:
            description = ""
        
        tools[file.name] = {
            'status': status,
            'description': description
        }
    
    return tools


def extract_key_dependencies(deps: list) -> dict:
    """Categorize important dependencies"""
    categories = {
        'ai_ml': ['langchain', 'ollama', 'chromadb', 'fastmcp', 'mcp'],
        'data': ['pandas', 'numpy'],
        'research': ['pyzotero', 'marker-pdf'],
        'utilities': ['python-dotenv', 'sqlalchemy']
    }
    
    found = {}
    for dep in deps:
        dep_name = dep.split('>=')[0].split('==')[0].strip()
        for category, keywords in categories.items():
            if any(keyword in dep_name.lower() for keyword in keywords):
                if category not in found:
                    found[category] = []
                found[category].append(dep_name)
    
    return found


def generate_system_prompt(project_info: dict, tools: dict, readme_content: str) -> str:
    """Generate the system prompt markdown"""
    
    # Categorize dependencies
    deps = extract_key_dependencies(project_info.get('dependencies', []))
    tech_stack = []
    if 'ai_ml' in deps:
        tech_stack.extend(deps['ai_ml'])
    
    # Separate tools by status
    ready_tools = {k: v for k, v in tools.items() if '✓' in v['status']}
    incomplete_tools = {k: v for k, v in tools.items() if '⚠' in v['status']}
    
    prompt = f"""# SCICO System Prompt
*Auto-generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*
*Version: {project_info.get('version', 'unknown')}*

## Identity
I am Scico - a scientific AI co-worker helping humans overcome technical hurdles in research, coding, and documentation.

**Project Description:** {project_info.get('description', 'Scientific coworker centered around an LLM')}

## Core Mission
- **Support human creativity** as the driving force - never interrupt or bias it
- **Remove technical barriers** in research, summarizing, coding, and reference management
- **Elevate, don't replace** - the human is architect, director, and conductor

## Operating Principles
1. **Plan → Decide → Execute** (or communicate limitations)
2. **Deterministic first** - prefer workflows over unpredictable AI when possible
3. **Transparent & reproducible** - explain architecture and decisions
4. **Human-controlled** - full access to my architecture; user can modify/add tools

## Current Capabilities

### Operational Tools ({len(ready_tools)})
"""
    
    for tool_name, info in ready_tools.items():
        desc = info['description'] if info['description'] else "Available"
        prompt += f"- **{tool_name}**: {desc}\n"
    
    if incomplete_tools:
        prompt += f"\n### Incomplete Tools ({len(incomplete_tools)})\n"
        for tool_name, info in incomplete_tools.items():
            prompt += f"- **{tool_name}**: Needs implementation\n"
    
    prompt += f"""
## Tech Stack
{' • '.join(tech_stack)}

## Project Structure

{generate_src_tree_markdown('src', include_descriptions=True, max_depth=2)}

## Current State
Version {project_info.get('version', '0.1.0')} - Building toward complete agentic workflow system.
Functional components: {len(ready_tools)} | In development: {len(incomplete_tools)}
"""

    return prompt


def main():
    """Main execution"""
    print("🔄 Generating Scico System Prompt...")

    # Gather information
    project_info = parse_pyproject_toml("pyproject.toml")
    tools = scan_src_directory("src")
    readme = read_file("README.md")

    # Generate prompt
    prompt = generate_system_prompt(project_info, tools, readme)

    # Save to file
    output_file = "LLM_INSTRUCTIONS.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(prompt)

    print(f"✅ System prompt generated: {output_file}")
    print(f"   - Found {len(tools)} tool files")
    print(f"   - Project version: {project_info.get('version', 'unknown')}")


if __name__ == "__main__":
    main()