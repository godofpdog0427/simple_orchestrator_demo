## Troubleshooting

### Rate Limit Errors (429 Too Many Requests)

**Symptom**: `HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 429 Too Many Requests"`

**What This Means**:
You've exceeded Anthropic's API rate limits. Rate limits are measured in:
- **RPM (Requests Per Minute)** - Number of API calls per minute
- **ITPM (Input Tokens Per Minute)** - Input tokens consumed per minute
- **OTPM (Output Tokens Per Minute)** - Output tokens generated per minute

**Why It Happens**:
1. **Low Usage Tier**: New accounts start at Tier 1 with very restrictive limits
2. **Rapid Requests**: ReAct loop makes multiple LLM calls in quick succession (up to 20 iterations)
3. **Large Context**: High token usage in complex tasks

**Solution (Automatic)**:
As of Phase 2.7, the orchestrator **automatically retries** with exponential backoff:
- Attempt 1: Wait 2 seconds, retry
- Attempt 2: Wait 4 seconds, retry
- Attempt 3: Wait 8 seconds, retry
- Attempt 4: Wait 16 seconds, retry
- Attempt 5: Wait 32 seconds, retry
- After 5 retries: Task fails with clear error message

**Manual Solutions**:

1. **Check Your Usage Tier**:
   - Visit https://console.anthropic.com/settings/limits
   - Higher tiers have much higher rate limits
   - Tier automatically increases as you use more API credits

2. **Enable Request Throttling** (optional):
   ```yaml
   # config/default.yaml or config/local.yaml
   llm:
     anthropic:
       throttle:
         enabled: true  # Prevents rapid consecutive requests
         min_request_interval: 0.5  # Wait 0.5s between requests
   ```

3. **Adjust Retry Settings** (if needed):
   ```yaml
   llm:
     anthropic:
       retry:
         max_retries: 10  # More retries for low-tier accounts
         base_delay: 3.0  # Longer initial wait
         max_delay: 120.0  # Allow up to 2 minutes between retries
   ```

4. **Reduce Task Complexity**:
   - Break large tasks into smaller subtasks
   - Use simpler prompts to reduce iterations
   - Lower `orchestrator.max_iterations` from 20 to 10

**Understanding Usage Tiers**:
- **Tier 1** (New accounts): Very low limits (e.g., 5 RPM, 20K ITPM)
- **Tier 2**: Requires $5 cumulative spend
- **Tier 3**: Requires $50 cumulative spend
- **Tier 4**: Requires $500 cumulative spend

Each tier dramatically increases rate limits. See: https://docs.anthropic.com/en/api/rate-limits

**Debug Logs**:
When 429 occurs, you'll see:
```
WARNING - Rate limit error (429) on attempt 1/6. Retrying in 2.0s...
(Tip: Check your usage tier at https://console.anthropic.com/settings/limits)
```

If all retries fail:
```
ERROR - Rate limit error persisted after 5 retries.
Your API usage tier may be too low.
Check https://console.anthropic.com/settings/limits
```

### API Key Not Found

**Symptom**: `Error: ANTHROPIC_API_KEY environment variable not set`

**Solution**:
1. Check `.env` file exists: `ls -la .env`
2. Verify key is set: `grep ANTHROPIC_API_KEY .env`
3. Ensure no quotes: `ANTHROPIC_API_KEY=sk-ant-xxx` (not `"sk-ant-xxx"`)
4. Restart shell or re-run `source .venv/bin/activate`

### Tool Not Found

**Symptom**: `Tool 'my_tool' not found in registry`

**Solution**:
1. Check tool is registered: `orchestrator tool list`
2. Verify tool is enabled in config:
   ```yaml
   tools:
     my_tool:
       enabled: true
   ```
3. Check registration in `ToolRegistry._register_builtin_tools()` or user_extensions

### LLM Not Using Tools

**Symptom**: LLM responds with text instead of calling tools

**Possible Causes**:
1. Tools not passed to API - check `_reasoning_loop()` passes `tools` parameter
2. Tool descriptions unclear - improve `description` and `parameters.description`
3. Task doesn't require tools - LLM correctly determined text response is sufficient

**Debug**:
```python
# Add logging in _reasoning_loop()
logger.debug(f"Calling LLM with {len(tools)} tools: {[t['name'] for t in tools]}")
```

### Import Errors

**Symptom**: `ModuleNotFoundError: No module named 'orchestrator'`

**Solution**:
1. Ensure in virtual environment: `which python` should show `.venv/bin/python`
2. Install in editable mode: `pip install -e ".[dev]"`
3. Check `pyproject.toml` exists and has correct `[project]` section

### Task Stuck in IN_PROGRESS

**Symptom**: Task never completes or fails

**Possible Causes**:
1. LLM infinite loop - check conversation history for repeated patterns
2. Tool timeout - increase `tools.bash.timeout` in config
3. Hook blocking - check hook logs for `action="block"`

**Debug**:
```bash
# Check state file
cat .orchestrator/state.json | jq '.tasks[] | select(.status == "IN_PROGRESS")'

# Check logs
tail -f .orchestrator/orchestrator.log
```

### High Token Usage

**Symptom**: Hitting token limits frequently

**Solutions**:
1. Reduce `max_tokens` in config
2. Use more focused task descriptions
3. Enable result caching (Phase 5)
4. Use subagents with token budgets (Phase 4)

---

