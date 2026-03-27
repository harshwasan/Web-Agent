# Releases

Use semantic version tags for public publishing.

## Suggested flow

1. Update version numbers:
   - `widget/package.json`
   - `server/pyproject.toml`
2. Commit changes.
3. Create a git tag:

```bash
git tag v1.0.0
git push origin v1.0.0
```

4. Publish the widget:

```bash
cd widget
npm publish --access public
```

5. Publish the local bridge:

```bash
cd server
python -m build
twine upload dist/*
```

## Versioning guidance

- `v1.0.0`
  First public stable release.
- `v1.0.1`
  Small compatible fixes.
- Minor versions
  New backward-compatible features.
- Major versions
  Breaking API or bridge contract changes.
