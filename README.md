# tachyon-dist-tools

CI/CD utilities for managing Tachyon distribution builds, versioning, and release metadata.

## CLI Tools

| Command | Description |
|---------|-------------|
| `tachyon-resolve-version` | Resolve semantic versions from git tags for release, prerelease, and stable channels |
| `tachyon-update-published-metadata` | Update release metadata in S3 with retry logic for concurrent writes |
| `tachyon-json-validator` | Validate JSON files against bundled JSON Schema Draft 2020-12 schemas |
| `tachyon-s3-updater` | Read/write S3 objects with optimistic locking via ETags |
| `tachyon-gh-note-builder` | Convert release metadata JSON to Markdown for GitHub release notes |

### Series-namespaced version streams

By default `tachyon-resolve-version` resolves a single stream of bare semver tags
(`1.2.19`, `1.2.20`, …). A repository that builds more than one product line from
one branch (e.g. the Tachyon composer building Ubuntu 24.04 **and** 26.04) can keep
each line on an independent version stream with namespaced tags:

```sh
# 24.04 stays on the bare stream (unchanged):
tachyon-resolve-version --build-type release                       # -> 1.2.20

# 26.04 uses a 'NN.NN/' tag stream; the printed version is always clean semver:
tachyon-resolve-version --build-type release   --tag-prefix "26.04/"                    # tag 26.04/1.3.0 -> 1.3.0
tachyon-resolve-version --build-type prerelease --tag-prefix "26.04/" \
    --seed-version 1.3.0 --build-id "build.$(git rev-parse --short HEAD)"               # -> 1.3.0-dev+build.<sha>
```

- `--tag-prefix` scopes every tag lookup to that stream, and strips the prefix from
  the resolved output (the prefix only ever lives on the git tag, e.g. `26.04/1.3.0`).
  Omitted or empty, behaviour is identical to before — bare tags, no prefix.
- `--seed-version` is the base a **prerelease** falls back to when its stream has no
  release tag yet, so a brand-new line's first prereleases carry the intended number
  (`1.3.0-dev+…`) instead of the generic `99.99.9999` placeholder.
- The `stable` channel does not support `--tag-prefix`.

## Installation

Install from the [latest GitHub release](https://github.com/particle-iot/tachyon-dist-tools/releases/latest):

```sh
pip install https://github.com/particle-iot/tachyon-dist-tools/releases/download/<version>/tachyon_dist_tools-<version>-py3-none-any.whl
```

## Development

```sh
make install   # creates venv and installs with dev dependencies
. .venv/bin/activate
pytest
```

## License

[Apache-2.0](LICENSE)
