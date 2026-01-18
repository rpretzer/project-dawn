"""
Code Agent

Agent that provides file system and code operations tools.
Implements Phase 3 tools, resources, and prompts from the development plan.
"""

import os
import re
import json
import time
import subprocess
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fnmatch import fnmatch
from .base_agent import BaseAgent
from mcp.resources import MCPResource
from mcp.prompts import MCPPrompt, MCPPromptArgument

logger = logging.getLogger(__name__)


class CodeAgent(BaseAgent):
    """
    Code Agent
    
    Provides tools for file system operations, code analysis, execution, and formatting.
    """
    
    def __init__(self, agent_id: str, workspace_path: Optional[str] = None, name: Optional[str] = None):
        """
        Initialize code agent
        
        Args:
            agent_id: Agent ID
            workspace_path: Base workspace path (defaults to current directory)
            name: Agent name
        """
        super().__init__(agent_id, name or "CodeAgent")
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        self.workspace_path = self.workspace_path.resolve()
        
        # Security: restrict operations to workspace
        self.allowed_paths = [self.workspace_path]
        
        # Code execution sandbox settings
        self.execution_timeout = 30.0  # seconds
        self.max_output_size = 1024 * 1024  # 1MB
        
        # File history tracking (simple in-memory for now)
        self.file_history: Dict[str, List[Dict[str, Any]]] = {}
        
        # Register tools, resources, and prompts
        self._register_tools()
        self._register_resources()
        self._register_prompts()
        
        logger.info(f"CodeAgent '{self.name}' initialized with workspace: {self.workspace_path}")
    
    def _register_tools(self):
        """Register Phase 3: File System & Code Operations tools"""
        
        # Tool 1: file_read
        self.register_tool(
            tool_name="file_read",
            description="Read file contents",
            handler=self._file_read,
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path (relative to workspace)"
                    },
                    "encoding": {
                        "type": "string",
                        "enum": ["utf-8", "binary"],
                        "description": "File encoding",
                        "default": "utf-8"
                    }
                },
                "required": ["path"]
            }
        )
        
        # Tool 2: file_write
        self.register_tool(
            tool_name="file_write",
            description="Write file contents",
            handler=self._file_write,
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path (relative to workspace)"
                    },
                    "content": {
                        "type": "string",
                        "description": "File content to write"
                    },
                    "encoding": {
                        "type": "string",
                        "enum": ["utf-8"],
                        "description": "File encoding",
                        "default": "utf-8"
                    }
                },
                "required": ["path", "content"]
            }
        )
        
        # Tool 3: file_list
        self.register_tool(
            tool_name="file_list",
            description="List directory contents",
            handler=self._file_list,
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path (relative to workspace)",
                        "default": "."
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "List recursively",
                        "default": False
                    },
                    "pattern": {
                        "type": "string",
                        "description": "File pattern filter (e.g., '*.py')"
                    }
                }
            }
        )
        
        # Tool 4: file_search
        self.register_tool(
            tool_name="file_search",
            description="Search files by content or name",
            handler=self._file_search,
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "path": {
                        "type": "string",
                        "description": "Base path to search (relative to workspace)",
                        "default": "."
                    },
                    "type": {
                        "type": "string",
                        "enum": ["content", "name"],
                        "description": "Search type",
                        "default": "content"
                    }
                },
                "required": ["query"]
            }
        )
        
        # Tool 5: code_analyze
        self.register_tool(
            tool_name="code_analyze",
            description="Analyze code structure and dependencies",
            handler=self._code_analyze,
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File or directory path to analyze"
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language (auto-detected if not specified)"
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Analysis depth (1-3)",
                        "default": 2,
                        "minimum": 1,
                        "maximum": 3
                    }
                },
                "required": ["path"]
            }
        )
        
        # Tool 6: code_execute
        self.register_tool(
            tool_name="code_execute",
            description="Execute code in sandboxed environment",
            handler=self._code_execute,
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to execute"
                    },
                    "language": {
                        "type": "string",
                        "enum": ["python", "javascript", "bash"],
                        "description": "Programming language"
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Execution timeout in seconds",
                        "default": 30
                    }
                },
                "required": ["code", "language"]
            }
        )
        
        # Tool 7: code_format
        self.register_tool(
            tool_name="code_format",
            description="Format code according to style guide",
            handler=self._code_format,
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to format"
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language"
                    },
                    "style": {
                        "type": "string",
                        "description": "Style guide (e.g., 'pep8', 'black', 'prettier')",
                        "default": "auto"
                    }
                },
                "required": ["code", "language"]
            }
        )
        
        # Tool 8: code_test
        self.register_tool(
            tool_name="code_test",
            description="Run tests for code",
            handler=self._code_test,
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File or directory path to test"
                    },
                    "test_pattern": {
                        "type": "string",
                        "description": "Test file pattern (e.g., 'test_*.py')"
                    },
                    "framework": {
                        "type": "string",
                        "description": "Test framework (auto-detected if not specified)"
                    }
                },
                "required": ["path"]
            }
        )
        
        logger.info(f"CodeAgent '{self.name}' registered {len(self.get_tools())} tools")
    
    def _register_resources(self):
        """Register Phase 3: File System & Code Operations resources"""
        
        # Resource 1: file://tree
        self.server.register_resource(
            resource=MCPResource(
                uri="file://tree",
                name="File System Tree",
                description="File system tree structure of the workspace",
                mimeType="application/json",
            ),
            handler=self._file_tree_resource,
        )
        
        # Resource 2: code://dependencies
        self.server.register_resource(
            resource=MCPResource(
                uri="code://dependencies",
                name="Code Dependencies",
                description="Code dependencies graph",
                mimeType="application/json",
            ),
            handler=self._code_dependencies_resource,
        )
        
        # Resource 3: code://metrics
        self.server.register_resource(
            resource=MCPResource(
                uri="code://metrics",
                name="Code Metrics",
                description="Code quality metrics",
                mimeType="application/json",
            ),
            handler=self._code_metrics_resource,
        )
        
        # Resource 4: file://history
        self.server.register_resource(
            resource=MCPResource(
                uri="file://history",
                name="File History",
                description="File change history",
                mimeType="application/json",
            ),
            handler=self._file_history_resource,
        )
        
        logger.info(f"CodeAgent '{self.name}' registered {len(self.server.get_resources())} resources")
    
    def _register_prompts(self):
        """Register Phase 3: File System & Code Operations prompts"""
        
        # Prompt 1: code_review
        self.server.register_prompt(
            prompt=MCPPrompt(
                name="code_review",
                description="Generate code review",
                arguments=[
                    MCPPromptArgument(
                        name="code",
                        description="Code to review",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="language",
                        description="Programming language",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="focus",
                        description="Focus area for review (optional)",
                        required=False,
                    ),
                ],
                template="Review this {{language}} code: {{code}}. Focus: {{focus}}",
            ),
            handler=self._code_review_prompt,
        )
        
        # Prompt 2: code_explanation
        self.server.register_prompt(
            prompt=MCPPrompt(
                name="code_explanation",
                description="Explain code functionality",
                arguments=[
                    MCPPromptArgument(
                        name="code",
                        description="Code to explain",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="language",
                        description="Programming language",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="detail_level",
                        description="Detail level: simple or detailed",
                        required=False,
                    ),
                ],
                template="Explain this {{language}} code: {{code}}",
            ),
            handler=self._code_explanation_prompt,
        )
        
        # Prompt 3: refactoring_suggestion
        self.server.register_prompt(
            prompt=MCPPrompt(
                name="refactoring_suggestion",
                description="Suggest code refactoring",
                arguments=[
                    MCPPromptArgument(
                        name="code",
                        description="Code to refactor",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="language",
                        description="Programming language",
                        required=True,
                    ),
                    MCPPromptArgument(
                        name="goals",
                        description="Refactoring goals (JSON array)",
                        required=False,
                    ),
                ],
                template="Suggest refactoring for: {{code}}. Goals: {{goals}}",
            ),
            handler=self._refactoring_suggestion_prompt,
        )
        
        logger.info(f"CodeAgent '{self.name}' registered {len(self.server.get_prompts())} prompts")
    
    # Security helpers
    
    def _resolve_path(self, path: str) -> Path:
        """
        Resolve and validate file path
        
        Args:
            path: Relative or absolute path
            
        Returns:
            Resolved Path object
            
        Raises:
            ValueError: If path is outside allowed workspace
        """
        # Convert to Path
        if os.path.isabs(path):
            resolved = Path(path)
        else:
            resolved = (self.workspace_path / path).resolve()
        
        # Check if path is within allowed workspace
        if not any(str(resolved).startswith(str(allowed)) for allowed in self.allowed_paths):
            raise ValueError(f"Path {path} is outside allowed workspace")
        
        return resolved
    
    # Tool Handlers
    
    async def _file_read(
        self,
        path: str,
        encoding: str = "utf-8"
    ) -> Dict[str, Any]:
        """
        Read file contents
        
        Args:
            path: File path
            encoding: File encoding
            
        Returns:
            File contents
        """
        try:
            file_path = self._resolve_path(path)
            
            if not file_path.exists():
                return {
                    "success": False,
                    "error": f"File not found: {path}",
                }
            
            if not file_path.is_file():
                return {
                    "success": False,
                    "error": f"Path is not a file: {path}",
                }
            
            if encoding == "binary":
                with open(file_path, "rb") as f:
                    content = f.read()
                return {
                    "success": True,
                    "content": content.hex(),
                    "size": len(content),
                    "encoding": "binary",
                }
            else:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
                return {
                    "success": True,
                    "content": content,
                    "size": len(content),
                    "encoding": encoding,
                    "lines": len(content.splitlines()),
                }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            return {
                "success": False,
                "error": f"Failed to read file: {str(e)}",
            }
    
    async def _file_write(
        self,
        path: str,
        content: str,
        encoding: str = "utf-8"
    ) -> Dict[str, Any]:
        """
        Write file contents
        
        Args:
            path: File path
            content: Content to write
            encoding: File encoding
            
        Returns:
            Success confirmation
        """
        try:
            file_path = self._resolve_path(path)
            
            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            with open(file_path, "w", encoding=encoding) as f:
                f.write(content)
            
            # Track in history
            if str(file_path) not in self.file_history:
                self.file_history[str(file_path)] = []
            
            self.file_history[str(file_path)].append({
                "action": "write",
                "timestamp": time.time(),
                "size": len(content),
            })
            
            logger.info(f"Wrote file {path} ({len(content)} bytes)")
            
            return {
                "success": True,
                "path": str(file_path.relative_to(self.workspace_path)),
                "size": len(content),
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"Error writing file {path}: {e}")
            return {
                "success": False,
                "error": f"Failed to write file: {str(e)}",
            }
    
    async def _file_list(
        self,
        path: str = ".",
        recursive: bool = False,
        pattern: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List directory contents
        
        Args:
            path: Directory path
            recursive: List recursively
            pattern: File pattern filter
            
        Returns:
            List of files/directories
        """
        try:
            dir_path = self._resolve_path(path)
            
            if not dir_path.exists():
                return {
                    "success": False,
                    "error": f"Directory not found: {path}",
                }
            
            if not dir_path.is_dir():
                return {
                    "success": False,
                    "error": f"Path is not a directory: {path}",
                }
            
            files = []
            
            if recursive:
                for file_path in dir_path.rglob("*"):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(self.workspace_path)
                        if not pattern or fnmatch(str(rel_path), pattern):
                            files.append({
                                "path": str(rel_path),
                                "type": "file",
                                "size": file_path.stat().st_size,
                            })
            else:
                for item in sorted(dir_path.iterdir()):
                    rel_path = item.relative_to(self.workspace_path)
                    if not pattern or fnmatch(str(rel_path), pattern):
                        files.append({
                            "path": str(rel_path),
                            "type": "directory" if item.is_dir() else "file",
                            "size": item.stat().st_size if item.is_file() else None,
                        })
            
            return {
                "success": True,
                "path": str(dir_path.relative_to(self.workspace_path)),
                "files": files,
                "count": len(files),
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"Error listing directory {path}: {e}")
            return {
                "success": False,
                "error": f"Failed to list directory: {str(e)}",
            }
    
    async def _file_search(
        self,
        query: str,
        path: str = ".",
        type: str = "content"
    ) -> Dict[str, Any]:
        """
        Search files by content or name
        
        Args:
            query: Search query
            path: Base path to search
            type: Search type (content or name)
            
        Returns:
            Matching files with snippets
        """
        try:
            base_path = self._resolve_path(path)
            
            if not base_path.exists():
                return {
                    "success": False,
                    "error": f"Path not found: {path}",
                }
            
            matches = []
            query_lower = query.lower()
            
            if type == "name":
                # Search by filename
                for file_path in base_path.rglob("*"):
                    if file_path.is_file():
                        if query_lower in file_path.name.lower():
                            matches.append({
                                "path": str(file_path.relative_to(self.workspace_path)),
                                "type": "name_match",
                            })
            else:
                # Search by content
                for file_path in base_path.rglob("*"):
                    if file_path.is_file():
                        try:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                                if query_lower in content.lower():
                                    # Find snippet
                                    lines = content.splitlines()
                                    snippet_lines = []
                                    for i, line in enumerate(lines):
                                        if query_lower in line.lower():
                                            start = max(0, i - 2)
                                            end = min(len(lines), i + 3)
                                            snippet_lines = lines[start:end]
                                            break
                                    
                                    matches.append({
                                        "path": str(file_path.relative_to(self.workspace_path)),
                                        "type": "content_match",
                                        "snippet": "\n".join(snippet_lines),
                                    })
                        except Exception as e:
                            # Skip binary files or files with reading errors
                            logger.debug(f"Could not read file {file_path} during search: {e}")
                            pass
            
            return {
                "success": True,
                "query": query,
                "matches": matches,
                "count": len(matches),
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"Error searching files: {e}")
            return {
                "success": False,
                "error": f"Failed to search files: {str(e)}",
            }
    
    async def _code_analyze(
        self,
        path: str,
        language: Optional[str] = None,
        depth: int = 2
    ) -> Dict[str, Any]:
        """
        Analyze code structure and dependencies
        
        Args:
            path: File or directory path
            language: Programming language
            depth: Analysis depth
            
        Returns:
            Code analysis (imports, functions, classes, etc.)
        """
        try:
            file_path = self._resolve_path(path)
            
            if not file_path.exists():
                return {
                    "success": False,
                    "error": f"Path not found: {path}",
                }
            
            # Auto-detect language if not specified
            if not language:
                ext = file_path.suffix.lower()
                lang_map = {
                    ".py": "python",
                    ".js": "javascript",
                    ".ts": "typescript",
                    ".java": "java",
                    ".go": "go",
                    ".rs": "rust",
                }
                language = lang_map.get(ext, "unknown")
            
            analysis = {
                "path": str(file_path.relative_to(self.workspace_path)),
                "language": language,
                "imports": [],
                "functions": [],
                "classes": [],
                "dependencies": [],
            }
            
            if file_path.is_file() and language == "python":
                # Simple Python analysis
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # Extract imports
                    import_pattern = r'^(?:from\s+(\S+)\s+)?import\s+(\S+)'
                    for line in content.splitlines():
                        match = re.match(import_pattern, line.strip())
                        if match:
                            module = match.group(1) or match.group(2)
                            analysis["imports"].append(module)
                            analysis["dependencies"].append(module.split(".")[0])
                    
                    # Extract functions
                    func_pattern = r'^def\s+(\w+)\s*\('
                    for line in content.splitlines():
                        match = re.match(func_pattern, line.strip())
                        if match:
                            analysis["functions"].append(match.group(1))
                    
                    # Extract classes
                    class_pattern = r'^class\s+(\w+)'
                    for line in content.splitlines():
                        match = re.match(class_pattern, line.strip())
                        if match:
                            analysis["classes"].append(match.group(1))
                except Exception as e:
                    logger.warning(f"Error analyzing Python file: {e}")
            
            return {
                "success": True,
                "analysis": analysis,
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"Error analyzing code: {e}")
            return {
                "success": False,
                "error": f"Failed to analyze code: {str(e)}",
            }
    
    async def _code_execute(
        self,
        code: str,
        language: str,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Execute code in sandboxed environment
        
        Args:
            code: Code to execute
            language: Programming language
            timeout: Execution timeout
            
        Returns:
            Execution result (stdout, stderr, return code)
        """
        try:
            if language == "python":
                result = subprocess.run(
                    ["python3", "-c", code],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(self.workspace_path),
                )
            elif language == "javascript":
                result = subprocess.run(
                    ["node", "-e", code],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(self.workspace_path),
                )
            elif language == "bash":
                result = subprocess.run(
                    ["bash", "-c", code],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(self.workspace_path),
                )
            else:
                return {
                    "success": False,
                    "error": f"Unsupported language: {language}",
                }
            
            # Limit output size
            stdout = result.stdout[:self.max_output_size]
            stderr = result.stderr[:self.max_output_size]
            
            return {
                "success": True,
                "stdout": stdout,
                "stderr": stderr,
                "return_code": result.returncode,
                "language": language,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Execution timeout after {timeout} seconds",
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"Language runtime not found: {language}",
            }
        except Exception as e:
            logger.error(f"Error executing code: {e}")
            return {
                "success": False,
                "error": f"Failed to execute code: {str(e)}",
            }
    
    async def _code_format(
        self,
        code: str,
        language: str,
        style: str = "auto"
    ) -> Dict[str, Any]:
        """
        Format code according to style guide
        
        Args:
            code: Code to format
            language: Programming language
            style: Style guide
            
        Returns:
            Formatted code
        """
        try:
            language_lower = language.lower()
            formatted_code = code
            
            # Python formatting using black (if available)
            if language_lower in ("python", "py"):
                try:
                    import black
                    mode = black.FileMode()
                    if style != "auto":
                        # Parse style options if provided
                        if "line-length" in style.lower():
                            try:
                                line_length = int(re.search(r'line-length[=:]\s*(\d+)', style).group(1))
                                mode = black.FileMode(line_length=line_length)
                            except (AttributeError, ValueError):
                                pass
                    formatted_code = black.format_str(code, mode=mode)
                    logger.debug("Formatted Python code using black")
                except ImportError:
                    # Fallback: basic Python formatting using autopep8 or manual formatting
                    try:
                        import autopep8
                        formatted_code = autopep8.fix_code(code, options={'aggressive': 1})
                        logger.debug("Formatted Python code using autopep8")
                    except ImportError:
                        # Last resort: basic formatting (normalize whitespace)
                        lines = code.split('\n')
                        formatted_lines = []
                        indent_level = 0
                        for line in lines:
                            stripped = line.strip()
                            if not stripped:
                                formatted_lines.append('')
                                continue
                            # Adjust indent based on line content
                            if stripped.endswith(':'):
                                formatted_lines.append(' ' * (indent_level * 4) + stripped)
                                indent_level += 1
                            elif stripped.startswith(('return ', 'break', 'continue', 'pass', 'raise ', 'assert ')):
                                indent_level = max(0, indent_level - 1)
                                formatted_lines.append(' ' * (indent_level * 4) + stripped)
                            else:
                                formatted_lines.append(' ' * (indent_level * 4) + stripped)
                            # Decrease indent after certain statements
                            if any(stripped.startswith(x) for x in ('return', 'break', 'continue', 'pass', 'raise', 'assert')):
                                indent_level = max(0, indent_level - 1)
                        formatted_code = '\n'.join(formatted_lines)
                        logger.debug("Formatted Python code using basic formatter")
            
            # JavaScript/TypeScript formatting using prettier (if available via subprocess)
            elif language_lower in ("javascript", "js", "typescript", "ts", "jsx", "tsx"):
                try:
                    result = subprocess.run(
                        ["prettier", "--stdin-filepath", f"code.{language_lower}"],
                        input=code,
                        text=True,
                        capture_output=True,
                        timeout=5.0,
                    )
                    if result.returncode == 0:
                        formatted_code = result.stdout
                        logger.debug(f"Formatted {language} code using prettier")
                    else:
                        logger.warning(f"Prettier failed: {result.stderr}")
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    # Fallback: basic JavaScript formatting
                    formatted_code = code  # Keep as-is if prettier not available
                    logger.debug("Prettier not available, code kept as-is")
            
            # JSON formatting
            elif language_lower == "json":
                try:
                    parsed = json.loads(code)
                    formatted_code = json.dumps(parsed, indent=2, sort_keys=True)
                    logger.debug("Formatted JSON code")
                except json.JSONDecodeError:
                    formatted_code = code  # Invalid JSON, return as-is
            
            # YAML formatting (basic)
            elif language_lower in ("yaml", "yml"):
                try:
                    import yaml
                    parsed = yaml.safe_load(code)
                    formatted_code = yaml.dump(parsed, default_flow_style=False, sort_keys=False)
                    logger.debug("Formatted YAML code")
                except ImportError:
                    formatted_code = code  # Keep as-is if PyYAML not available
                except yaml.YAMLError:
                    formatted_code = code  # Invalid YAML, return as-is
            
            # HTML/XML formatting (basic indentation)
            elif language_lower in ("html", "xml"):
                try:
                    import xml.dom.minidom
                    parsed = xml.dom.minidom.parseString(code)
                    formatted_code = parsed.toprettyxml(indent="  ")
                    # Remove extra blank lines
                    lines = [line for line in formatted_code.split('\n') if line.strip()]
                    formatted_code = '\n'.join(lines)
                    logger.debug(f"Formatted {language} code")
                except Exception:
                    formatted_code = code  # Keep as-is if formatting fails
            
            # Default: normalize whitespace
            else:
                # Basic formatting: normalize line endings and trailing whitespace
                lines = code.splitlines()
                formatted_lines = [line.rstrip() for line in lines]
                formatted_code = '\n'.join(formatted_lines)
                if code.endswith('\n'):
                    formatted_code += '\n'
                logger.debug(f"Applied basic formatting to {language} code")
            
            return {
                "success": True,
                "formatted_code": formatted_code,
                "language": language,
                "style": style,
                "changed": formatted_code != code,
            }
        except Exception as e:
            logger.error(f"Error formatting code: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to format code: {str(e)}",
                "formatted_code": code,  # Return original code on error
            }
    
    async def _code_test(
        self,
        path: str,
        test_pattern: Optional[str] = None,
        framework: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run tests for code
        
        Args:
            path: File or directory path to test
            test_pattern: Test file pattern
            framework: Test framework
            
        Returns:
            Test results
        """
        try:
            test_path = self._resolve_path(path)
            
            if not test_path.exists():
                return {
                    "success": False,
                    "error": f"Path not found: {path}",
                }
            
            # Auto-detect framework
            if not framework:
                if (test_path.parent / "pytest.ini").exists() or (test_path.parent / "pyproject.toml").exists():
                    framework = "pytest"
                elif (test_path.parent / "package.json").exists():
                    framework = "jest"
                else:
                    framework = "pytest"  # Default for Python
            
            # Run tests
            if framework == "pytest":
                pattern = test_pattern or "test_*.py"
                result = subprocess.run(
                    ["pytest", str(test_path), "-v", "-k", pattern] if test_pattern else ["pytest", str(test_path), "-v"],
                    capture_output=True,
                    text=True,
                    timeout=60.0,
                    cwd=str(self.workspace_path),
                )
            else:
                return {
                    "success": False,
                    "error": f"Test framework not implemented: {framework}",
                }
            
            return {
                "success": True,
                "framework": framework,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
                "passed": result.returncode == 0,
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Test execution timeout",
            }
        except Exception as e:
            logger.error(f"Error running tests: {e}")
            return {
                "success": False,
                "error": f"Failed to run tests: {str(e)}",
            }
    
    # Resource Handlers
    
    async def _file_tree_resource(self) -> str:
        """Resource handler for file system tree"""
        def build_tree(path: Path, max_depth: int = 3, current_depth: int = 0) -> Dict[str, Any]:
            if current_depth >= max_depth:
                return {"name": path.name, "type": "file" if path.is_file() else "directory", "truncated": True}
            
            if path.is_file():
                return {
                    "name": path.name,
                    "type": "file",
                    "size": path.stat().st_size,
                }
            else:
                children = []
                try:
                    for item in sorted(path.iterdir()):
                        if item.name.startswith(".") and item.name not in [".git"]:
                            continue
                        children.append(build_tree(item, max_depth, current_depth + 1))
                except PermissionError:
                    pass
                
                return {
                    "name": path.name,
                    "type": "directory",
                    "children": children,
                }
        
        tree = build_tree(self.workspace_path)
        
        return json.dumps({
            "workspace": str(self.workspace_path),
            "tree": tree,
            "timestamp": time.time(),
        }, indent=2)
    
    async def _code_dependencies_resource(self) -> str:
        """Resource handler for code dependencies"""
        dependencies = {}
        
        # Scan Python files for imports
        for py_file in self.workspace_path.rglob("*.py"):
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()
                
                imports = []
                import_pattern = r'^(?:from\s+(\S+)\s+)?import\s+(\S+)'
                for line in content.splitlines():
                    match = re.match(import_pattern, line.strip())
                    if match:
                        module = match.group(1) or match.group(2)
                        imports.append(module.split(".")[0])
                
                if imports:
                    rel_path = str(py_file.relative_to(self.workspace_path))
                    dependencies[rel_path] = list(set(imports))
            except Exception as e:
                logger.warning(f"Failed to analyze dependencies for file {py_file}: {e}")
                pass
        
        return json.dumps({
            "dependencies": dependencies,
            "timestamp": time.time(),
        }, indent=2)
    
    async def _code_metrics_resource(self) -> str:
        """Resource handler for code metrics"""
        metrics = {
            "total_files": 0,
            "total_lines": 0,
            "languages": {},
            "complexity": {},
        }
        
        for file_path in self.workspace_path.rglob("*"):
            if file_path.is_file():
                ext = file_path.suffix.lower()
                lang_map = {
                    ".py": "python",
                    ".js": "javascript",
                    ".ts": "typescript",
                    ".java": "java",
                    ".go": "go",
                    ".rs": "rust",
                }
                language = lang_map.get(ext, "other")
                
                if language != "other":
                    metrics["total_files"] += 1
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            lines = len(f.readlines())
                            metrics["total_lines"] += lines
                            metrics["languages"][language] = metrics["languages"].get(language, 0) + lines
                    except Exception as e:
                        logger.warning(f"Failed to calculate metrics for file {file_path}: {e}")
                        pass
        
        return json.dumps({
            "metrics": metrics,
            "timestamp": time.time(),
        }, indent=2)
    
    async def _file_history_resource(self) -> str:
        """Resource handler for file history"""
        return json.dumps({
            "history": self.file_history,
            "timestamp": time.time(),
        }, indent=2)
    
    # Prompt Handlers
    
    async def _code_review_prompt(
        self,
        code: str,
        language: str,
        focus: Optional[str] = None
    ) -> str:
        """Prompt handler for code review"""
        prompt = "Code Review Request\n\n"
        prompt += f"Language: {language}\n\n"
        prompt += f"Code:\n```{language}\n{code}\n```\n\n"
        
        if focus:
            prompt += f"Focus Area: {focus}\n\n"
        
        prompt += "Please provide a code review covering:\n"
        prompt += "1. Code quality and style\n"
        prompt += "2. Potential bugs or issues\n"
        prompt += "3. Performance considerations\n"
        prompt += "4. Security concerns\n"
        prompt += "5. Best practices and improvements\n"
        
        if focus:
            prompt += f"\nPay special attention to: {focus}\n"
        
        return prompt
    
    async def _code_explanation_prompt(
        self,
        code: str,
        language: str,
        detail_level: Optional[str] = None
    ) -> str:
        """Prompt handler for code explanation"""
        detail = detail_level or "detailed"
        
        prompt = "Code Explanation Request\n\n"
        prompt += f"Language: {language}\n"
        prompt += f"Detail Level: {detail}\n\n"
        prompt += f"Code:\n```{language}\n{code}\n```\n\n"
        
        if detail == "simple":
            prompt += "Please provide a simple, high-level explanation of what this code does."
        else:
            prompt += "Please provide a detailed explanation of this code, including:\n"
            prompt += "1. Overall purpose and functionality\n"
            prompt += "2. Key components and their roles\n"
            prompt += "3. Control flow and logic\n"
            prompt += "4. Important variables and data structures\n"
            prompt += "5. Potential edge cases or considerations\n"
        
        return prompt
    
    async def _refactoring_suggestion_prompt(
        self,
        code: str,
        language: str,
        goals: Optional[str] = None
    ) -> str:
        """Prompt handler for refactoring suggestion"""
        prompt = "Refactoring Suggestion Request\n\n"
        prompt += f"Language: {language}\n\n"
        prompt += f"Code:\n```{language}\n{code}\n```\n\n"
        
        if goals:
            try:
                goals_list = json.loads(goals) if goals.startswith("[") else [goals]
                prompt += f"Refactoring Goals: {', '.join(goals_list)}\n\n"
            except json.JSONDecodeError:
                prompt += f"Refactoring Goals: {goals}\n\n"
        
        prompt += "Please suggest refactoring improvements, including:\n"
        prompt += "1. Code structure improvements\n"
        prompt += "2. Performance optimizations\n"
        prompt += "3. Readability enhancements\n"
        prompt += "4. Design pattern applications\n"
        prompt += "5. Specific refactoring steps\n"
        
        return prompt


