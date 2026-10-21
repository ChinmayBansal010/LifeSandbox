"""Test suite for OpenUI Lang Syntax & AST Schema Validation Harness."""

from __future__ import annotations

from evals.openui_harness import OpenUILangValidator


def test_openui_valid_dashboard_program():
    valid_program = (
        'header = CardHeader("Monthly Financial Trajectory", "50/30/20 Breakdown")\n'
        's1 = Series("Target", [50, 30, 20])\n'
        's2 = Series("Current", [55, 35, 10])\n'
        'chart = BarChart(["Needs", "Wants", "Savings"], [s1, s2])\n'
        'summary = TextContent("You are currently under-allocating savings by 10%.")\n'
        'root = Card([header, chart, summary])'
    )
    report = OpenUILangValidator.validate(valid_program)
    assert report.is_valid is True
    assert report.root_defined is True
    assert "Card" in report.components_used
    assert "BarChart" in report.components_used
    assert len(report.unreferenced_variables) == 0
    assert len([i for i in report.issues if i.severity == "error"]) == 0


def test_openui_detects_missing_root():
    program = (
        'header = CardHeader("Welcome")\n'
        'content = TextContent("Here is your data")'
    )
    report = OpenUILangValidator.validate(program)
    assert report.is_valid is False
    assert report.root_defined is False
    assert any(i.rule == "missing_root" for i in report.issues)


def test_openui_detects_unbalanced_parentheses():
    program = (
        'header = CardHeader("Missing paren"\n'
        'root = Card([header])'
    )
    report = OpenUILangValidator.validate(program)
    assert report.is_valid is False
    assert any(i.rule == "unbalanced_delimiter" for i in report.issues)


def test_openui_detects_unclosed_string_literal():
    program = (
        'header = CardHeader("Unclosed string)\n'
        'root = Card([header])'
    )
    report = OpenUILangValidator.validate(program)
    assert report.is_valid is False
    assert any(i.rule in ("unclosed_string", "unbalanced_delimiter") for i in report.issues)


def test_openui_detects_prohibited_keyword_arguments():
    # Positional args are required in OpenUI Lang; keyword args are invalid
    program = (
        'header = CardHeader(title: "Invalid Colon Syntax")\n'
        'root = Card([header])'
    )
    report = OpenUILangValidator.validate(program)
    assert report.is_valid is False
    assert any(i.rule == "positional_args_required" for i in report.issues)


def test_openui_detects_unknown_component_name():
    program = (
        'widget = FancySuperHologramView("3D")\n'
        'root = Card([widget])'
    )
    report = OpenUILangValidator.validate(program)
    assert report.is_valid is False
    assert any(i.rule == "unknown_component" for i in report.issues)


def test_openui_warns_on_unreferenced_variable():
    program = (
        'orphan = TextContent("I am defined but never placed in root")\n'
        'header = CardHeader("Title")\n'
        'root = Card([header])'
    )
    report = OpenUILangValidator.validate(program)
    # Warnings do not invalidate the program if root and syntax are valid
    assert "orphan" in report.unreferenced_variables
    assert any(i.rule == "unreferenced_variable" for i in report.issues)
