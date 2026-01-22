## ⚠️ CRITICAL: Git Branch Strategy

**READ THIS FIRST - MANDATORY RULES**

This project uses a strict branch strategy to prevent catastrophic data loss:

### Branch Structure

- **`main`** - Production-ready code. **PROTECTED BRANCH**
- **`dev`** - Development integration branch. **Default working branch**
- **`feature/*`** - Feature branches (created from `dev`)
- **`fix/*`** - Bug fix branches (created from `dev`)

### Branching Rules for Claude Code

**YOU MUST FOLLOW THESE RULES:**

1. **NEVER merge to `main`** - Only the human user can merge to `main`
2. **ALWAYS create feature branches from `dev`** - Never from `main`
3. **ALWAYS merge your changes to `dev`** - Never to `main`
4. **NEVER force push** - Especially not to `main` or `dev`
5. **ALWAYS work on feature branches** - Format: `feature/description` or `fix/description`

### Workflow for Claude Code

```bash
# 1. Start from dev branch
git checkout dev
git pull origin dev  # Get latest changes

# 2. Create feature branch
git checkout -b feature/your-feature-name

# 3. Make changes and commit
git add .
git commit -m "feat: your changes"

# 4. Push feature branch
git push -u origin feature/your-feature-name

# 5. Merge to dev (NEVER to main)
git checkout dev
git merge feature/your-feature-name
git push origin dev

# 6. Delete feature branch (optional)
git branch -d feature/your-feature-name
```

### What You CAN Do

✅ Create feature branches from `dev`
✅ Commit to feature branches
✅ Merge feature branches to `dev`
✅ Push to `dev` branch
✅ Create pull requests (for review)

### What You CANNOT Do

❌ **Merge to `main`** (NEVER)
❌ **Force push to any branch**
❌ **Delete `main` or `dev` branches**
❌ **Create branches from `main`** (use `dev` instead)
❌ **Push directly to `main`**

### Emergency Recovery

If you accidentally work on the wrong branch:

```bash
# Save your work
git stash

# Switch to correct branch
git checkout dev
git checkout -b feature/your-feature

# Restore your work
git stash pop
```

### Why This Matters

This project was previously lost due to an accidental `/clear` command. The branch strategy ensures:
- `main` always has stable, working code
- All development happens in isolated feature branches
- Only the human user controls what goes to production (`main`)
- Claude Code cannot accidentally destroy the codebase

---

