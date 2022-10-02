import re

from typing import Callable, NamedTuple


class Requirements(NamedTuple):
    depends: list[str]
    prerequisites: list[str]
    is_phony: bool


class Rule(NamedTuple):
    matcher: re.Pattern
    recipe: Callable
    requirements: Requirements


rules: list[Rule] = []


def target(
    recipe: Callable,
    name: str,
    depends: list[str],
    prerequisites: list[str],
    is_phony: bool,
):
    requirements = Requirements(depends, prerequisites, is_phony)
    rules.append(Rule(re.compile(name), recipe, requirements))


def target_output(name: str, depends: list[str] = [], prerequisites: list[str] = []):
    return lambda recipe: target(recipe, name, depends, prerequisites, False)


def target_phony(name: str, depends: list[str] = [], prerequisites: list[str] = []):
    return lambda recipe: target(recipe, name, depends, prerequisites, True)
