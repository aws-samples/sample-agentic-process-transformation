# Agent Workflow Patterns

Patterns for orchestrating multiple agents in a business process. Each pattern addresses a distinct coordination challenge — from dynamic dispatch to parallel fan-out to human oversight.

All implementations use Strands Agents with Amazon Bedrock.

## Patterns

| # | Pattern | Description | When to Use |
|---|---|---|---|
| 1 | **Routing** | Classifies incoming work and dispatches to the right specialist | When ambiguous input arrives and multiple specialists exist |
| 2 | **Parallelization** | Fan out independent tasks to multiple agents, then aggregate | When waiting is the bottleneck — multiple inputs must be analyzed simultaneously |
| 3 | **Human-in-the-Loop** | Agent pauses at decision points for human approval | When certain decisions require human judgment |
| 4 | **Reflect and Refine** | Generator + reviewer loop with feedback until quality passes | When quality review is a process requirement |
