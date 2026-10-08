"""Recovery of tool calls the model wrote out as text.

Small local models sometimes describe the call in the body of the reply
instead of emitting it through the tool channel. Ollama then has nothing to
execute, and without this module the operator would see the raw dictionary in
the chat.

Such a call may carry arithmetic inside the JSON (`"latitudes": [-7.23 - 0.01]`),
which is not valid JSON and therefore cannot be recovered with `json.loads`.
The evaluator below understands numbers, lists, dictionaries, strings and the
four arithmetic operations, and refuses anything else.
"""

from __future__ import annotations

import ast
import inspect
from types import EllipsisType
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.agents.dashboard.tools import ProposalBuffer

NAME_FIELDS = ("name", "tool", "tool_name", "function")
ARGUMENT_FIELDS = ("parameters", "arguments", "args", "parameter")

# Naming what `_evaluate` builds: the constants a Python literal can hold, nested in dicts and lists.
type LiteralValue = (
    dict[LiteralValue, LiteralValue]
    | list[LiteralValue]
    | str
    | bytes
    | bool
    | int
    | float
    | complex
    | EllipsisType
    | None
)

_JSON_LITERALS = {
    "true": True,
    "false": False,
    "null": None,
    "True": True,
    "False": False,
    "None": None,
}
_ARITHMETIC = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
}


def _evaluate(node: ast.AST | None) -> LiteralValue:
    """Evaluates a syntax node, accepting only data and simple arithmetic.

    Private on purpose: this is the security boundary of the module. Calling it
    from elsewhere would invite evaluating text that never went through
    `recover_tool_call`.

    Raises:
        ValueError: On any construct outside the allowed set, such as function
            calls or attribute access.
    """
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Dict):
        return {_evaluate(key): _evaluate(value) for key, value in zip(node.keys, node.values, strict=True)}

    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [_evaluate(element) for element in node.elts]

    if isinstance(node, ast.Name) and node.id in _JSON_LITERALS:
        return _JSON_LITERALS[node.id]

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return _evaluate_sign(node)

    if isinstance(node, ast.BinOp) and type(node.op) in _ARITHMETIC:
        return _evaluate_arithmetic(node)

    raise ValueError(f"Construct not allowed: {type(node).__name__}.")


def _evaluate_sign(node: ast.UnaryOp) -> int | float:
    """Evaluates a plus or minus sign in front of a number.

    Private for the same reason as `_evaluate`, whose boundary it belongs to.

    Raises:
        ValueError: If the operand is not a number.
    """
    value = _evaluate(node.operand)
    if not isinstance(value, (int, float)):
        raise ValueError("Sign applied to a value that is not a number.")
    return -value if isinstance(node.op, ast.USub) else value


def _evaluate_arithmetic(node: ast.BinOp) -> int | float:
    """Evaluates one of the four arithmetic operations between two numbers.

    Private for the same reason as `_evaluate`, whose boundary it belongs to.

    Raises:
        ValueError: If either operand is not a number.
    """
    left = _evaluate(node.left)
    right = _evaluate(node.right)
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        raise ValueError("Arithmetic between values that are not numbers.")
    return _ARITHMETIC[type(node.op)](left, right)


def find_object_candidates(text: str) -> list[str]:
    """Extracts the brace-balanced fragments found in the text.

    Returns:
        list: Fragments, outermost first.
    """
    candidates = []

    for start, character in enumerate(text):
        if character != "{":
            continue

        depth = 0
        for end in range(start, len(text)):
            if text[end] == "{":
                depth += 1
            elif text[end] == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start : end + 1])
                    break

    return candidates


def first_present(mapping: dict[LiteralValue, LiteralValue], fields: tuple[str, ...]) -> LiteralValue:
    for field in fields:
        if field in mapping:
            return mapping[field]
    return None


def evaluated_objects(text: str) -> list[dict[LiteralValue, LiteralValue]]:
    """Returns: list: The dictionaries the text's brace-balanced fragments evaluate to, outermost first."""
    objects = []

    for candidate in find_object_candidates(text):
        try:
            parsed = _evaluate(ast.parse(candidate, mode="eval").body)
        except (SyntaxError, ValueError, TypeError, ZeroDivisionError):
            continue

        if isinstance(parsed, dict):
            objects.append(parsed)

    return objects


def parse_tool_call(text: str | None) -> tuple[str, dict[LiteralValue, LiteralValue]] | None:
    """Looks for a tool call written out by the model.

    Args:
        text (str): Content returned by the agent.

    Returns:
        tuple or None: (tool name, argument dictionary), or None if the text
        holds no recognizable call.
    """
    if not text or "{" not in text:
        return None

    for parsed in evaluated_objects(text):
        name = first_present(parsed, NAME_FIELDS)
        arguments = first_present(parsed, ARGUMENT_FIELDS)

        if isinstance(name, str) and isinstance(arguments, dict):
            return name, arguments

    return None


def tools_taking(arguments: dict[LiteralValue, LiteralValue], tools: list[Callable[..., str]]) -> list[str]:
    """Returns: list: The names of the tools that take every one of these arguments and need no other."""
    names = []

    for tool in tools:
        parameters = inspect.signature(tool).parameters.values()
        accepted = {parameter.name for parameter in parameters}
        required = {parameter.name for parameter in parameters if parameter.default is inspect.Parameter.empty}
        if set(arguments) <= accepted and required <= set(arguments):
            names.append(tool.__name__)

    return names


def parse_bare_arguments(
    text: str | None, tools: list[Callable[..., str]]
) -> tuple[str, dict[LiteralValue, LiteralValue]] | None:
    """Looks for the arguments of a tool call the model wrote out without the tool's name.

    Observed on 8 October 2026 with qwen3:4b, as the whole reply to "add one
    satellite near ground station 11": `{"node_types": ["Satellite"],
    "latitudes": [-3.1019], "longitudes": [-60.0250]}`. An object is taken as a
    call only when exactly one tool takes those arguments; one that two tools
    could take is left alone rather than guessed at.

    Args:
        text (str): Content returned by the agent.
        tools (list): The tools the agent was given.

    Returns:
        tuple or None: (tool name, argument dictionary), or None if no object
        in the text belongs to exactly one tool.
    """
    if not text or "{" not in text:
        return None

    for parsed in evaluated_objects(text):
        if not parsed or not all(isinstance(key, str) for key in parsed):
            continue

        names = tools_taking(parsed, tools)
        if len(names) == 1:
            return names[0], parsed

    return None


def looks_like_tool_call(text: str | None) -> bool:
    """Returns: bool: True if the text is in fact a tool call."""
    return parse_tool_call(text) is not None


def recover(buffer: ProposalBuffer, text: str | None) -> str | None:
    """Tries to execute a tool call that arrived written into the text.

    Args:
        buffer (ProposalBuffer): Buffer whose tools may be invoked.
        text (str): Content returned by the agent.

    Returns:
        str or None: The executed tool's reply, or None if nothing was
        recoverable.
    """
    call = parse_tool_call(text) or parse_bare_arguments(text, buffer.get_tools())
    if call is None:
        return None

    name, arguments = call
    tools = {tool.__name__: tool for tool in buffer.get_tools()}

    tool = tools.get(name)
    if tool is None:
        return None

    try:
        # Passing the arguments as keywords: a key that is not a string raises TypeError, answered below.
        return tool(**cast("dict[str, LiteralValue]", arguments))
    except TypeError as error:
        return f"Error: could not apply {name}: {error}"
