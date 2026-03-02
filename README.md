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
