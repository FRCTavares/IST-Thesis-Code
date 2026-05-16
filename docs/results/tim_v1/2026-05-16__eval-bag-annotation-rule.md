# Eval Bag Annotation Rule

Tracker IDs are online labels and are not stable across independent replay runs.

The same raw dataset bag can produce different tracker IDs when detector/tracker/TIM are rerun. Therefore, target-correctness annotations are valid only for the exact generated eval bag used during manual review.

Correct workflow:

1. Generate an eval bag.
2. Freeze it. Do not overwrite it.
3. Render overlay videos from that exact eval bag.
4. Annotate target correctness using the IDs visible in those overlay videos.
5. Run correctness evaluation on that exact eval bag.
6. Run all-score diagnostics on that exact eval bag.

Do not reuse ID-based annotations across regenerated eval bags.
