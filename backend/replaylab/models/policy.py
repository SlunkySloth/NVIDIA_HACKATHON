import ast

from pydantic import Field

from replaylab.schemas import StrictModel


class Diagnosis(StrictModel):
    explanation: str = Field(min_length=10, max_length=1500)
    suspected_location: str = Field(max_length=100)
    regression_test: str = Field(min_length=20, max_length=12000)


class Candidate(StrictModel):
    explanation: str = Field(min_length=10, max_length=1500)
    path: str
    source: str = Field(min_length=20, max_length=16000)


def validate_candidate(candidate: Candidate):
    if candidate.path != "handler.py":
        raise ValueError("patch policy permits only handler.py; tests, observer and dependencies are immutable")
    tree = ast.parse(candidate.source)
    if not any(isinstance(n, ast.FunctionDef) and n.name == "handle" for n in tree.body):
        raise ValueError("candidate must expose handle(db, event)")
    return candidate.source


def validate_test(source: str):
    """Declarative HTTP assertions only: cannot alter reports or test collection.

    This policy is defense in depth; tests still execute unprivileged in live mode.
    Independent SQLite checks, not these tests, determine the business verdict.
    """
    tree = ast.parse(source)
    allowed = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Assign, ast.Expr, ast.Assert, ast.Name, ast.Load, ast.Store, ast.Constant, ast.Dict, ast.List, ast.Tuple, ast.Subscript, ast.Attribute, ast.Call, ast.keyword, ast.Compare, ast.Eq, ast.NotEq, ast.Gt, ast.GtE, ast.Lt, ast.LtE, ast.UnaryOp, ast.USub)
    for n in ast.walk(tree):
        if not isinstance(n, allowed):
            raise ValueError(f"test policy disallows {type(n).__name__}; use straight-line HTTP calls and assertions")  # noqa: TRY004 - this is a source-policy validation error.
        if isinstance(n, ast.Name) and (n.id.startswith("_") or n.id in {"exec", "eval", "open", "compile", "globals", "locals", "pytest", "getattr", "setattr"}):
            raise ValueError("unsafe name in generated test")
        if isinstance(n, ast.Attribute) and n.attr not in {"post", "get", "json", "status_code"}:
            raise ValueError("only client HTTP methods, JSON and status_code may be accessed")
        if isinstance(n, ast.Call):
            if not isinstance(n.func, ast.Attribute) or n.func.attr not in {"post", "get", "json"}:
                raise ValueError("only HTTP requests and response JSON calls are allowed")
            endpoints = {"/state"} if n.func.attr == "get" else {"/webhook", "/__replay/restart"}
            if n.func.attr in {"post", "get"} and (not isinstance(n.func.value, ast.Name) or n.func.value.id != "client" or not n.args or not isinstance(n.args[0], ast.Constant) or n.args[0].value not in endpoints):
                raise ValueError("test requests must use the fixture client and supported relative endpoints")
        if isinstance(n, ast.FunctionDef) and (not n.name.startswith("test_") or n.decorator_list or n.returns or n.args.defaults or n.args.kw_defaults or n.args.vararg or n.args.kwarg or n.args.kwonlyargs or n.args.posonlyargs or [a.arg for a in n.args.args] != ["client"]):
            raise ValueError("test functions must take only client, without decorators or defaults")
        if isinstance(n, ast.Assign) and any(not isinstance(t, ast.Name) or t.id == "client" for t in n.targets):
            raise ValueError("assignment must target a local variable other than client")
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef) or not any(isinstance(n, ast.Assert) for n in ast.walk(tree)):
        raise ValueError("provide one test function containing at least one assertion")
    return source
