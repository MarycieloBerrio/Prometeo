# notebooks/

Exploration only: inspecting PSI/NTRS files, prototyping FlameVision thresholds, checking
extracted values. Apps never import from here.

- Use the backend environment: `cd apps/backend && uv sync --extra science --extra vision`,
  then `uv run --with jupyter jupyter lab ../../notebooks`.
- Import domain code (`from prometeo.domain.physics.metrics import …`) instead of re-implementing formulas.
- Anything that becomes real logic moves into `apps/backend/src/prometeo/` with tests.
- Clear outputs before committing. Never commit raw NASA files or videos.
