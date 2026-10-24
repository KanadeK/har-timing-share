# Contributing

Small, reproducible bug reports and focused changes are welcome. Check the
documented scope before proposing a feature. Use synthetic fixtures; never attach
production exports, private paths, tokens, or personal data to an issue.

## Development

```console
python -m pip install -e . build==1.6.1 ruff==0.17.2
python -m ruff check .
python -m ruff format --check .
python -m unittest discover -s tests -v
python -m build
python tools/smoke.py
```

Add regression coverage for behavioral changes. Keep error messages actionable,
outputs deterministic, and runtime dependencies minimal. Document any output
schema changes and update CHANGELOG.md. Security concerns follow SECURITY.md.
The CI workflow only runs checks and builds; it never commits or pushes code.
