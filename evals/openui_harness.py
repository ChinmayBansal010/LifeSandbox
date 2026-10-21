"""OpenUI Lang Syntax & AST Schema Validation Harness.

Validates that declarative OpenUI Lang programs emitted by the LLM strictly conform
to the syntax rules and component library specifications defined in openui_prompt.txt:
1. Root entry point requirement (`root = Card(...)`).
2. Balanced parentheses, brackets, and string literal closures.
3. Positional argument enforcement (disallowing Python/JS keyword arguments `foo: bar` inside component calls).
4. Component whitelist enforcement against known library signatures.
5. Reference graph connectivity: every non-root variable must be consumed by a parent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

VALID_COMPONENTS = {
    # Structure & Container
    "Card", "CardHeader", "CardFooter", "InlineHeader", "Separator", "Callout", "TextCallout",
    # Content & Typography
    "TextContent", "MarkDownRenderer", "CodeBlock", "Image", "ImageBlock", "ImageGallery",
    # Tables
    "Table", "Col", "EditableTable",
    # Charts
    "BarChart", "LineChart", "AreaChart", "RadarChart", "HorizontalBarChart", "Series",
    "PieChart", "RadialChart", "SingleStackedBarChart", "Slice",
    "ScatterChart", "ScatterSeries", "Point",
    # Metrics & KPIs
    "Metric", "Stat", "Badge",
    # Forms & Inputs
    "Form", "FormControl", "Label", "Input", "TextArea", "Select", "SelectItem",
    "DatePicker", "Slider", "CheckBoxGroup", "RadioGroup", "Chips", "OptionCards",
    # Actions & Steps
    "Action", "Button", "Buttons",
}


@dataclass
class ValidationIssue:
    line_number: int
    rule: str
    message: str
    severity: str = "error"  # error | warning


@dataclass
class OpenUIValidationReport:
    is_valid: bool
    root_defined: bool
    variables_defined: list[str]
    variables_referenced: list[str]
    unreferenced_variables: list[str]
    components_used: list[str]
    issues: list[ValidationIssue] = field(default_factory=list)


class OpenUILangValidator:
    """Parses and validates OpenUI Lang source code."""

    @classmethod
    def validate(cls, code: str) -> OpenUIValidationReport:
        issues: list[ValidationIssue] = []
        clean = (code or "").strip()

        if not clean:
            return OpenUIValidationReport(
                is_valid=False,
                root_defined=False,
                variables_defined=[],
                variables_referenced=[],
                unreferenced_variables=[],
                components_used=[],
                issues=[ValidationIssue(0, "empty_program", "OpenUI program is empty")],
            )

        # Check balanced delimiters
        delimiter_issue = cls._check_balanced_delimiters(clean)
        if delimiter_issue:
            issues.append(delimiter_issue)

        lines = clean.splitlines()
        defined_vars: set[str] = set()
        components_used: set[str] = set()
        rhs_texts: list[str] = []

        root_found = False

        for line_idx, line in enumerate(lines, start=1):
            line_str = line.strip()
            if not line_str or line_str.startswith("#") or line_str.startswith("//"):
                continue

            # Check assignment pattern: identifier = Expression
            match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+)$", line_str)
            if not match:
                # Top-level non-assignment statement
                issues.append(
                    ValidationIssue(
                        line_idx,
                        "assignment_syntax",
                        f"Line does not follow 'identifier = Expression' syntax: '{line_str[:50]}'",
                    )
                )
                continue

            var_name, rhs = match.group(1), match.group(2)
            defined_vars.add(var_name)
            if var_name == "root":
                root_found = True

            rhs_texts.append(rhs)

            # Check keyword arguments inside component call: Component(arg: "val") is invalid
            # Note: Object literals inside arrays [{ key: val }] are allowed, but Foo(bar: baz) is illegal
            colon_match = re.search(r"([A-Z][a-zA-Z0-9]+)\s*\([^)]*?\b([a-zA-Z_][a-zA-Z0-9_]*)\s*:", rhs)
            if colon_match:
                comp_name = colon_match.group(1)
                kw_name = colon_match.group(2)
                # Ensure it's not a url like http: or json object like {
                if "{" not in rhs[colon_match.start() : colon_match.end()]:
                    issues.append(
                        ValidationIssue(
                            line_idx,
                            "positional_args_required",
                            f"Component '{comp_name}' uses keyword argument '{kw_name}:'. OpenUI arguments are strictly positional.",
                        )
                    )

            # Find all component calls: e.g. Card(...), TextContent(...)
            call_matches = re.findall(r"\b([A-Z][a-zA-Z0-9]+)\s*\(", rhs)
            for c_name in call_matches:
                components_used.add(c_name)
                if c_name not in VALID_COMPONENTS:
                    issues.append(
                        ValidationIssue(
                            line_idx,
                            "unknown_component",
                            f"Unknown component '{c_name}'. Must be one of the recognized OpenUI components.",
                        )
                    )

        if not root_found:
            issues.append(
                ValidationIssue(
                    len(lines),
                    "missing_root",
                    "OpenUI program must define 'root = ...' as its entry point.",
                )
            )

        # Check variable referencing: every defined variable (except root) must be referenced
        all_rhs_combined = " ".join(rhs_texts)
        unreferenced: list[str] = []
        referenced: set[str] = set()

        for var in defined_vars:
            if var == "root":
                continue
            # Look for variable reference as a whole word in RHS expressions
            # exclude matches where it's on the LHS
            if re.search(rf"\b{re.escape(var)}\b", all_rhs_combined):
                referenced.add(var)
            else:
                unreferenced.append(var)
                issues.append(
                    ValidationIssue(
                        0,
                        "unreferenced_variable",
                        f"Variable '{var}' is defined but never referenced by another component. It will be silently dropped.",
                        severity="warning",
                    )
                )

        has_errors = any(i.severity == "error" for i in issues)

        return OpenUIValidationReport(
            is_valid=not has_errors,
            root_defined=root_found,
            variables_defined=sorted(defined_vars),
            variables_referenced=sorted(referenced),
            unreferenced_variables=sorted(unreferenced),
            components_used=sorted(components_used),
            issues=issues,
        )

    @staticmethod
    def _check_balanced_delimiters(code: str) -> ValidationIssue | None:
        stack: list[tuple[str, int]] = []
        pairs = {")": "(", "]": "[", "}": "{"}
        in_string = False
        escape = False

        for idx, char in enumerate(code):
            if char == '"' and not escape:
                in_string = not in_string
            elif char == "\\" and in_string:
                escape = not escape
                continue
            elif in_string:
                escape = False
                continue

            if char in "([{":
                stack.append((char, idx))
            elif char in ")]}":
                if not stack or stack[-1][0] != pairs[char]:
                    return ValidationIssue(
                        1,
                        "unbalanced_delimiter",
                        f"Unmatched closing delimiter '{char}' at character index {idx}.",
                    )
                stack.pop()

        if in_string:
            return ValidationIssue(1, "unclosed_string", "String literal was not closed.")
        if stack:
            open_delim, idx = stack[-1]
            return ValidationIssue(
                1,
                "unbalanced_delimiter",
                f"Unclosed opening delimiter '{open_delim}' at character index {idx}.",
            )
        return None
