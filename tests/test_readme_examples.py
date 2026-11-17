"""Runs the `$ jaden ...` examples in README.md and README_JP.md and checks that the output shown is real.

An example is checked when its command is followed by output lines. A line that is just '...'
skips ahead to the next line that matches. Commands that need a file, the network or a running
server are not run.
"""

import re
import shlex
from pathlib import Path

import pytest

from jaden.cli import main

ROOT = Path(__file__).resolve().parents[1]
READMES = ("README.md", "README_JP.md")
RUNNABLE = {"normalize", "validate", "parse", "compare", "postal", "suggest", "reverse"}


def _examples():
    found = []
    for name in READMES:
        if (ROOT / name).exists():
            found.extend(_examples_in(name))
    return found


def _examples_in(name):
    found = []
    for block in re.findall(r"```bash\n(.*?)```", (ROOT / name).read_text(encoding="utf-8"), flags=re.S):
        lines = block.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("$ jaden "):
                expected = []
                j = i + 1
                while j < len(lines) and lines[j].strip() and not lines[j].startswith(("$ ", "# ")):
                    expected.append(lines[j])
                    j += 1
                command = line[len("$ jaden "):]
                args = shlex.split(re.sub(r"\s+#.*$", "", command))
                offline = args[0] != "geocode" or "offline" in args
                if expected and args[0] in RUNNABLE | {"geocode"} and offline and "|" not in command:
                    found.append((f"{name}: {command}", args, expected))
                i = j
            else:
                i += 1
    return found


EXAMPLES = _examples()


@pytest.mark.skipif(not EXAMPLES, reason="the READMEs are not next to the tests (installed-package run)")
@pytest.mark.parametrize("command, args, expected", EXAMPLES, ids=[e[0][:70] for e in EXAMPLES])
def test_readme_example_output_is_real(command, args, expected, capsys):
    main(args)
    actual = capsys.readouterr().out.rstrip("\n").splitlines()
    position = 0
    for want in expected:
        if want.strip() == "...":
            continue
        while position < len(actual) and actual[position].rstrip() != want.rstrip():
            position += 1
        assert position < len(actual), f"`{command}` does not print: {want!r}\nactual output:\n" + "\n".join(actual)
        position += 1
    if "..." not in [w.strip() for w in expected]:
        assert len(actual) == len(expected), f"`{command}` prints {len(actual)} lines, README shows {len(expected)}:\n" + "\n".join(actual)
