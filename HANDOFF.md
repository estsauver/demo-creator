# Demo Creator Plugin - Handoff Document

## Summary

Extracted the demo-creator plugin from `health_company/plugins/demo-creator` into a standalone repository at `~/Dev/demo-creator` and pushed to GitHub at `estsauver/demo-creator` (private).

## What Was Done

### 1. Repository Creation
- Created new repo at `~/Dev/demo-creator`
- Created private GitHub repo `estsauver/demo-creator`
- Single clean commit on main (squashed history)

### 2. Security Cleanup (All Complete)
- Renamed `FIBONACCI_VOICE_ID` → `ELEVENLABS_VOICE_ID` everywhere
- Removed hardcoded GCS bucket `fibonacci-demos` (now requires `GCS_BUCKET_NAME` env var)
- Removed hardcoded k8s context `k3d-fibonacci` (now uses `KUBE_CONTEXT` env var)
- Replaced `demo-agents.localhost` with configurable `DEMO_TARGET_URL`
- Replaced `FIB-123` issue prefixes with `ISSUE-123`
- Removed company email, paths, and "Fibonacci Bio" references
- Updated plugin.json author to "Earl St Sauver"

### 3. File Organization
- Moved docs to `docs/` directory
- Moved CLI scripts to `scripts/` directory
- Removed `claude-docs/` (external docs, not part of plugin)
- Removed demo artifacts and SECURITY_REVIEW.md
- Clean root with only essential files

### 4. Documentation
- New README.md with installation instructions, usage, troubleshooting
- Added note about plugin being extracted and needing adaptation
- MIT LICENSE file
- marketplace.json for plugin discovery

## Current State

### Files
```
~/Dev/demo-creator/
├── .claude-plugin/
│   ├── plugin.json         # Minimal manifest (name, description, version, author)
│   └── marketplace.json    # For marketplace discovery
├── commands/               # 5 command files (.md)
├── agents/                 # 12 agent files (.md)
├── skills/                 # Skill files
├── utils/                  # Python utilities
├── tests/                  # Test suite
├── docs/                   # Internal documentation
├── scripts/                # CLI utilities
└── README.md, LICENSE, pyproject.toml
```

### GitHub
- Repo: https://github.com/estsauver/demo-creator (private)
- Single commit: "Initial release: Demo Creator plugin for Claude Code"

## What's Still Broken

### Commands Not Being Discovered

**Symptom:** After installing the plugin, typing `/demo-creator` doesn't autocomplete to any commands like `/demo-creator:create`.

**What we tried:**
1. Added explicit `"commands": "./commands/"` to plugin.json → Got validation error "agents: Invalid input"
2. Tried array format `"commands": ["./commands/"]` → Same validation error
3. Removed all explicit paths (like working plugins use) → Plugin installs but commands not discovered

**Observations from working plugins:**
- Official plugins (linear, slack) have NO `commands`/`agents`/`skills` fields
- Local temporal plugin also has no explicit fields
- They all use auto-discovery

### Possible Theories

1. **Command frontmatter format wrong**
   - Demo-creator commands have `name: create` in frontmatter
   - Temporal commands do NOT have `name` field - just `description` and `argument-hint`
   - Maybe `name` field shouldn't be there? Filename should be the command name.

2. **Caching issue**
   - Old cached version might be interfering
   - Try: `rm -rf ~/.claude/plugins/cache/demo-creator`

3. **Marketplace vs direct install**
   - Maybe installing via marketplace has different discovery behavior
   - Try: `claude plugin add ~/Dev/demo-creator` directly

4. **Skills directory structure**
   - `skills/` has both `screenenv.md` and `skills/screenenv/SKILL.md`
   - Maybe the duplicate/nested structure is confusing the parser

## Most Likely Fix

**The `name` field in command frontmatter is probably the issue.**

Working temporal commands:
```yaml
---
description: List Temporal workflows in namespace
argument-hint: [namespace|--all] [--query "filter"]
allowed-tools: Bash(kubectl:*, git:*)
---
```

Broken demo-creator commands:
```yaml
---
name: create   # <-- THIS FIELD SHOULDN'T BE HERE
description: Create professional demo videos...
---
```

The command name comes from the **filename** (`create.md` → `/demo-creator:create`), not from frontmatter.

## Next Steps to Try

1. **Remove `name` field from command frontmatter** (MOST LIKELY FIX)
   ```bash
   cd ~/Dev/demo-creator/commands
   # Check temporal commands for reference format
   # Edit create.md, quick.md, etc. to remove name: field
   ```

2. **Clear plugin cache and reinstall**
   ```bash
   rm -rf ~/.claude/plugins/cache/demo-creator
   claude plugin marketplace remove demo-creator
   claude plugin marketplace add estsauver/demo-creator
   claude plugin install demo-creator@demo-creator
   ```

3. **Try direct local install**
   ```bash
   claude plugin add ~/Dev/demo-creator
   ```

4. **Check if skills structure is causing issues**
   - Remove `skills/screenenv.md` (keep only `skills/screenenv/SKILL.md`)
   - Or vice versa

5. **Debug mode**
   ```bash
   claude --debug
   # Then try /demo-creator to see what's being loaded
   ```

6. **Compare frontmatter exactly with working temporal plugin**
   ```
   # Temporal command format:
   ---
   description: Deep debug a failed workflow
   argument-hint: <workflow-id> [namespace]
   allowed-tools: Bash(kubectl:*, git:*)
   ---

   # Demo-creator current format:
   ---
   name: create
   description: Create professional demo videos...
   ---
   ```

## Environment Variables (For Reference)

| Variable | Purpose | Required |
|----------|---------|----------|
| `ELEVENLABS_API_KEY` | ElevenLabs TTS API key | Yes (for audio) |
| `ELEVENLABS_VOICE_ID` | Voice ID for narration | Yes (for audio) |
| `GCS_BUCKET_NAME` | Cloud storage bucket | Yes (for upload) |
| `KUBE_CONTEXT` | Kubernetes context | No (uses current) |
| `DEMO_TARGET_URL` | Application URL | No (defaults to localhost:3000) |

## Key Files to Check

- `~/.claude/plugins/installed_plugins.json` - see what's installed
- `~/.claude/plugins/cache/` - cached plugin files
- `~/.claude/plugins/marketplaces/` - marketplace data
- `/Users/earljstsauver/Dev/health_company/plugins/temporal/commands/*.md` - working command examples
