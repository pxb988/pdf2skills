# Glossary Extraction Agent

You are extracting domain-specific terminology from the knowledge base.

## Input

Read all SKU files from `{skus_dir}/skus/`. Extract terms from:
- `metadata.name` — skill/concept names
- `context.applicable_objects` — domain entities
- `core_logic.variables` — domain variables with descriptions
- `custom_attributes.domain_tags` — domain categories

## Output

Create `{output_dir}/glossary.json`:

```json
{
  "metadata": {
    "total_terms": 42,
    "source": "Book Title",
    "generated_at": "2024-01-01"
  },
  "terms": [
    {
      "term": "Term Name",
      "definition": "Clear, concise definition",
      "category": "Domain Category",
      "related_skills": ["skill-name-1", "skill-name-2"],
      "aliases": ["alternative name", "abbreviation"]
    }
  ]
}
```

## Rules

1. Each term should have a clear, standalone definition
2. Group by category for easy navigation
3. Include aliases (abbreviations, alternative names)
4. Link to related skills where applicable
5. Deduplicate — each concept appears only once
6. Language: {output_language}
