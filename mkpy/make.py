import inspect
import re
import threading
import time
import traceback

from collections import defaultdict
from collections.abc import Iterable
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Callable, Mapping, NamedTuple

from .util import trim_library_code_from_traceback


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


class MKPY_Exception(Exception):
    pass


class MakefileUsageException(MKPY_Exception):
    pass


class PhonyUsageException(MakefileUsageException):
    def __init__(self, target_name) -> None:
        super().__init__(
            f"Rule for target '{target_name}' did not produce the expected file, consider using '@target_phony'"
        )


class MissingTargetException(MKPY_Exception):
    def __init__(self, target_name) -> None:
        super().__init__(f"No rule for target: '{target_name}'")


class DuplicateTargetException(MKPY_Exception):
    def __init__(self, target_name) -> None:
        super().__init__(f"Multiple matching definitions for target: '{target_name}'")


class CircularDependencyException(MKPY_Exception):
    def __init__(self, target_name, depend_name) -> None:
        super().__init__(
            f"A circular dependency is formed: target '{target_name}' depends on ancestor '{depend_name}'"
        )


rules: list[Rule] = []


def single_target(
    recipe: Callable,
    name: str,
    depends: list[str],
    prerequisites: list[str],
    is_phony: bool,
):
    # Make rules can have a variable number of arguments
    parameters = len(inspect.signature(recipe).parameters)
    if parameters == 0:
        normalized_recipe = lambda _1, _2, _3: recipe()
    elif parameters == 1:
        normalized_recipe = lambda target, _2, _3: recipe(target)
    elif parameters == 2:
        normalized_recipe = lambda target, depends, _3: recipe(target, depends)
    elif parameters == 3:
        normalized_recipe = recipe
    else:
        raise MakefileUsageException(f"Too many arguments for rule body: '{name}'")

    requirements = Requirements([*depends], [*prerequisites], is_phony)
    rules.append(Rule(re.compile(name), normalized_recipe, requirements))


def target(
    recipe: Callable | list[Callable],
    name: str,
    depends: list[str],
    prerequisites: list[str],
    is_phony: bool,
):
    if isinstance(depends, str):
        raise MakefileUsageException(
            f"Dependency list must not be a string: did you mean ['{depends}']?"
        )

    if isinstance(prerequisites, str):
        raise MakefileUsageException(
            f"Prerequisite list must not be a string: did you mean ['{prerequisites}']?"
        )

    if isinstance(recipe, Iterable):
        for item in recipe:
            single_target(item, name, depends, prerequisites, is_phony)
    else:
        single_target(recipe, name, depends, prerequisites, is_phony)


def target_output(name: str, depends: list[str] = [], prerequisites: list[str] = []):
    return lambda recipe: target(recipe, name, depends, prerequisites, False)


def target_phony(name: str, depends: list[str] = [], prerequisites: list[str] = []):
    return lambda recipe: target(recipe, name, depends, prerequisites, True)


def source_file_recipe(target, depends, prerequisites):
    assert len(depends) == 0
    assert len(prerequisites) == 0
    assert Path(target).exists()


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
        # The graph cannot be generated: a special case is needed for pre-existing source files
        # TODO: should the user manually specify which files are source files?
        if not Path(target_name).exists():
            raise last_missing_target or MissingTargetException(target_name)

        return Node(
            target_name,
            False,
            is_prerequisite,
            source_file_recipe,
            [],
            [],
        )

    return top_level


class MakeBlockedException(MKPY_Exception):
    pass


class MakeFinishedException(MKPY_Exception):
    pass


class MakeState(Enum):
    NOT_YET_MADE = 0
    CURRENTLY_MAKING = 1
    FINISHED_MAKING = 2


target_states: Mapping[str, MakeState] = defaultdict(lambda: MakeState.NOT_YET_MADE)


def get_next_node_to_build(top_level: Node):
    if target_states[top_level.name] != MakeState.NOT_YET_MADE:
        raise MakeFinishedException()

    waiting_for_depend = False
    for node in top_level.depends + top_level.prerequisites:
        if target_states[node.name] == MakeState.NOT_YET_MADE:
            try:
                return get_next_node_to_build(node)
            except MakeBlockedException:
                waiting_for_depend = True
        if target_states[node.name] == MakeState.CURRENTLY_MAKING:
            waiting_for_depend = True

    if waiting_for_depend:
        raise MakeBlockedException()

    return top_level


dependency_graph_lock = threading.Lock()
has_any_worker_thrown_an_exception = False
worker_mkpy_exception = None


def except_hook(args: threading.ExceptHookArgs):
    global has_any_worker_thrown_an_exception, worker_mkpy_exception
    has_any_worker_thrown_an_exception = True

    if isinstance(args.exc_value, MKPY_Exception):
        worker_mkpy_exception = args.exc_value
    else:
        tb = trim_library_code_from_traceback(args.exc_traceback)
        traceback.print_exception(args.exc_type, args.exc_value, tb)


def should_run_node_recipe(node: Node):
    if node.is_phony:
        return True

    if not Path(node.name).exists():
        return True

    if node.is_prerequisite:
        return False  # Timestamp depends don't matter for prerequisites

    if any(map(lambda depend: depend.is_phony, node.depends)):
        return True

    top_level_timestamp = Path(node.name).stat().st_mtime
    for depend in node.depends:
        if Path(depend.name).stat().st_mtime > top_level_timestamp:
            return True

    return False


def worker_thread(top_level: Node):
    while not has_any_worker_thrown_an_exception:
        try:
            with dependency_graph_lock:
                next_node = get_next_node_to_build(top_level)
                target_states[next_node.name] = MakeState.CURRENTLY_MAKING
        except MakeBlockedException:
            # Start polling: further work is blocked until another worker finishes
            time.sleep(0)
            continue
        except MakeFinishedException:
            # Terminal case: someone else is dealing with the top_level target
            break

        def get_node_names(nodes: list[Node]):
            return list(map(lambda node: node.name, nodes))

        depends = get_node_names(next_node.depends)
        prerequisites = get_node_names(next_node.prerequisites)
        if should_run_node_recipe(next_node):
            next_node.recipe(next_node.name, depends, prerequisites)

            if not next_node.is_phony and not Path(next_node.name).exists():
                raise PhonyUsageException(next_node.name)

        with dependency_graph_lock:
            target_states[next_node.name] = MakeState.FINISHED_MAKING


def run_make(target_name, job_count):
    graph = generate_dependency_graph(target_name, satisfied_targets=set())

    threading.excepthook = except_hook

    thread_pool: list[threading.Thread] = []
    for _ in range(job_count):
        thread_pool.append(threading.Thread(target=partial(worker_thread, graph)))

    for thread in thread_pool:
        thread.start()

    for thread in thread_pool:
        thread.join()

    if has_any_worker_thrown_an_exception:
        raise worker_mkpy_exception or MKPY_Exception("Exception thrown in worker")
