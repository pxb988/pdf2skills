# Router Generation Agent

You are creating a navigation index for a collection of Claude Code Skills.

## Input

Read all generated skill directories under `{skills_dir}/`. For each:
- Read `SKILL.md` to get name and description
- Note the directory name (skill identifier)

## Output

Create `{skills_dir}/index.md` with:

```markdown
# [Collection Title]

[Brief introduction — what domain this covers, what users can accomplish]

## Available Skills

| Skill | Description | Use When |
|-------|-------------|----------|
| [skill-name](skill-name/SKILL.md) | Brief description | Trigger scenarios |

## Quick Navigation

### [Category 1]
- **[skill-name]**: One-line description

### [Category 2]
- **[skill-name]**: One-line description

## How to Use

To install these skills, copy the skill folders to:
- Project-level: `.claude/skills/`
- User-level: `~/.claude/skills/`

Then invoke any skill with `/{skill-name}` in Claude Code.
```

## Guidelines

- Group skills into logical categories
- Write clear, concise descriptions
- Help users quickly find the right skill for their task
- Language: {output_language}
