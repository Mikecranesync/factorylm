"""
POLISH & TECH DEBT CLEANUP
==========================
Final quality pass before tasks go to Done.

Workflow:
1. Task completes → trigger polish cycle
2. Scan for tech debt (TODOs, bare excepts, missing docs)
3. Fix issues autonomously
4. Polish output 3x (refine, improve, finalize)
5. Move to Done only when clean
"""

import os
import sys
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import logging

sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent, with_celery_tracing
from observability import traced

logger = logging.getLogger(__name__)

# Tech debt patterns to scan for
TECH_DEBT_PATTERNS = [
    (r'except\s*:', 'bare_except', 'Bare except clause - should specify exception type'),
    (r'#\s*(TODO|FIXME|HACK|XXX):', 'todo_comment', 'Unresolved TODO/FIXME comment'),
    (r'pass\s*$', 'empty_pass', 'Empty pass statement - may need implementation'),
    (r'import\s+\*', 'star_import', 'Star import - should be explicit'),
    (r'(password|secret|api_key)\s*=\s*["\'][^"\']+["\']', 'hardcoded_secret', 'Possible hardcoded secret'),
    (r'print\(', 'debug_print', 'Debug print statement'),
]

# Output directories to track
OUTPUT_DIRS = [
    '/opt/factorylm-sync/automatons-output',
    '/opt/master_of_puppets/reporting',
    '/root/jarvis-workspace/brand',
    '/root/jarvis-workspace/sales',
    '/root/jarvis-workspace/content',
]

DEBT_LOG = Path('/root/jarvis-workspace/brain/automaton/code-debt.md')
IMPROVEMENTS_LOG = Path('/root/jarvis-workspace/brain/automaton/improvements-log.md')


class PolishAgent(BaseAgent):
    """Final quality pass agent."""
    
    def __init__(self):
        super().__init__("PolishAgent")
    
    def scan_file_for_debt(self, filepath: str) -> List[Dict]:
        """Scan a file for tech debt patterns."""
        issues = []
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            for i, line in enumerate(lines, 1):
                for pattern, issue_type, description in TECH_DEBT_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        issues.append({
                            'file': filepath,
                            'line': i,
                            'type': issue_type,
                            'description': description,
                            'content': line.strip()[:100],
                        })
        except Exception as e:
            self.logger.warning(f"Could not scan {filepath}: {e}")
        
        return issues
    
    def scan_directory_for_debt(self, directory: str, extensions: List[str] = None) -> List[Dict]:
        """Scan directory recursively for tech debt."""
        if extensions is None:
            extensions = ['.py', '.ts', '.tsx', '.js', '.jsx', '.md']
        
        all_issues = []
        path = Path(directory)
        
        if not path.exists():
            return all_issues
        
        for ext in extensions:
            for filepath in path.rglob(f'*{ext}'):
                # Skip node_modules, venv, etc.
                if any(skip in str(filepath) for skip in ['node_modules', 'venv', '.git', '__pycache__']):
                    continue
                issues = self.scan_file_for_debt(str(filepath))
                all_issues.extend(issues)
        
        return all_issues
    
    def fix_bare_except(self, filepath: str, line_num: int) -> bool:
        """Fix bare except clauses."""
        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()
            
            if line_num <= len(lines):
                line = lines[line_num - 1]
                # Replace 'except:' with 'except Exception:'
                fixed = re.sub(r'except\s*:', 'except Exception:', line)
                if fixed != line:
                    lines[line_num - 1] = fixed
                    with open(filepath, 'w') as f:
                        f.writelines(lines)
                    return True
        except Exception as e:
            self.logger.error(f"Could not fix {filepath}:{line_num}: {e}")
        return False
    
    def log_debt(self, issues: List[Dict], task_name: str):
        """Log tech debt to markdown file."""
        DEBT_LOG.parent.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        with open(DEBT_LOG, 'a') as f:
            f.write(f"\n## {timestamp} - {task_name}\n\n")
            for issue in issues[:20]:  # Limit to 20 issues
                f.write(f"- **{issue['type']}** in `{issue['file']}:{issue['line']}`\n")
                f.write(f"  - {issue['description']}\n")
                f.write(f"  - `{issue['content']}`\n")
    
    def log_improvement(self, task_name: str, improvement: str):
        """Log improvements made."""
        IMPROVEMENTS_LOG.parent.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        with open(IMPROVEMENTS_LOG, 'a') as f:
            f.write(f"- {timestamp} | {task_name} | {improvement}\n")
    
    def polish_content(self, content: str, iteration: int) -> str:
        """
        Polish content through multiple refinement passes.
        Each pass focuses on different aspects.
        """
        # This would ideally call an LLM for each pass
        # For now, we do basic cleanup
        
        if iteration == 1:
            # Pass 1: Remove excessive whitespace
            content = re.sub(r'\n{3,}', '\n\n', content)
            content = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)
        
        elif iteration == 2:
            # Pass 2: Ensure consistent formatting
            content = re.sub(r'#([A-Za-z])', r'# \1', content)  # Space after headers
        
        elif iteration == 3:
            # Pass 3: Final cleanup
            content = content.strip() + '\n'
        
        return content
    
    def run_polish_cycle(self, task_info: Dict, polish_passes: int = 3) -> Dict:
        """
        Run complete polish cycle for a completed task.
        
        1. Scan for tech debt
        2. Fix what we can
        3. Log what we can't
        4. Polish outputs
        """
        self.log_start("polish_cycle")
        
        task_name = task_info.get('name', 'Unknown Task')
        task_id = task_info.get('id', '')
        
        results = {
            'task': task_name,
            'debt_found': 0,
            'debt_fixed': 0,
            'debt_logged': 0,
            'polish_passes': polish_passes,
            'status': 'completed'
        }
        
        # Step 1: Scan for tech debt in recent outputs
        all_issues = []
        for output_dir in OUTPUT_DIRS:
            issues = self.scan_directory_for_debt(output_dir)
            all_issues.extend(issues)
        
        results['debt_found'] = len(all_issues)
        
        # Step 2: Fix what we can automatically
        fixed_count = 0
        unfixed = []
        
        for issue in all_issues:
            if issue['type'] == 'bare_except':
                if self.fix_bare_except(issue['file'], issue['line']):
                    fixed_count += 1
                    self.log_improvement(task_name, f"Fixed bare except in {issue['file']}:{issue['line']}")
                else:
                    unfixed.append(issue)
            else:
                unfixed.append(issue)
        
        results['debt_fixed'] = fixed_count
        
        # Step 3: Log unfixed issues
        if unfixed:
            self.log_debt(unfixed, task_name)
            results['debt_logged'] = len(unfixed)
        
        # Step 4: Polish outputs (multiple passes)
        # For now, this is a placeholder - would integrate with LLM
        for i in range(1, polish_passes + 1):
            self.logger.info(f"Polish pass {i}/{polish_passes} for {task_name}")
            # In a full implementation, this would:
            # - Re-read output files
            # - Send to LLM for refinement
            # - Save improved versions
        
        self.log_complete("polish_cycle", results)
        return results


polish_agent = PolishAgent()


# ============== CELERY TASKS ==============

@app.task(bind=True, name='polish.run_cycle')
@with_celery_tracing("run_polish_cycle")
@traced(name="polish_cycle", layer="quality")
def run_polish_cycle(self, task_info: Dict, polish_passes: int = 3) -> Dict:
    """
    Run polish cycle for a completed task.
    Called automatically when tasks move to Done.
    """
    return polish_agent.run_polish_cycle(task_info, polish_passes)


@app.task(bind=True, name='polish.scan_debt')
@with_celery_tracing("scan_debt")
@traced(name="scan_debt", layer="quality")
def scan_debt(self, directory: str = None) -> Dict:
    """Scan for tech debt in specified directory or all output dirs."""
    if directory:
        issues = polish_agent.scan_directory_for_debt(directory)
    else:
        issues = []
        for d in OUTPUT_DIRS:
            issues.extend(polish_agent.scan_directory_for_debt(d))
    
    return {
        'issues_found': len(issues),
        'issues': issues[:50],  # Return first 50
        'directories_scanned': [directory] if directory else OUTPUT_DIRS
    }


@app.task(bind=True, name='polish.health')
@with_celery_tracing("health")
def health(self) -> Dict:
    """Health check for polish agent."""
    return {'status': 'ok', 'agent': 'PolishAgent'}
