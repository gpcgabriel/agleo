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

import ast

NAME_FIELDS = ("name", "tool", "tool_name", "function")
ARGUMENT_FIELDS = ("parameters", "arguments", "args", "parameter")

_JSON_LITERALS = {"true": True, "false": False, "null": None, "True": True, "False": False, "None": None}
_ARITHMETIC = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
               ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b}


def _evaluate(node):
    """Evaluates a syntax node, accepting only data and simple arithmetic.

    Raises:
        ValueError: On any construct outside the allowed set, such as function
            calls or attribute access.
    """
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Dict):
        return {_evaluate(key): _evaluate(value) for key, value in zip(node.keys, node.values)}

    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [_evaluate(element) for element in node.elts]

    if isinstance(node, ast.Name) and node.id in _JSON_LITERALS:
        return _JSON_LITERALS[node.id]

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _evaluate(node.operand)
        if not isinstance(value, (int, float)):
            raise ValueError("Sign applied to a value that is not a number.")
        return -value if isinstance(node.op, ast.USub) else value

    if isinstance(node, ast.BinOp) and type(node.op) in _ARITHMETIC:
        left = _evaluate(node.left)
        right = _evaluate(node.right)
        if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            raise ValueError("Arithmetic between values that are not numbers.")
        return _ARITHMETIC[type(node.op)](left, right)

    raise ValueError(f"Construct not allowed: {type(node).__name__}.")


def _find_object_candidates(text):
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


def _first_present(mapping, fields):
    for field in fields:
        if field in mapping:
            return mapping[field]
    return None


def parse_tool_call(text):
    """Looks for a tool call written out by the model.

    Args:
        text (str): Content returned by the agent.

    Returns:
        tuple or None: (tool name, argument dictionary), or None if the text
        holds no recognizable call.
    """
    if not text or "{" not in text:
        return None

    for candidate in _find_object_candidates(text):
        try:
            parsed = _evaluate(ast.parse(candidate, mode="eval").body)
        except (SyntaxError, ValueError, TypeError, ZeroDivisionError):
            continue

        if not isinstance(parsed, dict):
            continue

        name = _first_present(parsed, NAME_FIELDS)
        arguments = _first_present(parsed, ARGUMENT_FIELDS)

        if isinstance(name, str) and isinstance(arguments, dict):
            return name, arguments

    return None


def looks_like_tool_call(text):
    """Returns: bool: True if the text is in fact a tool call."""
    return parse_tool_call(text) is not None


def recover(buffer, text):
    """Tries to execute a tool call that arrived written into the text.

    Args:
        buffer (ProposalBuffer): Buffer whose tools may be invoked.
        text (str): Content returned by the agent.

    Returns:
        str or None: The executed tool's reply, or None if nothing was
        recoverable.
    """
    call = parse_tool_call(text)
    if call is None:
        return None

    name, arguments = call
    tools = {tool.__name__: tool for tool in buffer.get_tools()}

    tool = tools.get(name)
    if tool is None:
        return None

    try:
        return tool(**arguments)
    except TypeError as error:
        return f"Error: could not apply {name}: {error}"
