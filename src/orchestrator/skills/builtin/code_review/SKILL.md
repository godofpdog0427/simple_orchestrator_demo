---
name: code_review
description: "Review code for bugs, style issues, security vulnerabilities, and best practices"
tools_required: [file_read]
version: "1.0.0"
---

# Code Review

## Overview
Systematic code review focusing on correctness, security, style, and maintainability.

## When to Use
- Pull request review
- Security audit
- Code quality assessment
- Identifying technical debt

## Review Checklist

### 1. Correctness
- [ ] Logic errors or edge cases
- [ ] Off-by-one errors
- [ ] Null/undefined handling
- [ ] Type mismatches
- [ ] Resource leaks (file handles, connections)

### 2. Security
- [ ] SQL injection vulnerabilities
- [ ] XSS vulnerabilities
- [ ] Authentication/authorization checks
- [ ] Sensitive data exposure
- [ ] Unsafe deserialization
- [ ] Command injection risks

### 3. Performance
- [ ] N+1 queries
- [ ] Inefficient algorithms (O(n²) where O(n) possible)
- [ ] Unnecessary loops or computations
- [ ] Missing caching opportunities
- [ ] Memory leaks

### 4. Code Style
- [ ] Consistent naming conventions
- [ ] Proper error handling
- [ ] Meaningful variable names
- [ ] Adequate comments/documentation
- [ ] Function/method length (single responsibility)

### 5. Testing
- [ ] Test coverage for new code
- [ ] Edge cases tested
- [ ] Error paths tested
- [ ] Mocks used appropriately

## Review Process

1. **Understand Context**: Read related code and documentation
2. **Check Correctness**: Verify logic and edge cases
3. **Security Scan**: Look for common vulnerabilities
4. **Style Review**: Check consistency and readability
5. **Test Coverage**: Verify adequate testing
6. **Provide Feedback**: Constructive, specific suggestions

## Common Issues

### Security
```python
# ❌ Bad: SQL injection
query = f"SELECT * FROM users WHERE id = {user_id}"

# ✅ Good: Parameterized query
query = "SELECT * FROM users WHERE id = ?"
cursor.execute(query, (user_id,))
```

### Performance
```python
# ❌ Bad: N+1 queries
for user in users:
    posts = db.query(f"SELECT * FROM posts WHERE user_id = {user.id}")

# ✅ Good: Single query with join
posts = db.query("SELECT * FROM posts WHERE user_id IN (?)", user_ids)
```

### Error Handling
```python
# ❌ Bad: Silent failure
try:
    result = risky_operation()
except:
    pass

# ✅ Good: Proper error handling
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    return default_value
```

## Review Feedback Format

- **Severity**: Critical, High, Medium, Low
- **Location**: File and line number
- **Issue**: Clear description of problem
- **Suggestion**: Specific fix or improvement
- **Example**: Code snippet if helpful
