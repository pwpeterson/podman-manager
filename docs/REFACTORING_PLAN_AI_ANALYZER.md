# AI Analyzer Refactoring Plan

## Current State
- Single large file (1500+ lines)
- Mixed responsibilities in one class
- Duplicate code patterns
- Hard to maintain and extend

## Proposed Structure

### 1. Core AI Analyzer (`ai_analyzer.py`)
```python
class AIAnalyzer:
    """Main coordinator for AI analysis"""
    def __init__(self, manager):
        self.manager = manager
        self.collectors = {
            'logs': LogsDataCollector(manager),
            'build_failure': BuildDataCollector(manager),
            'status': StatusDataCollector(manager),
            'performance': PerformanceDataCollector(manager)
        }
        self.prompt_generator = PromptGenerator()
        self.result_formatter = ResultFormatter()

    def ai_analyze(self, analysis_type, target, context_data=None, ai_agent=None, verbose=False):
        # Main orchestration logic
```

### 2. Data Collectors (`collectors/`)
- `base_collector.py` - Abstract base class
- `logs_collector.py` - Service logs and diagnostics
- `build_collector.py` - Build failure data
- `status_collector.py` - Service status data
- `performance_collector.py` - Performance metrics
- `system_collector.py` - System resources (shared)

### 3. Prompt Generation (`prompts/`)
- `prompt_generator.py` - Main prompt coordinator
- `logs_prompts.py` - Log analysis prompts
- `build_prompts.py` - Build failure prompts
- `status_prompts.py` - Status analysis prompts

### 4. Result Formatting (`formatters/`)
- `result_formatter.py` - Display and format results
- `troubleshooting_guides.py` - Basic troubleshooting fallbacks

## Benefits

1. **Single Responsibility**: Each class has one clear purpose
2. **Easier Testing**: Smaller, focused classes are easier to test
3. **Better Maintainability**: Changes to one analysis type don't affect others
4. **Extensibility**: Easy to add new analysis types
5. **Code Reuse**: Common functionality in base classes
6. **Cleaner Dependencies**: Clear separation of concerns

## Migration Strategy

1. **Phase 1**: Extract data collectors
2. **Phase 2**: Extract prompt generators
3. **Phase 3**: Extract result formatters
4. **Phase 4**: Update main AIAnalyzer class
5. **Phase 5**: Update imports in dependent files

## Implementation Priority

- **High**: Extract build failure components (most recent addition)
- **Medium**: Extract logs components (most complex)
- **Low**: Extract status/performance (simpler, less critical)

## Backward Compatibility

Maintain the same public interface (`ai_analyze` method) so existing code continues to work without changes.
