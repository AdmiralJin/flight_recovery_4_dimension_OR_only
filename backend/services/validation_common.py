from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError


@dataclass(frozen=True)
class ValidationIssue:
    location: str
    code: str
    message: str


def format_location(parts: Iterable[Any]) -> str:
    result = ""
    for part in parts:
        if isinstance(part, int):
            result += f"[{part}]"
        else:
            result += ("." if result else "") + str(part)
    return result or "$"


def issue(location: str, code: str, message: str) -> ValidationIssue:
    return ValidationIssue(location=location, code=code, message=message)


def pydantic_issues(exc: ValidationError) -> list[ValidationIssue]:
    return [
        issue(format_location(error["loc"]), error["type"], error["msg"])
        for error in exc.errors(include_url=False, include_input=False)
    ]
