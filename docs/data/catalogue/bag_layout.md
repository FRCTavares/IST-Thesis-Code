# Bag Folder Layout

The bag root is organised by role, not by experiment name.

Folder layout:

    bags/
      source/
        curated/        selected source bags used often
        archive/        older/raw/full historical recordings
      annotation_inputs/ bags used to create or inspect manual annotations
      replay/            generated replay/evaluation outputs
      reference/         frozen known-good reference runs
      review/            quarantined temporary or uncertain material

Rules:

- source/ contains recorded input data.
- replay/ contains generated outputs from experiments, replays, detector sweeps, runtime checks, or UI jobs.
- reference/ contains frozen reference runs that should not be overwritten.
- annotation_inputs/ contains bags useful for manual annotation workflows.
- review/ contains material not deleted yet, but not part of the active clean dataset.
