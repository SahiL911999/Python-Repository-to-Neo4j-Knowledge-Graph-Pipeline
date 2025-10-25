#!/usr/bin/env python3
"""
Production-Ready Python Repository to Neo4j Knowledge Graph Pipeline
======================================================================
Complete end-to-end automation: Repository Analysis → JSONL Generation → Neo4j Loading

Features:
- Automatically analyzes any Python repository
- Creates organized output directories per repository
- Checks for existing data before processing
- Validates Neo4j connection and existing data
- Loads data with full error handling and verification
- Production-grade robustness and logging

Usage:
    python repo_to_neo4j.py --repo /path/to/python/repository
    python repo_to_neo4j.py --repo ~/projects/django --clean
    python repo_to_neo4j.py --repo ./my_project --exclude tests .venv --skip-neo4j

Author: Repository Analyzer System
Version: 1.0.0 Production
"""

import argparse
import ast
import hashlib
import json
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional, Any
from dataclasses import dataclass, asdict, field
from collections import defaultdict
from enum import Enum
from datetime import datetime

# Try to import Neo4j driver, install if needed
try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    print("⚠️  Neo4j driver not installed. Will skip Neo4j loading unless installed.")

# Try to load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


# ============================================================================
# ENUMS AND DATA STRUCTURES
# ============================================================================

class NodeType(str, Enum):
    """Node types in the knowledge graph"""
    REPOSITORY = "Repository"
    DIRECTORY = "Directory"
    FILE = "File"
    MODULE = "Module"
    CLASS = "Class"
    FUNCTION = "Function"
    METHOD = "Method"
    VARIABLE = "Variable"
    PARAMETER = "Parameter"
    IMPORT = "Import"
    DECORATOR = "Decorator"


class EdgeType(str, Enum):
    """Edge types representing relationships"""
    CONTAINS = "CONTAINS"
    IMPORTS = "IMPORTS"
    DEFINES = "DEFINES"
    CALLS = "CALLS"
    INHERITS = "INHERITS"
    USES = "USES"
    DECORATES = "DECORATES"
    RETURNS = "RETURNS"
    RAISES = "RAISES"
    HAS_PARAMETER = "HAS_PARAMETER"


@dataclass
class CodeMetrics:
    """Comprehensive code quality metrics"""
    lines_of_code: int
    complexity: int
    num_parameters: int
    num_returns: int
    num_branches: int
    num_loops: int
    has_docstring: bool
    num_decorators: int
    max_nesting_depth: int = 0


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def sha1_hex(s: str) -> str:
    """Generate SHA1 hash of string"""
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def stable_id(*parts: str) -> str:
    """Create stable ID from parts"""
    return sha1_hex("::".join(str(p) for p in parts))


def calculate_complexity(node: ast.AST) -> int:
    """Calculate McCabe cyclomatic complexity"""
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.For, ast.While, ast.And, ast.Or,
                             ast.ExceptHandler, ast.With, ast.Assert)):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
    return complexity


def print_header(title: str, char="="):
    """Print formatted header"""
    print("\n" + char * 80)
    print(title.center(80))
    print(char * 80)


def print_section(title: str):
    """Print section header"""
    print(f"\n{'─' * 80}")
    print(f"📌 {title}")
    print(f"{'─' * 80}")


# ============================================================================
# REPOSITORY ANALYZER
# ============================================================================

class ComprehensiveExtractor(ast.NodeVisitor):
    """Enhanced AST visitor for comprehensive code extraction with hierarchy"""
    
    def __init__(self, repo_root: Path, file_path: Path, src: str):
        self.repo_root = repo_root
        self.file_path = file_path
        self.src = src
        self.nodes: List[Dict] = []
        self.edges: List[Dict] = []
        
        # Context tracking
        self.current_scope_stack: List[str] = []
        self.current_function = None
        self.current_class = None
        
        # Name resolution
        self.imports_map: Dict[str, str] = {}
        self.defined_names: Dict[str, str] = {}
        self.scope_vars: Dict[str, Set[str]] = defaultdict(set)
        
        # Statistics
        self.stats = {
            "functions": 0, "classes": 0, "methods": 0,
            "imports": 0, "calls": 0, "variables": 0, "decorators": 0
        }
        
        self.file_id = stable_id(str(self.file_path))
    
    def _get_current_scope(self) -> str:
        return self.current_scope_stack[-1] if self.current_scope_stack else self.file_id
    
    def record_file_node(self) -> str:
        """Create file node with comprehensive metadata"""
        relpath = str(self.file_path.relative_to(self.repo_root))
        module_name = relpath.replace('/', '.').replace('\\', '.').replace('.py', '')
        lines = self.src.splitlines()
        
        node = {
            "id": self.file_id,
            "type": NodeType.FILE.value,
            "name": self.file_path.name,
            "path": str(self.file_path),
            "relpath": relpath,
            "module": module_name,
            "extension": self.file_path.suffix,
            "sha1": sha1_hex(self.src),
            "lines_of_code": len(lines),
            "size_bytes": len(self.src.encode('utf-8')),
            "language": "python",
            "encoding": "utf-8"
        }
        self.nodes.append(node)
        self.current_scope_stack.append(self.file_id)
        return self.file_id
    
    def _is_stdlib(self, module_name: str) -> bool:
        """Check if module is from standard library"""
        stdlib_modules = {
            'abc', 'argparse', 'ast', 'asyncio', 'collections', 'copy',
            'dataclasses', 'datetime', 'enum', 'functools', 'hashlib',
            'itertools', 'json', 'logging', 'math', 'os', 'pathlib',
            'pickle', 're', 'sys', 'time', 'typing', 'unittest'
        }
        base_module = module_name.split('.')[0]
        return base_module in stdlib_modules
    
    def _safe_unparse(self, node: ast.AST) -> Optional[str]:
        """Safely unparse AST node"""
        try:
            if hasattr(ast, 'unparse'):
                return ast.unparse(node)[:200]
        except:
            pass
        return None
    
    def _get_full_name(self, node: ast.Attribute) -> str:
        """Get full dotted name from Attribute node"""
        parts = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        return ".".join(reversed(parts))
    
    def visit_Import(self, node: ast.Import):
        """Extract regular imports"""
        for alias in node.names:
            target = alias.name
            import_alias = alias.asname or alias.name
            self.imports_map[import_alias] = target
            
            import_id = stable_id(self.file_id, "import", target, str(node.lineno))
            self.nodes.append({
                "id": import_id,
                "type": NodeType.IMPORT.value,
                "name": target,
                "alias": alias.asname,
                "import_type": "direct",
                "lineno": node.lineno,
                "is_stdlib": self._is_stdlib(target),
                "is_relative": False,
                "level": 0
            })
            
            self.edges.append({
                "type": EdgeType.IMPORTS.value,
                "from_id": self.file_id,
                "to_id": import_id,
                "lineno": node.lineno,
            })
            self.stats["imports"] += 1
        
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Extract from imports"""
        module = node.module or ""
        level = node.level
        
        for alias in node.names:
            target = f"{module}.{alias.name}" if module else alias.name
            import_alias = alias.asname or alias.name
            self.imports_map[import_alias] = target
            
            import_id = stable_id(self.file_id, "import", target, str(node.lineno))
            self.nodes.append({
                "id": import_id,
                "type": NodeType.IMPORT.value,
                "name": alias.name,
                "module": module,
                "full_name": target,
                "alias": alias.asname,
                "import_type": "from",
                "level": level,
                "is_relative": level > 0,
                "lineno": node.lineno,
                "is_stdlib": self._is_stdlib(module) if module else False,
            })
            
            self.edges.append({
                "type": EdgeType.IMPORTS.value,
                "from_id": self.file_id,
                "to_id": import_id,
                "lineno": node.lineno,
            })
            self.stats["imports"] += 1
        
        self.generic_visit(node)
    
    def _extract_decorators(self, node: ast.FunctionDef) -> List[Dict]:
        """Extract decorator information with parameters"""
        decorators = []
        for dec in node.decorator_list:
            dec_info = {"name": None, "args": [], "kwargs": {}}
            
            if isinstance(dec, ast.Name):
                dec_info["name"] = dec.id
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    dec_info["name"] = dec.func.id
                elif isinstance(dec.func, ast.Attribute):
                    dec_info["name"] = self._get_full_name(dec.func)
                
                dec_info["args"] = [self._safe_unparse(arg) for arg in dec.args]
                dec_info["kwargs"] = {kw.arg: self._safe_unparse(kw.value) for kw in dec.keywords}
            else:
                dec_info["name"] = self._safe_unparse(dec)
            
            decorators.append(dec_info)
            
            if dec_info["name"]:
                dec_id = stable_id(self.file_id, "decorator", dec_info["name"], str(dec.lineno))
                self.nodes.append({
                    "id": dec_id,
                    "type": NodeType.DECORATOR.value,
                    "name": dec_info["name"],
                    "lineno": dec.lineno,
                    "args": dec_info["args"],
                    "kwargs": dec_info["kwargs"]
                })
                self.stats["decorators"] += 1
        
        return decorators
    
    def _extract_parameters(self, node: ast.arguments) -> List[Dict]:
        """Extract function parameters"""
        params = []
        
        defaults_offset = len(node.args) - len(node.defaults)
        for i, arg in enumerate(node.args):
            default = None
            if i >= defaults_offset:
                default = self._safe_unparse(node.defaults[i - defaults_offset])
            
            params.append({
                "name": arg.arg,
                "type": self._safe_unparse(arg.annotation) if arg.annotation else None,
                "kind": "positional",
                "default": default,
                "position": i
            })
        
        if node.vararg:
            params.append({
                "name": node.vararg.arg,
                "type": self._safe_unparse(node.vararg.annotation) if node.vararg.annotation else None,
                "kind": "vararg",
                "default": None,
                "position": len(params)
            })
        
        kw_defaults_map = {
            kw.arg: self._safe_unparse(default) 
            for kw, default in zip(node.kwonlyargs, node.kw_defaults) 
            if default
        }
        for arg in node.kwonlyargs:
            params.append({
                "name": arg.arg,
                "type": self._safe_unparse(arg.annotation) if arg.annotation else None,
                "kind": "keyword_only",
                "default": kw_defaults_map.get(arg.arg),
                "position": len(params)
            })
        
        if node.kwarg:
            params.append({
                "name": node.kwarg.arg,
                "type": self._safe_unparse(node.kwarg.annotation) if node.kwarg.annotation else None,
                "kind": "kwarg",
                "default": None,
                "position": len(params)
            })
        
        return params
    
    def _compute_metrics(self, node: ast.FunctionDef) -> CodeMetrics:
        """Compute comprehensive code metrics"""
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", node.lineno)
        loc = end_line - start_line + 1
        
        num_returns = sum(1 for n in ast.walk(node) if isinstance(n, ast.Return))
        num_branches = sum(1 for n in ast.walk(node) if isinstance(n, (ast.If, ast.IfExp)))
        num_loops = sum(1 for n in ast.walk(node) if isinstance(n, (ast.For, ast.While)))
        
        def calc_depth(n, depth=0):
            max_d = depth
            for child in ast.iter_child_nodes(n):
                if isinstance(child, (ast.For, ast.While, ast.If, ast.With, ast.Try)):
                    max_d = max(max_d, calc_depth(child, depth + 1))
            return max_d
        
        return CodeMetrics(
            lines_of_code=loc,
            complexity=calculate_complexity(node),
            num_parameters=len(node.args.args),
            num_returns=num_returns,
            num_branches=num_branches,
            num_loops=num_loops,
            has_docstring=ast.get_docstring(node) is not None,
            num_decorators=len(node.decorator_list),
            max_nesting_depth=calc_depth(node)
        )
    
    def _get_source_snippet(self, node: ast.AST, max_lines: int = 10) -> str:
        """Extract source code snippet"""
        lines = self.src.splitlines()
        start = max(0, node.lineno - 1)
        end = min(len(lines), getattr(node, "end_lineno", node.lineno))
        snippet_lines = lines[start:end]
        
        if len(snippet_lines) > max_lines:
            snippet_lines = snippet_lines[:max_lines]
            snippet_lines.append("...")
        
        return "\n".join(snippet_lines)
    
    def _record_function(self, node: ast.FunctionDef) -> str:
        """Record function with comprehensive metadata"""
        is_method = self.current_class is not None
        parent_scope = self._get_current_scope()
        
        fn_id = stable_id(self.file_id, "function", node.name, str(node.lineno))
        
        decorators = self._extract_decorators(node)
        parameters = self._extract_parameters(node.args)
        metrics = self._compute_metrics(node)
        snippet = self._get_source_snippet(node)
        doc = ast.get_docstring(node)
        return_type = self._safe_unparse(node.returns) if node.returns else None
        
        self.defined_names[node.name] = fn_id
        node_type = NodeType.METHOD if is_method else NodeType.FUNCTION
        
        self.nodes.append({
            "id": fn_id,
            "type": node_type.value,
            "name": node.name,
            "qualified_name": f"{self.current_class}.{node.name}" if is_method else node.name,
            "is_async": isinstance(node, ast.AsyncFunctionDef),
            "is_method": is_method,
            "is_static": any(d["name"] == "staticmethod" for d in decorators),
            "is_class_method": any(d["name"] == "classmethod" for d in decorators),
            "is_property": any(d["name"] == "property" for d in decorators),
            "is_private": node.name.startswith('_') and not node.name.startswith('__'),
            "is_magic": node.name.startswith('__') and node.name.endswith('__'),
            "decorators": [d["name"] for d in decorators],
            "decorator_details": decorators,
            "parameters": parameters,
            "return_type": return_type,
            "lineno": node.lineno,
            "end_lineno": getattr(node, "end_lineno", None),
            "docstring": doc,
            "snippet": snippet[:500] if len(snippet) > 500 else snippet,
            "metrics": asdict(metrics),
        })
        
        self.edges.append({
            "type": EdgeType.DEFINES.value,
            "from_id": parent_scope,
            "to_id": fn_id,
            "relationship": "contains_method" if is_method else "contains_function"
        })
        
        for param in parameters:
            param_id = stable_id(fn_id, "param", param["name"])
            self.nodes.append({
                "id": param_id,
                "type": NodeType.PARAMETER.value,
                "name": param["name"],
                "param_type": param["type"],
                "kind": param["kind"],
                "default": param["default"],
                "position": param["position"]
            })
            
            self.edges.append({
                "type": EdgeType.HAS_PARAMETER.value,
                "from_id": fn_id,
                "to_id": param_id,
                "position": param["position"]
            })
        
        for dec in decorators:
            if dec["name"]:
                dec_id = stable_id(self.file_id, "decorator", dec["name"], str(node.lineno))
                self.edges.append({
                    "type": EdgeType.DECORATES.value,
                    "from_id": dec_id,
                    "to_id": fn_id,
                    "lineno": node.lineno
                })
        
        stat_key = "methods" if is_method else "functions"
        self.stats[stat_key] += 1
        
        return fn_id
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        prev_function = self.current_function
        fn_id = self._record_function(node)
        self.current_function = fn_id
        self.current_scope_stack.append(fn_id)
        self.generic_visit(node)
        self.current_scope_stack.pop()
        self.current_function = prev_function
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        prev_function = self.current_function
        fn_id = self._record_function(node)
        self.current_function = fn_id
        self.current_scope_stack.append(fn_id)
        self.generic_visit(node)
        self.current_scope_stack.pop()
        self.current_function = prev_function
    
    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit class definition"""
        parent_scope = self._get_current_scope()
        class_id = stable_id(self.file_path, "class", node.name, str(node.lineno))
        
        snippet = self._get_source_snippet(node)
        doc = ast.get_docstring(node)
        
        bases = [self._safe_unparse(b) for b in node.bases if self._safe_unparse(b)]
        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            else:
                dec_name = self._safe_unparse(dec)
                if dec_name:
                    decorators.append(dec_name)
        
        methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        class_vars = [n for n in node.body if isinstance(n, ast.Assign)]
        
        self.defined_names[node.name] = class_id
        
        self.nodes.append({
            "id": class_id,
            "type": NodeType.CLASS.value,
            "name": node.name,
            "lineno": node.lineno,
            "end_lineno": getattr(node, "end_lineno", None),
            "docstring": doc,
            "snippet": snippet[:500] if len(snippet) > 500 else snippet,
            "bases": bases,
            "decorators": decorators,
            "num_methods": len(methods),
            "num_class_vars": len(class_vars),
            "is_private": node.name.startswith('_'),
            "is_abstract": 'ABC' in bases or 'abc.ABC' in bases,
        })
        
        self.edges.append({
            "type": EdgeType.DEFINES.value,
            "from_id": parent_scope,
            "to_id": class_id,
            "relationship": "contains_class"
        })
        
        for base in bases:
            if base in self.defined_names:
                self.edges.append({
                    "type": EdgeType.INHERITS.value,
                    "from_id": class_id,
                    "to_id": self.defined_names[base],
                    "base_name": base
                })
            else:
                self.edges.append({
                    "type": EdgeType.INHERITS.value,
                    "from_id": class_id,
                    "to_name": base,
                    "inferred": True
                })
        
        self.stats["classes"] += 1
        
        prev_class = self.current_class
        self.current_class = node.name
        self.current_scope_stack.append(class_id)
        self.generic_visit(node)
        self.current_scope_stack.pop()
        self.current_class = prev_class
    
    def visit_Assign(self, node: ast.Assign):
        """Visit assignments to capture variables"""
        scope = self._get_current_scope()
        is_global = scope == self.file_id
        
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                is_constant = var_name.isupper()
                is_private = var_name.startswith('_')
                
                var_id = stable_id(scope, "var", var_name, str(node.lineno))
                
                value_str = None
                value_type = None
                if isinstance(node.value, ast.Constant):
                    value_str = str(node.value.value)[:100]
                    value_type = type(node.value.value).__name__
                else:
                    value_str = self._safe_unparse(node.value)
                    value_type = "complex"
                
                self.nodes.append({
                    "id": var_id,
                    "type": NodeType.VARIABLE.value,
                    "name": var_name,
                    "value": value_str,
                    "value_type": value_type,
                    "lineno": node.lineno,
                    "is_global": is_global,
                    "is_constant": is_constant,
                    "is_private": is_private,
                    "scope": "global" if is_global else "local"
                })
                
                self.edges.append({
                    "type": EdgeType.DEFINES.value,
                    "from_id": scope,
                    "to_id": var_id,
                    "relationship": "defines_variable"
                })
                
                self.scope_vars[scope].add(var_name)
                self.defined_names[var_name] = var_id
                self.stats["variables"] += 1
        
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        """Visit function calls"""
        callee = None
        if isinstance(node.func, ast.Name):
            callee = node.func.id
        elif isinstance(node.func, ast.Attribute):
            callee = self._get_full_name(node.func)
        
        caller = self._get_current_scope()
        
        if callee and caller:
            resolved_name = callee
            first_part = callee.split('.')[0]
            
            if first_part in self.imports_map:
                resolved_name = self.imports_map[first_part]
                if '.' in callee:
                    resolved_name += callee[len(first_part):]
            
            target_id = self.defined_names.get(first_part)
            
            call_edge = {
                "type": EdgeType.CALLS.value,
                "from_id": caller,
                "to_name": callee,
                "lineno": node.lineno,
                "resolved_name": resolved_name if resolved_name != callee else None,
                "num_args": len(node.args),
                "num_kwargs": len(node.keywords),
                "inferred": target_id is None
            }
            
            if target_id:
                call_edge["to_id"] = target_id
            
            self.edges.append(call_edge)
            self.stats["calls"] += 1
        
        self.generic_visit(node)
    
    def visit_Raise(self, node: ast.Raise):
        """Track raised exceptions"""
        if node.exc and self.current_function:
            exc_type = self._safe_unparse(node.exc)
            if exc_type:
                self.edges.append({
                    "type": EdgeType.RAISES.value,
                    "from_id": self.current_function,
                    "to_name": exc_type,
                    "lineno": node.lineno
                })
        self.generic_visit(node)
    
    def visit_Return(self, node: ast.Return):
        """Track return statements"""
        if node.value and self.current_function:
            return_expr = self._safe_unparse(node.value)
            if return_expr:
                self.edges.append({
                    "type": EdgeType.RETURNS.value,
                    "from_id": self.current_function,
                    "to_name": return_expr,
                    "lineno": node.lineno
                })
        self.generic_visit(node)


def extract_file(repo_root: Path, file_path: Path) -> Tuple[List[Dict], List[Dict], Dict]:
    """Extract nodes and edges from a Python file"""
    try:
        src = file_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"[ERROR] Could not read {file_path}: {e}")
        return [], [], {}
    
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        print(f"[ERROR] SyntaxError in {file_path} at line {e.lineno}: {e.msg}")
        return [], [], {}
    except Exception as e:
        print(f"[ERROR] Parse error in {file_path}: {e}")
        return [], [], {}
    
    extractor = ComprehensiveExtractor(repo_root, file_path, src)
    extractor.record_file_node()
    
    try:
        extractor.visit(tree)
    except Exception as e:
        print(f"[ERROR] Extraction error in {file_path}: {e}")
    
    return extractor.nodes, extractor.edges, extractor.stats


def build_directory_tree(root: Path, exclude: Optional[List[str]] = None) -> Tuple[Dict[Path, str], List[Dict], List[Dict]]:
    """Build directory tree structure"""
    if exclude is None:
        exclude = [".git", "__pycache__", "node_modules", ".venv", "venv", 
                  ".tox", "build", "dist", ".eggs"]
    
    dir_to_id = {}
    nodes = []
    edges = []
    
    repo_id = stable_id(str(root))
    dir_to_id[root] = repo_id
    
    nodes.append({
        "id": repo_id,
        "type": NodeType.REPOSITORY.value,
        "name": root.name,
        "path": str(root),
    })
    
    for dirpath, dirnames, filenames in os.walk(root):
        current_path = Path(dirpath)
        dirnames[:] = [d for d in dirnames if d not in exclude and not d.startswith('.')]
        
        current_id = dir_to_id.get(current_path)
        if not current_id:
            current_id = stable_id(str(current_path))
            dir_to_id[current_path] = current_id
            
            nodes.append({
                "id": current_id,
                "type": NodeType.DIRECTORY.value,
                "name": current_path.name,
                "path": str(current_path),
                "relpath": str(current_path.relative_to(root))
            })
            
            parent_path = current_path.parent
            if parent_path in dir_to_id:
                edges.append({
                    "type": EdgeType.CONTAINS.value,
                    "from_id": dir_to_id[parent_path],
                    "to_id": current_id,
                    "relationship": "contains_directory"
                })
        
        for dirname in dirnames:
            dir_path = current_path / dirname
            dir_id = stable_id(str(dir_path))
            dir_to_id[dir_path] = dir_id
            
            nodes.append({
                "id": dir_id,
                "type": NodeType.DIRECTORY.value,
                "name": dirname,
                "path": str(dir_path),
                "relpath": str(dir_path.relative_to(root))
            })
            
            edges.append({
                "type": EdgeType.CONTAINS.value,
                "from_id": current_id,
                "to_id": dir_id,
                "relationship": "contains_directory"
            })
        
        for filename in filenames:
            if filename.endswith('.py') and not filename.startswith('.'):
                file_path = current_path / filename
                file_id = stable_id(str(file_path))
                
                edges.append({
                    "type": EdgeType.CONTAINS.value,
                    "from_id": current_id,
                    "to_id": file_id,
                    "relationship": "contains_file"
                })
    
    return dir_to_id, nodes, edges


def find_python_files(root: Path, exclude: Optional[List[str]] = None) -> List[Path]:
    """Find all Python files"""
    if exclude is None:
        exclude = [".git", "__pycache__", "node_modules", ".venv", "venv"]
    
    py_files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude and not d.startswith('.')]
        for filename in filenames:
            if filename.endswith('.py') and not filename.startswith('.'):
                py_files.append(Path(dirpath) / filename)
    
    return py_files


def write_jsonl(path: Path, items: List[Dict]):
    """Write items to JSONL file"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for item in items:
            json.dump(item, f, ensure_ascii=False)
            f.write('\n')


# ============================================================================
# NEO4J LOADER
# ============================================================================

class Neo4jRepositoryLoader:
    """Loads hierarchical Python repository structure into Neo4j"""
    
    def __init__(self, uri: str, username: str, password: str):
        if not NEO4J_AVAILABLE:
            raise ImportError("Neo4j driver not installed. Run: pip install neo4j")
        
        print(f"🔐 Connecting to Neo4j...")
        try:
            self.driver = GraphDatabase.driver(
                uri, 
                auth=(username, password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=60
            )
            with self.driver.session() as session:
                session.run("RETURN 1")
            print(f"✅ Connected to Neo4j!")
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            raise
    
    def close(self):
        self.driver.close()
    
    def check_existing_data(self) -> int:
        """Check if database has existing data"""
        with self.driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) as count")
            return result.single()["count"]
    
    def clear_database(self):
        """Clear all data from database"""
        print("🗑️  Clearing existing data...")
        with self.driver.session() as session:
            while True:
                result = session.run(
                    "MATCH (n) WITH n LIMIT 10000 DETACH DELETE n RETURN count(*) as deleted"
                )
                deleted = result.single()["deleted"]
                if deleted == 0:
                    break
                print(f"   Deleted {deleted} nodes...")
        print("✅ Database cleared")
    
    def create_constraints_and_indexes(self):
        """Create constraints and indexes"""
        print("🔧 Creating constraints and indexes...")
        with self.driver.session() as session:
            constraints = [
                "CREATE CONSTRAINT repo_id IF NOT EXISTS FOR (n:Repository) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT dir_id IF NOT EXISTS FOR (n:Directory) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT file_id IF NOT EXISTS FOR (n:File) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT class_id IF NOT EXISTS FOR (n:Class) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT func_id IF NOT EXISTS FOR (n:Function) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT method_id IF NOT EXISTS FOR (n:Method) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT var_id IF NOT EXISTS FOR (n:Variable) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT param_id IF NOT EXISTS FOR (n:Parameter) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT import_id IF NOT EXISTS FOR (n:Import) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT decorator_id IF NOT EXISTS FOR (n:Decorator) REQUIRE n.id IS UNIQUE",
            ]
            
            for query in constraints:
                try:
                    session.run(query)
                except Exception:
                    pass
            
            indexes = [
                "CREATE INDEX file_name IF NOT EXISTS FOR (n:File) ON (n.name)",
                "CREATE INDEX class_name IF NOT EXISTS FOR (n:Class) ON (n.name)",
            ]
            
            for query in indexes:
                try:
                    session.run(query)
                except Exception:
                    pass
        
        print("✅ Constraints created")
    
    def load_jsonl(self, filepath: Path) -> List[Dict]:
        """Load JSONL file"""
        print(f"📂 Loading {filepath.name}...")
        items = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    items.append(json.loads(line))
        print(f"   ✅ Loaded {len(items)} items")
        return items
    
    def batch_insert_nodes(self, nodes: List[Dict], batch_size: int = 1000):
        """Insert nodes with proper handling"""
        print("📥 Inserting nodes...")
        nodes_by_type = defaultdict(list)
        
        for node in nodes:
            node_copy = node.copy()
            node_type = node_copy.pop('type')
            nodes_by_type[node_type].append(node_copy)
        
        total_inserted = 0
        
        with self.driver.session() as session:
            type_order = [
                'Repository', 'Directory', 'File', 'Module',
                'Class', 'Function', 'Method', 
                'Variable', 'Parameter', 'Decorator', 'Import'
            ]
            
            for node_type in type_order:
                if node_type not in nodes_by_type:
                    continue
                
                type_nodes = nodes_by_type[node_type]
                print(f"   📦 {node_type}: {len(type_nodes)} nodes", end=" ")
                
                for i in range(0, len(type_nodes), batch_size):
                    batch = type_nodes[i:i+batch_size]
                    
                    cleaned_batch = []
                    for node in batch:
                        cleaned_node = {}
                        for key, value in node.items():
                            if value is not None:
                                if isinstance(value, (list, dict)):
                                    cleaned_node[key] = json.dumps(value)
                                else:
                                    cleaned_node[key] = value
                        cleaned_batch.append(cleaned_node)
                    
                    query = f"""
                    UNWIND $batch AS nodeData 
                    CREATE (n:{node_type}) 
                    SET n = nodeData
                    """
                    
                    try:
                        session.run(query, batch=cleaned_batch)
                        total_inserted += len(batch)
                    except Exception as e:
                        print(f"\n      ⚠️  Batch error: {e}")
                        for single_node in cleaned_batch:
                            try:
                                session.run(query, batch=[single_node])
                                total_inserted += 1
                            except:
                                pass
                
                print("✅")
        
        print(f"✅ Inserted {total_inserted} nodes")
        return total_inserted
    
    def batch_insert_edges(self, edges: List[Dict], batch_size: int = 1000):
        """Insert edges with proper handling"""
        print("🔗 Creating relationships...")
        edges_by_type = defaultdict(list)
        
        for edge in edges:
            edges_by_type[edge['type']].append(edge)
        
        total_inserted = 0
        skipped_external = 0
        
        with self.driver.session() as session:
            for edge_type in sorted(edges_by_type.keys()):
                type_edges = edges_by_type[edge_type]
                print(f"   🔗 {edge_type}: {len(type_edges)} edges", end=" ")
                
                direct = [e for e in type_edges if ('to_id' in e or 'to' in e)]
                inferred = len(type_edges) - len(direct)
                skipped_external += inferred
                
                for i in range(0, len(direct), batch_size):
                    batch = direct[i:i+batch_size]
                    
                    normalized_batch = []
                    for edge in batch:
                        normalized = {}
                        
                        if 'from_id' in edge:
                            normalized['from'] = edge['from_id']
                        elif 'from' in edge:
                            normalized['from'] = edge['from']
                        
                        if 'to_id' in edge:
                            normalized['to'] = edge['to_id']
                        elif 'to' in edge:
                            normalized['to'] = edge['to']
                        
                        props = {}
                        for key, value in edge.items():
                            if key not in ['type', 'from', 'to', 'from_id', 'to_id', 'to_name']:
                                if value is not None:
                                    if isinstance(value, (list, dict)):
                                        props[key] = json.dumps(value)
                                    else:
                                        props[key] = value
                        
                        normalized['properties'] = props
                        normalized_batch.append(normalized)
                    
                    query = f"""
                    UNWIND $batch AS edge 
                    MATCH (from {{id: edge.from}}) 
                    MATCH (to {{id: edge.to}}) 
                    CREATE (from)-[r:{edge_type}]->(to) 
                    SET r = edge.properties
                    """
                    
                    try:
                        result = session.run(query, batch=normalized_batch)
                        summary = result.consume()
                        total_inserted += summary.counters.relationships_created
                    except Exception:
                        for single_edge in normalized_batch:
                            try:
                                result = session.run(query, batch=[single_edge])
                                summary = result.consume()
                                total_inserted += summary.counters.relationships_created
                            except:
                                pass
                
                if inferred > 0:
                    print(f"✅ (skipped {inferred} external)")
                else:
                    print("✅")
        
        print(f"✅ Created {total_inserted} relationships")
        if skipped_external > 0:
            print(f"ℹ️  Skipped {skipped_external} external references")
        
        return total_inserted


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def analyze_repository(repo_path: Path, output_dir: Path, exclude: List[str], clean: bool) -> bool:
    """Analyze repository and generate JSONL files"""
    
    print_section("Repository Analysis")
    
    if not repo_path.exists():
        print(f"❌ Repository path does not exist: {repo_path}")
        return False
    
    # Setup output paths
    nodes_path = output_dir / "nodes.jsonl"
    edges_path = output_dir / "edges.jsonl"
    stats_path = output_dir / "stats.json"
    
    # Clean if requested
    if clean:
        for p in [nodes_path, edges_path, stats_path]:
            if p.exists():
                p.unlink()
                print(f"🗑️  Cleaned {p.name}")
    
    # Check if files already exist
    if nodes_path.exists() and edges_path.exists() and not clean:
        print(f"✅ JSONL files already exist in {output_dir}/")
        print(f"   • {nodes_path.name}")
        print(f"   • {edges_path.name}")
        
        use_existing = input("   Use existing files? (yes/no): ").lower()
        if use_existing == 'yes':
            print("✅ Using existing JSONL files")
            return True
        else:
            print("🔄 Regenerating files...")
            nodes_path.unlink()
            edges_path.unlink()
            if stats_path.exists():
                stats_path.unlink()
    
    print(f"📁 Repository: {repo_path.name}")
    print(f"📂 Output: {output_dir}/")
    
    # Build directory tree
    print("\n🌳 Building directory structure...")
    dir_to_id, dir_nodes, dir_edges = build_directory_tree(repo_path, exclude)
    write_jsonl(nodes_path, dir_nodes)
    write_jsonl(edges_path, dir_edges)
    print(f"   ✅ Created {len(dir_nodes)} directory nodes")
    
    # Find Python files
    py_files = find_python_files(repo_path, exclude)
    print(f"🔍 Found {len(py_files)} Python files")
    
    if len(py_files) == 0:
        print("⚠️  No Python files found!")
        return False
    
    # Process files
    total_stats = defaultdict(int)
    errors = 0
    
    print("\n⚙️  Processing files...")
    for i, file_path in enumerate(py_files, 1):
        if i % 10 == 0 or i == len(py_files):
            print(f"   Progress: {i}/{len(py_files)} files...")
        
        nodes, edges, stats = extract_file(repo_path, file_path)
        
        if not nodes and not edges:
            errors += 1
            continue
        
        write_jsonl(nodes_path, nodes)
        write_jsonl(edges_path, edges)
        
        for key, val in stats.items():
            total_stats[key] += val
    
    # Write statistics
    final_stats = {
        "repository": str(repo_path),
        "repository_name": repo_path.name,
        "total_files": len(py_files),
        "files_processed": len(py_files) - errors,
        "files_with_errors": errors,
        "total_directories": len(dir_nodes) - 1,
        "total_functions": total_stats["functions"],
        "total_methods": total_stats["methods"],
        "total_classes": total_stats["classes"],
        "total_imports": total_stats["imports"],
        "total_calls": total_stats["calls"],
        "total_variables": total_stats["variables"],
        "total_decorators": total_stats["decorators"],
        "analysis_timestamp": datetime.now().isoformat(),
    }
    
    with stats_path.open('w', encoding='utf-8') as f:
        json.dump(final_stats, f, indent=2)
    
    # Print summary
    print("\n" + "="*80)
    print("✅ ANALYSIS COMPLETE")
    print("="*80)
    print(f"📊 Statistics:")
    print(f"   Files: {final_stats['files_processed']}/{final_stats['total_files']}")
    print(f"   Directories: {final_stats['total_directories']}")
    print(f"   Classes: {final_stats['total_classes']}")
    print(f"   Functions: {final_stats['total_functions']}")
    print(f"   Methods: {final_stats['total_methods']}")
    print(f"   Imports: {final_stats['total_imports']}")
    print(f"   Variables: {final_stats['total_variables']}")
    if errors > 0:
        print(f"   ⚠️  Errors: {errors}")
    print("="*80)
    
    return True


def load_to_neo4j(output_dir: Path, neo4j_uri: str, neo4j_user: str, neo4j_pass: str, force_clear: bool = False) -> bool:
    """Load JSONL files into Neo4j"""
    
    print_section("Neo4j Loading")
    
    if not NEO4J_AVAILABLE:
        print("❌ Neo4j driver not installed")
        print("   Install with: pip install neo4j")
        return False
    
    nodes_path = output_dir / "nodes.jsonl"
    edges_path = output_dir / "edges.jsonl"
    
    if not nodes_path.exists() or not edges_path.exists():
        print(f"❌ JSONL files not found in {output_dir}/")
        return False
    
    try:
        loader = Neo4jRepositoryLoader(neo4j_uri, neo4j_user, neo4j_pass)
        
        # Check existing data
        existing = loader.check_existing_data()
        if existing > 0:
            print(f"⚠️  Database contains {existing} nodes")
            
            if force_clear:
                loader.clear_database()
            else:
                clear = input("   Clear database before loading? (yes/no): ").lower()
                if clear == 'yes':
                    loader.clear_database()
                else:
                    print("⚠️  Loading into existing database (may cause conflicts)")
        else:
            print("✅ Database is empty")
        
        # Create constraints
        loader.create_constraints_and_indexes()
        
        # Load data
        nodes = loader.load_jsonl(nodes_path)
        edges = loader.load_jsonl(edges_path)
        
        nodes_inserted = loader.batch_insert_nodes(nodes)
        edges_inserted = loader.batch_insert_edges(edges)
        
        loader.close()
        
        print("\n" + "="*80)
        print("✅ NEO4J LOADING COMPLETE")
        print("="*80)
        print(f"📊 Summary:")
        print(f"   Nodes: {nodes_inserted}")
        print(f"   Relationships: {edges_inserted}")
        print("="*80)
        
        return True
        
    except Exception as e:
        print(f"❌ Error during Neo4j loading: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main execution"""
    
    print_header("PYTHON REPOSITORY → NEO4J KNOWLEDGE GRAPH PIPELINE")
    print("Production-Ready Code Analysis and Graph Database Loading")
    print("="*80)
    
    parser = argparse.ArgumentParser(
        description="Analyze Python repository and load into Neo4j",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Analyze and load
    python repo_to_neo4j.py --repo /path/to/repository
    
    # Clean and regenerate
    python repo_to_neo4j.py --repo ~/projects/django --clean
    
    # Only analyze (skip Neo4j)
    python repo_to_neo4j.py --repo ./my_project --skip-neo4j
    
    # Exclude directories
    python repo_to_neo4j.py --repo ~/code --exclude tests .venv docs
        """
    )
    
    parser.add_argument("--repo", required=True, help="Path to Python repository")
    parser.add_argument("--output", help="Output directory (default: graph_data/<repo_name>)")
    parser.add_argument("--exclude", nargs="+", help="Additional directories to exclude")
    parser.add_argument("--clean", action="store_true", help="Clean existing data before analysis")
    parser.add_argument("--skip-neo4j", action="store_true", help="Skip Neo4j loading")
    parser.add_argument("--force-clear", action="store_true", help="Automatically clear Neo4j database")
    
    args = parser.parse_args()
    
    # Resolve repository path
    repo_path = Path(args.repo).resolve()
    if not repo_path.exists():
        print(f"❌ Repository path does not exist: {repo_path}")
        sys.exit(1)
    
    # Setup output directory
    if args.output:
        output_dir = Path(args.output).resolve()
    else:
        output_dir = Path("graph_data") / repo_path.name
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📍 Configuration:")
    print(f"   Repository: {repo_path}")
    print(f"   Output Directory: {output_dir}")
    if args.exclude:
        print(f"   Excluded: {', '.join(args.exclude)}")
    
    # Step 1: Analyze Repository
    success = analyze_repository(
        repo_path=repo_path,
        output_dir=output_dir,
        exclude=args.exclude or [],
        clean=args.clean
    )
    
    if not success:
        print("❌ Analysis failed")
        sys.exit(1)
    
    # Step 2: Load to Neo4j (if not skipped)
    if not args.skip_neo4j:
        # Get Neo4j credentials
        neo4j_uri = os.environ.get("NEO4J_URI")
        neo4j_user = os.environ.get("NEO4J_USERNAME")
        neo4j_pass = os.environ.get("NEO4J_PASSWORD")
        
        if not all([neo4j_uri, neo4j_user, neo4j_pass]):
            print("\n⚠️  Neo4j credentials not found in environment")
            print("   Set: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD")
            print("   Or create a .env file with these variables")
            
            skip = input("\n   Skip Neo4j loading? (yes/no): ").lower()
            if skip != 'yes':
                sys.exit(1)
        else:
            success = load_to_neo4j(
                output_dir=output_dir,
                neo4j_uri=neo4j_uri,
                neo4j_user=neo4j_user,
                neo4j_pass=neo4j_pass,
                force_clear=args.force_clear
            )
            
            if not success:
                print("❌ Neo4j loading failed")
                sys.exit(1)
            
            print(f"\n💡 Next Steps:")
            print(f"   1. Open Neo4j Browser")
            print(f"   2. Try: MATCH path = (r:Repository)-[:CONTAINS|DEFINES*1..4]->(n) RETURN path LIMIT 200")
            print(f"   3. Explore your repository's knowledge graph!")
    
    print("\n" + "="*80)
    print("✅ PIPELINE COMPLETE!")
    print("="*80)


if __name__ == "__main__":
    main()
