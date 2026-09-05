# Bag Folder Layout

The bag root is organised by role, not by experiment name.

Folder layout:

    bags/
      source/
        curated/        protected frequently reused source recordings
        official_flights/ protected original field-session recordings
      replay/            generated replay/evaluation outputs
      reference/         frozen known-good references and optional live aliases
      review/            optional quarantine for uncertain material

Rules:

- `source/` contains recorded input data and is protected by default.
- `replay/` contains generated outputs from experiments, replays, detector sweeps, runtime checks, or UI jobs.
- `reference/` contains frozen reference runs that should not be overwritten and may contain resolving convenience aliases.
- The historical `bags/annotation_inputs/` tree was removed during the July cleanup. Annotation work now uses real source/replay paths, resolving reference aliases when useful, and UI favourites.
- `review/` is optional quarantine for material not yet classified; absence of the directory does not make uncertain evidence disposable.
- Unknown or referenced evidence is retained until explicitly classified.
