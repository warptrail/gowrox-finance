# API Taxonomy Contract — Gowrox Finance

This document encodes durable classification rules, relationship invariants, and API expectations for taxonomy endpoints. All backend API work must comply with these constraints.

## Taxonomy Structure Rules

**Groups ↔ Categories Relationship**

- A **Group** is a stable economic domain.
- A **Category** belongs to exactly *one* Group (one-to-many: Groups → Categories).
- The API must preserve this invariant.
- No Category may appear in multiple Groups.

**Transactions → Category**

- A Transaction has *one* Category assignment.
- The Group is implied via the parent Category.
- The API must reflect this deterministically.

**Tags**

- Tags are freeform and non-hierarchical.
- Tags do not imply Group or Category membership.
- Taxonomy endpoints must not constrain or infer tag behavior.

## Endpoint Expectations & Stability Guarantees

**Immutability Constraints**

- Group and Category IDs are stable identifiers.
- Clients (e.g., React UI) may safely cache IDs and names across sessions.
- Existing IDs must never be renamed, reassigned, or repurposed without a formal migration plan.

**Field Names / Response Shape** Frontend consumers expect the following shape:

```
[
  {
    group_id: string,
    group_name: string,
    category_count: number,
    categories: [
      {
        category_id: string,
        category_name: string
      }
    ]
  }
]
```

Field names must match exactly.

**Sorting Guarantees**

- Groups must be sorted by `group_name` (ascending, alphabetical).
- Categories must be sorted by `category_name` (ascending, alphabetical).

Sorting must be stable across requests to support predictable React diffing.

## Category & Group Semantics

Classification is **structural**, not emotional or interpretive.

- Groups represent economic domains.
- Categories represent functional transaction classes.
- No behavioral, psychological, or ideological meaning should be inferred at the API layer.

The backend exposes ground-truth relationships only. Interpretation belongs in the UI layer.

## API Versioning & Backward Compatibility

Taxonomy data is core structural ground truth.

- Additive changes only.
- Do not remove, rename, or repurpose existing entities.
- Schema changes must include a backward-compatible migration plan.

Recommended versioning pattern:

```
Accept: application/vnd.gowrox.v1+json
```

or

```
Accept: application/vnd.gowrox.v2+json
```

Existing versions must remain supported until clients migrate.

## Failure Modes & Edge Cases

**Empty Groups**

- Groups with zero categories must still be returned.
- `category_count = 0`
- `categories = []`

**Incomplete or Sparse Data**

- Missing relationships must not cause crashes.
- Serialize empty but structurally valid responses.

**Concurrency**

- Endpoints must be idempotent.
- Safe for concurrent access by multiple clients.

## React UI Integration Assumptions

Frontend clients assume the following TypeScript-compatible structures:

```
type Group = {
  group_id: string;
  group_name: string;
  category_count: number;
  categories: Category[];
};

type Category = {
  category_id: string;
  category_name: string;
};
```

Implications:

- IDs are stable React keys.
- Ordering stability is required.
- Shape consistency is mandatory.

---

## Usage by Codex / Agents

- This file defines **hard constraints**, not suggestions.
- All taxonomy-related endpoints must comply with this contract.
- `AGENTS.md` should reference this file rather than duplicating its contents.

