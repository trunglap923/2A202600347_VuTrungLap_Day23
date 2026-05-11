# Day 23 Lab Report

## 1. Team / student

- Name: 2A202600347_VuTrungLap
- Repo/commit: AI_Vin/assignments/Day23
- Date: 2026-05-11

## 2. Architecture

The graph consists of 11 nodes (intake, classify, tool, evaluate, approval, retry, answer, etc.) 
connected via conditional edges. It uses priority-based routing and bounded retry loops.

## 3. State schema

| Field | Reducer | Why |
|---|---|---|
| messages | append | audit conversation/events |
| tool_results | append | history of tool outputs |
| errors | append | track failure reasons |
| route | overwrite | current route only |

## 4. Scenario results

| Scenario | Expected route | Actual route | Success | Retries | Interrupts |
|---|---|---|---:|---:|---:|
| G01_simple | simple | simple | True | 0 | 0 |
| G02_simple2 | simple | simple | True | 0 | 0 |
| G03_tool | tool | tool | True | 0 | 0 |
| G04_tool2 | tool | tool | True | 0 | 0 |
| G05_tool3 | tool | tool | True | 0 | 0 |
| G06_missing | missing_info | missing_info | True | 0 | 0 |
| G07_missing2 | missing_info | missing_info | True | 0 | 0 |
| G08_risky | risky | risky | True | 0 | 1 |
| G09_risky2 | risky | risky | True | 0 | 1 |
| G10_risky3 | risky | risky | True | 0 | 1 |
| G11_risky4 | risky | risky | True | 0 | 1 |
| G12_error | error | error | True | 2 | 0 |
| G13_error2 | error | error | True | 2 | 0 |
| G14_dead | error | error | True | 1 | 0 |
| G15_mixed | risky | risky | True | 0 | 1 |

- **Total Success Rate**: 100.00%
- **Average Nodes Visited**: 6.60

## 5. Failure analysis

1. **Retry or tool failure**: Handled by bounded loops (max_attempts) and evaluate node.
2. **Risky action without approval**: Prevented by mandatory HITL approval node.

## 6. Persistence / recovery evidence

Implemented SqliteSaver in persistence.py. Verified by checkpoints.db generation.

## 7. Extension work

**Persistence (SQLite)**: Implemented robust SQLite checkpointer for state durability.

## 8. Improvement plan

Productionize with LLM-as-judge and exponential backoff.
