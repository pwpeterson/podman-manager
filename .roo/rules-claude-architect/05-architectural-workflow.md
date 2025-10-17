# Architectural Workflow Rules

## Phase 1: Discovery & Analysis

### Understand Requirements

**MUST** clarify functional requirements

**MUST** identify non-functional requirements

**MUST** understand constraints (budget, timeline, skills)

**MUST** identify key stakeholders

**SHOULD** document assumptions

**MUST** ask clarifying questions early and often

**MUST** clarify priorities and success criteria

### Analyze Context

**MUST** understand existing system

**MUST** identify integration points

**SHOULD** review similar systems

**SHOULD** consult ConPort for past decisions

**MUST** understand data flow and volume

**MUST** read relevant files to understand existing architecture

**MUST** use list_code_definition_names to map system structure

**SHOULD** search for patterns and conventions with search_files

**SHOULD** analyze git history for evolution and pain points

### Research Context

**MUST** review product_context for project goals and constraints

**SHOULD** check active_context for ongoing work

**SHOULD** search decisions for related past choices

**SHOULD** review system_patterns for established conventions

**SHOULD** use semantic_search_conport for conceptual queries

## Phase 2: Design & Decision Making

### Generate Alternatives

**MUST** consider multiple approaches to solving the problem

**SHOULD** research proven patterns for similar problems

**SHOULD** evaluate emerging vs. established technologies

**SHOULD** think creatively about unconventional solutions

### Evaluate Trade-offs

**MUST** assess each alternative on:
- **Complexity** - Development and maintenance burden
- **Performance** - Scalability, latency, throughput
- **Cost** - Infrastructure, licensing, development time
- **Risk** - Technical maturity, team expertise, vendor lock-in
- **Flexibility** - Future extensibility and adaptability
- **Security** - Attack surface, compliance, data protection
- **Operations** - Monitoring, debugging, deployment

### Make Decisions

**MUST** for each significant decision:
1. State the decision clearly
2. Explain the rationale (why this over alternatives)
3. Document implementation approach
4. Identify risks and mitigation strategies
5. Log to ConPort immediately

### Design Solution

**MUST** start with high-level architecture

**MUST** identify major components

**MUST** define interfaces between components

**SHOULD** consider multiple approaches

**MUST** evaluate trade-offs

**MUST** define component boundaries and responsibilities

**MUST** specify interfaces and contracts

**SHOULD** plan data flow and state management

**MUST** design for failure and recovery

**MUST** consider security at every layer

## Phase 3: Planning & Documentation

### Create Implementation Roadmap

**MUST** use update_todo_list to break down implementation:
- Organize by logical phases (not just linear steps)
- Identify dependencies between tasks
- Specify acceptance criteria for each task
- Estimate complexity and risk
- Note which tasks can be parallelized

### Document Decisions

**MUST** log every architectural decision to ConPort

**MUST** build knowledge graph by linking related items

**SHOULD** document architectural patterns for future reference

### Risk Analysis

**MUST** document potential risks and mitigation strategies:
- Technical risks (unproven technology, complexity)
- Operational risks (monitoring, scaling, recovery)
- Team risks (skills gap, knowledge silos)
- Timeline risks (dependencies, unknowns)

### Success Metrics

**MUST** define how success will be measured:
- Performance benchmarks
- Reliability targets
- User experience goals
- Development velocity improvements

## Phase 4: Review & Handoff

### Present Solution

**MUST** create comprehensive documentation including:
- Executive summary (high-level overview)
- Architecture diagrams with explanations
- Key decisions with rationale
- Implementation roadmap
- Risk analysis and mitigations
- Success metrics
- Open questions and assumptions

### Iterate Based on Feedback

**SHOULD** be open to alternative perspectives

**SHOULD** explain trade-offs when defending decisions

**MUST** adapt plan based on new constraints or information

**MUST** update ConPort decisions if approach changes

### Handoff to Implementation

**MUST** use switch_mode when plan is approved:

```xml
<switch_mode>
<mode_slug>claude-code</mode_slug>
<reason>Architecture approved. Implementation plan documented in ConPort. Ready to begin development.</reason>
</switch_mode>
```
