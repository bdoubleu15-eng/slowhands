# SlowHands Examples

Example scripts that can be created, modified, and executed by the SlowHands agent.

## Directory Structure

```
examples/
├── basic/
│   └── calculator.py      # Simple add-only calculator with 100k limit
└── advanced/
    └── calculator.py      # Full-featured calculator with math functions
```

## Basic Calculator

A simple add-only calculator demonstrating fundamental Python concepts.

**Features:**
- Addition with limit checking (100,000 max)
- Error handling for invalid inputs
- Interactive and demo modes

**Usage:**
```bash
# Run demonstration
python examples/basic/calculator.py

# Interactive mode
python examples/basic/calculator.py --interactive
```

## Advanced Calculator

A full-featured calculator with arithmetic, trigonometry, and logarithms.

**Features:**
- Basic operations: `+`, `-`, `*`, `/`, `%`, `^`
- Functions: `sqrt()`, `sin()`, `cos()`, `tan()`, `log()`, `ln()`
- Memory storage for results
- Expression evaluation

**Usage:**
```bash
# Interactive mode (default)
python examples/advanced/calculator.py

# Run demonstration
python examples/advanced/calculator.py --demo
```

## Using with SlowHands

These examples are designed to be:
1. **Created** by the agent from scratch
2. **Modified** to add features or fix bugs
3. **Executed** to verify they work correctly

Try prompting the agent with:
- "Create a simple calculator that adds numbers"
- "Modify the calculator to support subtraction"
- "Add error handling to the calculator"
- "Write tests for the calculator"
