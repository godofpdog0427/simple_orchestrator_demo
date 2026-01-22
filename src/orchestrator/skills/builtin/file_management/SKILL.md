---
name: file_management
description: "Organize, rename, move, and manage files and directories"
tools_required: [bash, file_read, file_write, file_delete]
version: "1.0.0"
---

# File Management

## Overview
Safe and efficient file and directory operations.

## When to Use
- Reorganizing project structure
- Renaming files or directories
- Moving files between locations
- Cleaning up temporary or generated files

## Safety Principles

### Before Any Operation
1. **List first**: Use `ls` to understand current state
2. **Dry run**: Preview changes when possible
3. **Backup important files**: Copy before destructive operations
4. **Verify paths**: Double-check source and destination
5. **Check permissions**: Ensure you have necessary rights

## Common Operations

### Creating Directories
```bash
# Create single directory
mkdir new_directory

# Create nested directories
mkdir -p path/to/nested/directory

# Create with specific permissions
mkdir -m 755 directory_name
```

### Moving/Renaming Files
```bash
# Rename file
mv old_name.txt new_name.txt

# Move file to directory
mv file.txt target_directory/

# Move multiple files
mv file1.txt file2.txt target_directory/

# Move and rename
mv source/file.txt target/new_name.txt
```

### Copying Files
```bash
# Copy file
cp source.txt destination.txt

# Copy directory recursively
cp -r source_dir/ destination_dir/

# Copy preserving attributes
cp -p file.txt backup.txt

# Copy with confirmation
cp -i file.txt existing_file.txt
```

### Deleting Files

#### ⚠️ DANGER ZONE
Always verify before deleting!

```bash
# List first to verify
ls target_directory/

# Delete single file (use file_delete tool if available)
rm file.txt

# Delete directory and contents (VERY DANGEROUS)
rm -rf directory/  # ⚠️ Use with extreme caution

# Safer: Delete with confirmation
rm -i file.txt
```

#### Deletion Checklist
- [ ] Verified exact path with `ls`
- [ ] Checked no important files included
- [ ] Created backup if needed
- [ ] Double-checked command before executing
- [ ] Not using wildcards near root or home directory

### Finding Files
```bash
# Find by name
find . -name "*.txt"

# Find modified in last 7 days
find . -mtime -7

# Find by size
find . -size +10M

# Find and delete (CAREFUL!)
find . -name "*.tmp" -delete
```

### Organizing Files

#### By Type
```bash
# Move all PDFs to docs folder
mkdir -p docs
mv *.pdf docs/

# Move images to images folder
mkdir -p images
mv *.{jpg,png,gif} images/
```

#### By Date
```bash
# Create dated directory
mkdir "archive_$(date +%Y%m%d)"

# Move old files to archive
find . -mtime +30 -exec mv {} archive/ \;
```

## Directory Structure Best Practices

### Project Layout
```
project/
├── src/           # Source code
├── tests/         # Test files
├── docs/          # Documentation
├── config/        # Configuration files
├── scripts/       # Utility scripts
├── data/          # Data files
└── build/         # Build artifacts (gitignored)
```

### Naming Conventions
- **Lowercase**: Use lowercase for cross-platform compatibility
- **Underscores or hyphens**: `my_file.txt` or `my-file.txt`
- **Descriptive**: `user_controller.py` not `uc.py`
- **Versioned**: `backup_20260115.sql` for backups

## Common Patterns

### Bulk Rename
```bash
# Add prefix to all files
for f in *.txt; do mv "$f" "prefix_$f"; done

# Change extension
for f in *.jpeg; do mv "$f" "${f%.jpeg}.jpg"; done

# Remove spaces from filenames
for f in *\ *; do mv "$f" "${f// /_}"; done
```

### Cleaning Up

#### Temporary Files
```bash
# Remove common temp files
rm -f *.tmp *.log *.cache

# Remove empty directories
find . -type d -empty -delete

# Remove build artifacts
rm -rf build/ dist/ *.egg-info/
```

#### Git-ignored Files
```bash
# Remove all gitignored files (CAREFUL!)
git clean -fdX  # Dry run: git clean -ndX
```

## Error Prevention

### ❌ Don't
- Use `rm -rf /` or `rm -rf /*` (catastrophic)
- Delete without verifying with `ls` first
- Use wildcards like `rm -rf *` in wrong directory
- Move files without checking destination exists
- Rename system directories
- Delete `.git` directory

### ✅ Do
- Always verify paths before destructive operations
- Use relative paths when possible
- Create backups before major reorganization
- Test commands on a few files first
- Use version control for important files
- Keep consistent naming conventions

## Recovery

### Accidentally Deleted
```bash
# If in git repository
git checkout -- deleted_file.txt

# Check if file is in trash (macOS/Linux with trash)
# (Depends on system)

# Recover from backup
cp backup/file.txt .
```

### Wrong Move/Rename
```bash
# Undo recent move
mv new_location/file.txt old_location/

# Check git status for tracked files
git status
git checkout -- moved_file.txt
```

## Useful Commands

```bash
# Disk usage by directory
du -h --max-depth=1 | sort -h

# Find large files
find . -type f -size +100M -exec ls -lh {} \;

# Count files in directory
ls -1 | wc -l

# Create directory structure
mkdir -p {src,tests,docs}/{python,javascript}

# Archive directory
tar -czf archive.tar.gz directory/

# Extract archive
tar -xzf archive.tar.gz
```
