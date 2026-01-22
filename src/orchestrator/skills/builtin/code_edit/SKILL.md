---
name: code_edit
description: "Edit existing code files with proper diff handling and validation"
tools_required: [file_read, file_write]
version: "1.0.0"
---

# Code Edit

## Overview
This skill guides safe and effective code editing with proper validation and error handling.

## When to Use
- Modifying existing code files
- Refactoring code
- Fixing bugs
- Adding new features to existing files

## Process

### 1. Read First
Always read the file before editing:
- Understand the current structure
- Identify dependencies
- Check for existing patterns

### 2. Plan Changes
- Identify exact lines to modify
- Consider side effects
- Check for breaking changes

### 3. Apply Edits
- Make minimal, focused changes
- Preserve existing formatting and style
- Update related comments/documentation

### 4. Validate
- Check syntax if possible
- Verify imports/dependencies still work
- Consider running tests

## Best Practices

### ✅ Do
- Read the file before editing
- Make small, incremental changes
- Preserve code style and formatting
- Update comments when changing logic
- Consider backward compatibility

### ❌ Don't
- Edit without reading first
- Make unrelated changes in one edit
- Break existing API contracts without migration
- Remove error handling
- Ignore linting/formatting rules

## Common Patterns

### Adding a Function
```python
# 1. Read file to find insertion point
# 2. Add function after similar functions
# 3. Maintain alphabetical or logical ordering
# 4. Include docstring
```

### Refactoring
```python
# 1. Extract duplicated code into helper functions
# 2. Update all call sites
# 3. Preserve existing behavior
# 4. Add tests for new functions
```

### Bug Fix
```python
# 1. Identify root cause
# 2. Fix minimal code to resolve issue
# 3. Add validation/error handling
# 4. Consider test case for regression
```

## Example Workflow

```
1. file_read("src/app.py")
2. Identify section to modify
3. file_write with targeted changes
4. Consider if related files need updates
```
