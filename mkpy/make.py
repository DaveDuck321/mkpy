import re

from functools import partial
from typing import Callable, NamedTuple


class Requirements(NamedTuple):
    depends: list[str]
    prerequisites: list[str]
    is_phony: bool


class Rule(NamedTuple):
    matcher: re.Pattern
    recipe: Callable
    requirements: Requirements


class Node(NamedTuple):
    name: str
    is_phony: bool
    is_prerequisite: bool
    recipe: Callable
    depends: list["Node"]
    prerequisites: list["Node"]


class MissingTargetException(Exception):
    def __init__(self, target_name) -> None:
        super().__init__(f"No rule for target: '{target_name}'")


class DuplicateTargetException(Exception):
    def __init__(self, target_name) -> None:
        super().__init__(f"Multiple matching definitions for target: '{target_name}'")


class CircularDependencyException(Exception):
    def __init__(self, target_name, depend_name) -> None:
        super().__init__(
            f"A circular dependency is formed: target '{target_name}' depends on ancestor '{depend_name}'"
        )


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


def generate_dependency_graph(
    target_name: str, satisfied_targets: set[str], is_prerequisite: bool = False
) -> Node:
    top_level = None
    last_missing_target = None
    for rule in rules:
        if match := rule.matcher.fullmatch(target_name):

            def get_subgraph(is_prerequisite: bool, dependency: str):
                depend_name = dependency.format(*match.groups())
                if depend_name in satisfied_targets:
                    raise CircularDependencyException(target_name, depend_name)

                return generate_dependency_graph(
                    depend_name, satisfied_targets.union([depend_name]), is_prerequisite
                )

            try:
                requires = rule.requirements
                depends = map(partial(get_subgraph, False), requires.depends)
                prerequisites = map(partial(get_subgraph, True), requires.prerequisites)

                if top_level is not None:
                    raise DuplicateTargetException(target_name)

                top_level = Node(
                    target_name,
                    requires.is_phony,
                    is_prerequisite,
                    rule.recipe,
                    list(depends),
                    list(prerequisites),
                )
            except MissingTargetException as missing_target:
                last_missing_target = missing_target

    if top_level is None:
        raise last_missing_target or MissingTargetException(target_name)

    return top_level
