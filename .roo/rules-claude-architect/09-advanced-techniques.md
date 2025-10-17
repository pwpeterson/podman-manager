# Advanced Techniques Rules

## Analyzing Complex Systems

**MUST** follow this systematic approach:

1. **Start with boundaries** - Define what's in scope, what's external
2. **Identify key entities** - Map core business objects and their relationships
3. **Map critical paths** - Identify essential user journeys and system flows
4. **Understand constraints** - Document non-negotiable requirements and limitations
5. **Look for hidden assumptions** - Question what seems obvious

## System Architecture Analysis

### Component Identification
**MUST** identify and document:
- Core business logic components
- Data access and storage layers
- Integration and communication layers
- User interface and presentation layers
- Cross-cutting concerns (security, logging, monitoring)

### Dependency Mapping
**MUST** map dependencies between:
- Internal components
- External services and APIs
- Data stores and caches
- Infrastructure components
- Third-party libraries and frameworks

### Failure Mode Analysis
**MUST** consider failure scenarios:
- Single points of failure
- Cascade failure patterns
- Data consistency issues
- Network partition handling
- Resource exhaustion scenarios

## Technology Evaluation Techniques

### Proof of Concept Strategy
**SHOULD** recommend POCs for:
- Unproven technologies in the context
- Performance-critical components
- Complex integrations
- New architectural patterns

### Benchmarking Approach
**MUST** define benchmarking criteria:
- Performance metrics (latency, throughput)
- Resource utilization (CPU, memory, storage)
- Scalability characteristics
- Operational complexity

### Risk Assessment Matrix
**MUST** evaluate technologies on:
- **Probability** of issues (High/Medium/Low)
- **Impact** of issues (High/Medium/Low)
- **Mitigation** difficulty (Hard/Medium/Easy)

## Architecture Pattern Selection

### Pattern Evaluation Framework
**MUST** assess patterns based on:
- **Complexity** - Implementation and maintenance overhead
- **Scalability** - Ability to handle growth
- **Flexibility** - Adaptability to changing requirements
- **Team Fit** - Match with team skills and experience
- **Ecosystem** - Tool and library support

### Common Pattern Applications
**SHOULD** consider these patterns:

**Layered Architecture**
- Good for: Traditional web apps, clear separation
- Trade-offs: Can become rigid, performance overhead

**Microservices**
- Good for: Large teams, independent deployment
- Trade-offs: Increased complexity, distributed challenges

**Event-Driven**
- Good for: Loose coupling, async processing
- Trade-offs: Debugging complexity, eventual consistency

**CQRS**
- Good for: Read-heavy systems, complex domains
- Trade-offs: Increased complexity, data sync

**Hexagonal**
- Good for: Testability and external dependency isolation
- Trade-offs: Additional abstraction layers

## Performance Architecture

### Performance Requirements Analysis
**MUST** define:
- Response time requirements (p50, p95, p99)
- Throughput requirements (requests/second, transactions/minute)
- Concurrency requirements (simultaneous users)
- Data volume requirements (storage, processing)

### Scalability Planning
**MUST** plan for:
- **Horizontal scaling** - Adding more instances
- **Vertical scaling** - Adding more resources per instance
- **Data partitioning** - Sharding strategies
- **Caching strategies** - Multiple cache layers

### Bottleneck Identification
**SHOULD** analyze potential bottlenecks:
- Database query performance
- Network latency and bandwidth
- CPU-intensive operations
- Memory usage patterns
- I/O operations

## Security Architecture

### Security-by-Design Principles
**MUST** apply:
- **Defense in depth** - Multiple security layers
- **Least privilege** - Minimal necessary permissions
- **Fail secure** - Secure defaults when systems fail
- **Zero trust** - Verify everything, trust nothing

### Threat Modeling
**SHOULD** identify:
- **Assets** - What needs protection
- **Threats** - What could go wrong
- **Vulnerabilities** - How threats could succeed
- **Mitigations** - How to prevent or detect threats

## Data Architecture

### Data Modeling Strategies
**MUST** consider:
- **Consistency requirements** - ACID vs eventual consistency
- **Query patterns** - Read vs write optimization
- **Data relationships** - Relational vs document vs graph
- **Schema evolution** - How data models will change

### Storage Technology Selection
**SHOULD** evaluate:
- **Relational databases** - For complex relationships and ACID
- **Document stores** - For flexible schemas and JSON data
- **Key-value stores** - For simple, high-performance access
- **Graph databases** - For complex relationship queries
- **Time-series databases** - For metrics and monitoring data

## Integration Architecture

### Integration Pattern Selection
**MUST** choose appropriate patterns:
- **Synchronous** - For immediate consistency needs
- **Asynchronous** - For loose coupling and resilience
- **Event-driven** - For reactive architectures
- **Batch processing** - For large data volumes

### API Design Principles
**MUST** follow:
- **Consistency** - Uniform naming and behavior
- **Versioning** - Backward compatibility strategy
- **Error handling** - Meaningful error responses
- **Documentation** - Clear API specifications

## Monitoring and Observability

### Observability Strategy
**MUST** plan for:
- **Metrics** - System and business metrics
- **Logging** - Structured, searchable logs
- **Tracing** - Request flow across services
- **Alerting** - Proactive issue detection

### Health Check Design
**MUST** implement:
- **Liveness checks** - Is the service running?
- **Readiness checks** - Is the service ready to handle requests?
- **Dependency checks** - Are external dependencies available?

## Managing Technical Debt

### Debt Classification
**SHOULD** categorize debt as:
- **Tactical debt** - Short-term shortcuts for delivery
- **Strategic debt** - Architectural decisions that limit future options
- **Accidental debt** - Unintended complexity from poor decisions

### Debt Management Strategy
**MUST** plan for:
- **Documentation** - Record all conscious trade-offs
- **Prioritization** - Impact vs effort analysis
- **Incremental improvement** - Continuous refactoring
- **Prevention** - Architecture reviews and standards
