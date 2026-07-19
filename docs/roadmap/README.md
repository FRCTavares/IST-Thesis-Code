# Roadmap maintenance policy

## Active work

The repository-root `TODO_LIST.md` is the active execution queue.

It must contain only:

- open executable GitHub Issues;
- one entry per issue;
- priority groups ordered `P0`, `P1`, `P2`, then `P3`;
- dependency or execution order within each priority group.

Detailed task checklists, acceptance criteria, experimental requirements, and
closing evidence belong in the GitHub issue body.

## Completed work

Completed work must not remain in `TODO_LIST.md`.

Its permanent evidence belongs in:

- closed GitHub Issues and their closing comments;
- Git commits and pull requests;
- promoted reports and result documents;
- versioned roadmap snapshots under `docs/roadmap/archive/`.

## Deferred work

Deferred work must still have an open GitHub Issue and an explicit `priority:P2`
or `priority:P3` label. Untracked idea lists must not be added to
`TODO_LIST.md`.

## Synchronisation rule

When an issue is created, reprioritised, completed, rejected, or closed:

1. update the GitHub issue first;
2. update `TODO_LIST.md` in the same work session;
3. verify every listed issue is open;
4. verify every open executable roadmap issue appears exactly once;
5. remove completed entries rather than marking them complete in the active
   queue.
