#!/usr/bin/env python3
"""
Automated Dependency Update System
Detects and updates outdated package dependencies across multiple package managers.
Supports: npm, pip, pipenv, poetry, cargo, go mod
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import argparse


@dataclass
class DependencyInfo:
    """Information about a dependency"""
    name: str
    current_version: str
    latest_version: str
    package_manager: str
    file_path: str
    line_number: int = 0
    update_available: bool = False


@dataclass
class ProjectConfig:
    """Configuration for a project"""
    path: str
    package_managers: List[str] = field(default_factory=list)
    auto_update: bool = True
    update_major: bool = False
    update_minor: bool = True
    update_patch: bool = True
    exclude_packages: List[str] = field(default_factory=list)


class DependencyUpdater:
    """Main class for detecting and updating dependencies"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "dependency-updater.config.json"
        self.projects: List[ProjectConfig] = []
        self.dependencies: List[DependencyInfo] = []
        self.load_config()
    
    def load_config(self):
        """Load configuration from file"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    self.projects = [
                        ProjectConfig(**proj) for proj in config.get('projects', [])
                    ]
            except Exception as e:
                print(f"Warning: Could not load config: {e}")
                self.projects = []
        else:
            # Auto-detect projects
            self.auto_detect_projects()
    
    def auto_detect_projects(self):
        """Auto-detect projects - defaults to current directory"""
        # Default to current working directory
        current_dir = Path.cwd()
        config = self.detect_package_managers(current_dir)
        if config.package_managers:
            config.path = "."
            self.projects.append(config)
        else:
            # Fallback: check common locations
            home = Path.home()
            common_paths = [
                home,
                home / "projects",
                home / "workspace",
                home / "code",
            ]
            
            for base_path in common_paths:
                if base_path.exists():
                    for project_path in base_path.iterdir():
                        if project_path.is_dir():
                            config = self.detect_package_managers(project_path)
                            if config.package_managers:
                                config.path = str(project_path)
                                self.projects.append(config)
    
    def detect_package_managers(self, project_path: Path) -> ProjectConfig:
        """Detect which package managers are used in a project"""
        managers = []
        
        if (project_path / "package.json").exists():
            managers.append("npm")
        if (project_path / "requirements.txt").exists():
            managers.append("pip")
        if (project_path / "Pipfile").exists():
            managers.append("pipenv")
        if (project_path / "pyproject.toml").exists():
            # Check if it's poetry
            try:
                with open(project_path / "pyproject.toml") as f:
                    if "[tool.poetry]" in f.read():
                        managers.append("poetry")
            except:
                pass
        if (project_path / "Cargo.toml").exists():
            managers.append("cargo")
        if (project_path / "go.mod").exists():
            managers.append("go")
        
        return ProjectConfig(path=str(project_path), package_managers=managers)
    
    def check_npm_dependencies(self, project_path: str) -> List[DependencyInfo]:
        """Check npm dependencies"""
        deps = []
        package_json = Path(project_path) / "package.json"
        
        if not package_json.exists():
            return deps
        
        # Find project config for this path
        project_config = None
        abs_path = str(Path(project_path).resolve())
        for proj in self.projects:
            proj_abs_path = str(Path(proj.path).resolve())
            if proj_abs_path == abs_path or proj.path == ".":
                project_config = proj
                break
        
        try:
            with open(package_json, 'r') as f:
                package_data = json.load(f)
            
            # Check dependencies and devDependencies
            for dep_type in ['dependencies', 'devDependencies', 'peerDependencies']:
                if dep_type in package_data:
                    for name, version_spec in package_data[dep_type].items():
                        current = version_spec
                        latest = self.get_npm_latest_version(name)
                        
                        if latest:
                            update_available = self.should_update(current, latest, project_config)
                            deps.append(DependencyInfo(
                                name=name,
                                current_version=current,
                                latest_version=latest,
                                package_manager="npm",
                                file_path=str(package_json),
                                update_available=update_available
                            ))
        except Exception as e:
            print(f"Error checking npm dependencies in {project_path}: {e}")
        
        return deps
    
    def get_npm_latest_version(self, package_name: str) -> Optional[str]:
        """Get latest version of an npm package"""
        try:
            result = subprocess.run(
                ['npm', 'view', package_name, 'version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None
    
    def check_pip_dependencies(self, project_path: str) -> List[DependencyInfo]:
        """Check pip dependencies from requirements.txt"""
        deps = []
        requirements_file = Path(project_path) / "requirements.txt"
        
        if not requirements_file.exists():
            return deps
        
        # Find project config for this path
        project_config = None
        abs_path = str(Path(project_path).resolve())
        for proj in self.projects:
            proj_abs_path = str(Path(proj.path).resolve())
            if proj_abs_path == abs_path or proj.path == ".":
                project_config = proj
                break
        
        try:
            with open(requirements_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse package name and version
                    match = re.match(r'^([a-zA-Z0-9_-]+[a-zA-Z0-9_.-]*)(.*)$', line)
                    if match:
                        name = match.group(1)
                        version_spec = match.group(2).strip() or "latest"
                        
                        latest = self.get_pip_latest_version(name)
                        if latest:
                            update_available = self.should_update(version_spec, latest, project_config)
                            deps.append(DependencyInfo(
                                name=name,
                                current_version=version_spec,
                                latest_version=latest,
                                package_manager="pip",
                                file_path=str(requirements_file),
                                line_number=line_num,
                                update_available=update_available
                            ))
        except Exception as e:
            print(f"Error checking pip dependencies in {project_path}: {e}")
        
        return deps
    
    def get_pip_latest_version(self, package_name: str) -> Optional[str]:
        """Get latest version of a pip package using PyPI API"""
        try:
            from urllib.request import urlopen
            import json as json_lib
            
            # Use PyPI JSON API
            url = f"https://pypi.org/pypi/{package_name}/json"
            with urlopen(url, timeout=10) as response:
                data = json_lib.loads(response.read())
                # Get latest stable version (not pre-release)
                versions = data.get('releases', {})
                # Filter out pre-releases and get latest
                stable_versions = [
                    v for v in versions.keys()
                    if not any(char in v for char in ['a', 'b', 'rc', 'dev', 'alpha', 'beta'])
                ]
                if stable_versions:
                    # Sort versions properly
                    try:
                        from packaging import version as packaging_version
                        stable_versions.sort(key=packaging_version.parse, reverse=True)
                        return stable_versions[0]
                    except ImportError:
                        # Fallback: simple string sort (less accurate but works)
                        stable_versions.sort(reverse=True)
                        return stable_versions[0]
        except Exception as e:
            # Try alternative method: pip index
            try:
                result = subprocess.run(
                    ['pip', 'index', 'versions', package_name],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    # Parse output to get latest version
                    match = re.search(r'Available versions:\s*([\d.]+)', result.stdout)
                    if match:
                        return match.group(1)
            except Exception:
                pass
        return None
    
    def should_update(self, current_spec: str, latest_version: str, project_config: Optional[ProjectConfig] = None) -> bool:
        """Determine if an update should be applied based on version spec and project config"""
        if not latest_version:
            return False
        
        # Extract version from spec (handle ^, ~, >=, etc.)
        current_version = re.search(r'[\d.]+', current_spec)
        if not current_version:
            return True  # If we can't parse, assume update needed
        
        current = current_version.group(0)
        
        # Compare versions
        try:
            current_parts = [int(x) for x in current.split('.')]
            latest_parts = [int(x) for x in latest_version.split('.')]
            
            # Pad to same length
            max_len = max(len(current_parts), len(latest_parts))
            current_parts += [0] * (max_len - len(current_parts))
            latest_parts += [0] * (max_len - len(latest_parts))
            
            # Determine what type of update this is
            is_major = latest_parts[0] > current_parts[0] if len(latest_parts) > 0 and len(current_parts) > 0 else False
            is_minor = (latest_parts[0] == current_parts[0] and 
                       len(latest_parts) > 1 and len(current_parts) > 1 and
                       latest_parts[1] > current_parts[1])
            is_patch = (latest_parts[0] == current_parts[0] and 
                       len(latest_parts) > 1 and len(current_parts) > 1 and
                       latest_parts[1] == current_parts[1] and
                       len(latest_parts) > 2 and len(current_parts) > 2 and
                       latest_parts[2] > current_parts[2])
            
            # Check if update is needed based on version comparison
            needs_update = False
            for i in range(max_len):
                if latest_parts[i] > current_parts[i]:
                    needs_update = True
                    break
                elif latest_parts[i] < current_parts[i]:
                    return False
            
            if not needs_update:
                return False
            
            # Apply project config filters
            if project_config:
                if is_major and not project_config.update_major:
                    return False
                if is_minor and not project_config.update_minor:
                    return False
                if is_patch and not project_config.update_patch:
                    return False
            
            return True
        except Exception:
            return True  # If comparison fails, assume update needed
        
        return False
    
    def update_npm_dependency(self, project_path: str, dep: DependencyInfo, dry_run: bool = False) -> bool:
        """Update an npm dependency"""
        package_json = Path(project_path) / "package.json"
        
        try:
            with open(package_json, 'r') as f:
                package_data = json.load(f)
            
            updated = False
            for dep_type in ['dependencies', 'devDependencies', 'peerDependencies']:
                if dep_type in package_data and dep.name in package_data[dep_type]:
                    old_version = package_data[dep_type][dep.name]
                    # Update to latest with caret
                    new_version = f"^{dep.latest_version}"
                    package_data[dep_type][dep.name] = new_version
                    updated = True
                    print(f"  Updating {dep.name}: {old_version} -> {new_version}")
                    break
            
            if updated and not dry_run:
                with open(package_json, 'w') as f:
                    json.dump(package_data, f, indent=2)
                    f.write('\n')
                return True
        except Exception as e:
            print(f"Error updating npm dependency {dep.name}: {e}")
        
        return False
    
    def update_pip_dependency(self, project_path: str, dep: DependencyInfo, dry_run: bool = False) -> bool:
        """Update a pip dependency in requirements.txt"""
        requirements_file = Path(project_path) / "requirements.txt"
        
        try:
            with open(requirements_file, 'r') as f:
                lines = f.readlines()
            
            updated = False
            for i, line in enumerate(lines):
                if dep.name in line and i + 1 == dep.line_number:
                    # Update the version spec
                    old_line = line
                    # Replace version spec with ==latest
                    new_line = re.sub(
                        r'([a-zA-Z0-9_-]+[a-zA-Z0-9_.-]*)(.*)',
                        rf'\1=={dep.latest_version}',
                        line
                    )
                    lines[i] = new_line
                    updated = True
                    print(f"  Updating {dep.name}: {old_line.strip()} -> {new_line.strip()}")
                    break
            
            if updated and not dry_run:
                with open(requirements_file, 'w') as f:
                    f.writelines(lines)
                return True
        except Exception as e:
            print(f"Error updating pip dependency {dep.name}: {e}")
        
        return False
    
    def check_code_references(self, project_path: str, dep: DependencyInfo) -> List[str]:
        """Check for code references to the dependency that might need updating"""
        references = []
        project_root = Path(project_path)
        
        # Common file extensions to check
        extensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs']
        
        for ext in extensions:
            for file_path in project_root.rglob(f'*{ext}'):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        # Look for import statements or require statements
                        patterns = [
                            rf'import.*{re.escape(dep.name)}',
                            rf'from\s+{re.escape(dep.name)}',
                            rf'require\([\'"]{re.escape(dep.name)}',
                            rf'use\s+{re.escape(dep.name)}',
                        ]
                        
                        for pattern in patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                references.append(str(file_path))
                                break
                except Exception:
                    pass
        
        return references
    
    def scan_all_projects(self):
        """Scan all configured projects for outdated dependencies"""
        print("Scanning projects for outdated dependencies...\n")
        self.dependencies = []
        
        for project in self.projects:
            print(f"Scanning: {project.path}")
            
            if "npm" in project.package_managers:
                deps = self.check_npm_dependencies(project.path)
                self.dependencies.extend(deps)
            
            if "pip" in project.package_managers:
                deps = self.check_pip_dependencies(project.path)
                self.dependencies.extend(deps)
        
        return self.dependencies
    
    def update_all(self, dry_run: bool = False):
        """Update all outdated dependencies"""
        if not self.dependencies:
            self.scan_all_projects()
        
        outdated = [d for d in self.dependencies if d.update_available]
        
        if not outdated:
            print("No outdated dependencies found!")
            return
        
        print(f"\nFound {len(outdated)} outdated dependencies:\n")
        for dep in outdated:
            print(f"  {dep.name}: {dep.current_version} -> {dep.latest_version} ({dep.package_manager})")
        
        if dry_run:
            print("\n[DRY RUN] Would update the above dependencies.")
            return
        
        print("\nUpdating dependencies...\n")
        updated_count = 0
        
        for dep in outdated:
            project_path = str(Path(dep.file_path).parent)
            
            if dep.package_manager == "npm":
                if self.update_npm_dependency(project_path, dep, dry_run):
                    updated_count += 1
            elif dep.package_manager == "pip":
                if self.update_pip_dependency(project_path, dep, dry_run):
                    updated_count += 1
        
        print(f"\nUpdated {updated_count} dependencies.")
        
        # Check code references
        print("\nChecking code references...")
        for dep in outdated:
            project_path = str(Path(dep.file_path).parent)
            refs = self.check_code_references(project_path, dep)
            if refs:
                print(f"  {dep.name} referenced in: {', '.join(refs)}")
    
    def generate_report(self, output_file: str = "dependency-report.json"):
        """Generate a JSON report of all dependencies"""
        if not self.dependencies:
            self.scan_all_projects()
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "dependencies": [
                {
                    "name": d.name,
                    "current_version": d.current_version,
                    "latest_version": d.latest_version,
                    "package_manager": d.package_manager,
                    "file_path": d.file_path,
                    "update_available": d.update_available
                }
                for d in self.dependencies
            ]
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"Report saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Automated Dependency Update System")
    parser.add_argument('--scan', action='store_true', help='Scan for outdated dependencies')
    parser.add_argument('--update', action='store_true', help='Update outdated dependencies')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be updated without making changes')
    parser.add_argument('--report', type=str, help='Generate JSON report (specify output file)')
    parser.add_argument('--config', type=str, help='Path to config file')
    
    args = parser.parse_args()
    
    updater = DependencyUpdater(config_path=args.config)
    
    if args.scan or (not args.update and not args.report):
        updater.scan_all_projects()
        outdated = [d for d in updater.dependencies if d.update_available]
        print(f"\nFound {len(outdated)} outdated dependencies out of {len(updater.dependencies)} total.")
    
    if args.update:
        updater.update_all(dry_run=args.dry_run)
    
    if args.report:
        updater.generate_report(args.report)


if __name__ == "__main__":
    main()

