#!/usr/bin/env python3
"""Public API breaking change verification script for CI.

Compares the public method signatures of GLinet on the current branch (HEAD)
against the base branch (origin/master).

Flags breaking changes:
1. Removal or renaming of any public method.
2. Removal of any existing parameters from a public method.
3. Addition of new required parameters without default values.
4. Changing an optional parameter into a required parameter.
"""

import ast
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def get_base_glinet_source() -> str | None:
    """Retrieve the source code of gli4py/glinet.py from origin/master or master."""
    for ref in ["origin/master", "master"]:
        try:
            res = subprocess.run(
                ["git", "show", f"{ref}:gli4py/glinet.py"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            return res.stdout
        except subprocess.CalledProcessError:
            continue
    return None


def extract_public_methods(
    source: str,
) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Parse python source and extract public methods of class GLinet."""
    tree = ast.parse(source)
    methods: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "GLinet":
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    if not item.name.startswith("_"):
                        methods[item.name] = item
    return methods


def get_param_info(func: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, bool]:
    """Return dict mapping param name to bool indicating whether it has a default value."""
    args = func.args
    # Position of args that have defaults:
    # args.defaults corresponds to the LAST len(args.defaults) of args.args
    num_defaults = len(args.defaults)
    num_args = len(args.args)
    first_default_idx = num_args - num_defaults

    param_info: dict[str, bool] = {}
    for idx, arg in enumerate(args.args):
        if arg.arg == "self":
            continue
        has_default = idx >= first_default_idx
        param_info[arg.arg] = has_default

    # Keyword-only args
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        param_info[arg.arg] = default is not None

    return param_info


def compare_apis(
    base_methods: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    head_methods: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
) -> list[str]:
    """Detect breaking changes between base and head GLinet class."""
    errors: list[str] = []

    for method_name, base_func in base_methods.items():
        if method_name not in head_methods:
            errors.append(
                f"Breaking Change: Public method '{method_name}()' was removed or renamed."
            )
            continue

        head_func = head_methods[method_name]
        base_params = get_param_info(base_func)
        head_params = get_param_info(head_func)

        # 1. Check for removed parameters
        for param in base_params:
            if param not in head_params:
                errors.append(
                    f"Breaking Change in '{method_name}()': Parameter '{param}' was removed."
                )

        # 2. Check for optional parameters made required
        for param, had_default in base_params.items():
            if had_default and param in head_params and not head_params[param]:
                errors.append(
                    f"Breaking Change in '{method_name}()': "
                    f"Optional parameter '{param}' was changed to required."
                )

        # 3. Check for newly added required parameters (without defaults)
        for param, has_default in head_params.items():
            if param not in base_params and not has_default:
                errors.append(
                    f"Breaking Change in '{method_name}()': "
                    f"New parameter '{param}' was added without a default value."
                )

    return errors


def main() -> int:
    """Run API breaking change check against origin/master."""
    print("Checking for public API breaking changes against master...")
    base_source = get_base_glinet_source()
    if base_source is None:
        print(
            "[WARNING] Could not fetch origin/master:gli4py/glinet.py. "
            "Skipping breaking change check."
        )
        return 0

    head_path = PROJECT_ROOT / "gli4py" / "glinet.py"
    head_source = head_path.read_text(encoding="utf-8")

    base_methods = extract_public_methods(base_source)
    head_methods = extract_public_methods(head_source)

    errors = compare_apis(base_methods, head_methods)

    if errors:
        print(f"\n[FAIL] Detected {len(errors)} API breaking change(s):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(
        f"[OK] No breaking changes detected across {len(base_methods)} public methods."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
