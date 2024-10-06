#!/usr/bin/env python3

# requires a patched version of baron;
# One way to get this is to run:
# nix-shell ./common/redbaron.nix --run 'python3 ./common/replace-inline-callbacks.py'

import os
import subprocess
import sys
from multiprocessing import Lock
from multiprocessing import Pool
from pathlib import Path
from typing import List

import baron.parser
from redbaron import RedBaron


def refactor_defer_inlineCallbacks(code: str) -> str:
    red = RedBaron(code)

    # Refactor functions with @defer.inlineCallbacks and collect them
    functions_to_refactor = []
    for node in red.find_all('def'):
        # Look for the @defer.inlineCallbacks decorator
        to_remove = []
        for i, decorator in enumerate(node.decorators):
            if decorator.dumps() != "@defer.inlineCallbacks":
                continue
            to_remove.append(i)
            # Make the function async
            node.async_ = True
            # Mark the function for yield-to-await replacement
            functions_to_refactor.append(node)
        # Remove the @defer.inlineCallbacks decorator
        for i in reversed(to_remove):
            node.decorators.pop(i)
        if to_remove:
            pass

    # Replace yield with await, but only in functions that had inlineCallbacks
    for i, func_node in enumerate(functions_to_refactor):
        print(f"Refactoring {func_node.name}...")
        for yield_from_node in func_node.find_all('yield_from'):
            yield_from_node.replace(f"await for {yield_from_node.value.dumps()}")
        to_remove = []
        for i, yield_node in enumerate(func_node.find_all('yield')):
            if yield_node.value is None:
                to_remove.append(i)
            else:
                yield_node.replace(f"await {yield_node.value.dumps()}")
        for i in reversed(to_remove):
            func_node.pop(i)

    return red.dumps()


def find_files_with_inlineCallbacks() -> List[Path]:
    result = subprocess.run(
        ['rg', '--null-data', '--files-with-matches', '@defer.inlineCallbacks', '--glob', '*.py'],
        stdout=subprocess.PIPE,
        check=True,
    )

    return [Path(file.decode("utf-8")) for file in result.stdout.split(b'\0')]


GIT_LOCK = Lock()


def commit_file(file_path: Path, manual: bool = False) -> None:
    if file_path == Path("www/badges/buildbot_badges/__init__.py"):
        # This file adds an import that ruff cannot remove
        subprocess.run(
            ['sed', '-i', '/from twisted.internet import defer/d', str(file_path)], check=True
        )
    subprocess.run(["ruff", "format", str(file_path)], check=True)
    subprocess.run(["ruff", "check", "--fix", "--unsafe-fixes", str(file_path)], check=True)
    # this deletes empty lines sometimes
    subprocess.run(["ruff", "format", str(file_path)], check=True)

    with GIT_LOCK:
        subprocess.run(['git', 'add', str(file_path)], check=True)
        commit_message = f"{file_path}: use async/await instead of inlineCallbacks"
        if manual:
            commit_message = "[manual] " + commit_message
        subprocess.run(['git', 'commit', '-m', commit_message], check=True)


def refactor(file_path: Path) -> None | tuple[Path, Exception]:
    if file_path.resolve() == Path(__file__).resolve() or file_path.is_dir():
        return
    print(f"Refactoring {file_path}...")
    try:
        refactored_code = refactor_defer_inlineCallbacks(file_path.read_text())
        file_path.write_text(refactored_code)
        commit_file(file_path)
    except (baron.inner_formatting_grouper.GroupingError, baron.parser.ParsingError) as e:
        print(f"Failed to refactor {file_path}: {e}")
        return file_path, e
    except subprocess.CalledProcessError as e:
        print(f"Failed to commit {file_path}: {e}")
        with GIT_LOCK:
            subprocess.run(['git', 'checkout', '--', str(file_path)], check=True)
        return file_path, e


def main() -> None:
    if len(sys.argv) > 1:
        files_to_refactor = [Path(file) for file in sys.argv[1:]]
    else:
        files_to_refactor = find_files_with_inlineCallbacks()

    if os.environ.get("DEBUG_SCRIPT"):
        for f in files_to_refactor:
            refactor(f)
        return
    else:
        with Pool() as p:
            results = p.map(refactor, files_to_refactor)

    failed_paths = []
    for res in results:
        if res is None:
            continue
        file_path, e = res
        print(f"Failed to refactor this file: {file_path}")
        print("To retry, run:")
        print(f"  {sys.argv[0]} {file_path}")
        failed_paths.append(file_path)
    if os.environ.get("FIX_MANUALLY"):
        for path in failed_paths:
            print(f"Fixing {path} manually...")
            editor = os.environ.get("EDITOR", "vim")
            subprocess.run([editor, str(path)], check=True)
            commit_file(path)


if __name__ == "__main__":
    main()
