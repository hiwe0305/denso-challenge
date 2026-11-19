"""Agent QA/QC tool layer: read-only, deterministic computations on contract artifacts.

DA-43 design 2026-11-19 section 4. Every tool takes artifacts already loaded and a
`FactBook`, adds what it computed as facts, and returns a `ToolResult`. No tool calls a
model, opens a simulator or imports another lane or an adapter. A tool that lacks what
it needs says so as a fact (`not_judged`); silence never reads as "clean".
"""
