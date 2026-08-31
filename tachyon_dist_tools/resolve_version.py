import os
import sys
import argparse
from git import Repo
import semver
sys.modules.pop('github', None)  # Ensure the local file isn't loaded
from github import Github

# Configuration
DEFAULT_BRANCH_NAME = "develop"


def log_debug(message):
    """Logs debug messages to stderr."""
    print(message, file=sys.stderr)


def strip_tag_prefix(name, prefix=""):
    """Return the semver portion of a tag name for the given stream, or None.

    With an empty prefix (the default) the tag is returned unchanged -- this is
    the historical, single-stream behaviour. With a non-empty prefix (e.g.
    "26.04/") the tag must start with it; the prefix is stripped and the
    remainder returned, so callers can parse/compare a clean semver. Tags that
    do not belong to the prefixed stream return None and are ignored.
    """
    if not prefix:
        return name
    if not name.startswith(prefix):
        return None
    return name[len(prefix):]


def get_latest_version_tag(repo, prefix=""):
    """Returns the latest semver tag in the repository (within a tag stream).

    `prefix` selects a series-namespaced tag stream (e.g. "26.04/"); the default
    empty prefix considers every bare semver tag, exactly as before.
    """
    valid_tags = []
    for tag in repo.tags:
        v = strip_tag_prefix(tag.name, prefix)
        if v is not None and semver.VersionInfo.is_valid(v):
            valid_tags.append(v)
    return max(valid_tags, key=semver.VersionInfo.parse, default="1.0.0")

def tag_exists(repo, tag_name):
    """Check if a tag exists in the repository."""
    return tag_name in [tag.name for tag in repo.tags]


def infer_github_repo(repo):
    """
    Infers the GitHub repository owner and name from the remote URL.

    Args:
        repo (Repo): GitPython Repo object.

    Returns:
        str: Repository name in the format "owner/repo".
    """
    remotes = repo.remotes
    if not remotes:
        raise ValueError("No remotes found for the repository.")

    # Assume 'origin' is the default remote
    origin_url = remotes.origin.url
    if origin_url.startswith("git@"):
        # Parse SSH URL: git@github.com:owner/repo.git
        parts = origin_url.split(":")
        repo_path = parts[1].replace(".git", "")
    elif origin_url.startswith("https://"):
        # Parse HTTPS URL: https://github.com/owner/repo.git
        parts = origin_url.split("/")
        repo_path = "/".join(parts[-2:]).replace(".git", "")
    else:
        raise ValueError(f"Unsupported remote URL format: {origin_url}")

    log_debug(f"Inferred GitHub repository: {repo_path}")
    return repo_path


def create_version_tag_with_github(repo, version, github_token):
    """
    Creates a new tag for the given version using the GitHub API.

    Args:
        repo (Repo): GitPython Repo object.
        version (str): The version tag to create.
        github_token (str): GitHub personal access token.

    Returns:
        str: The created tag name.
    """
    # Infer the repository name
    repo_name = infer_github_repo(repo)

    # Initialize GitHub client
    g = Github(github_token)
    gh_repo = g.get_repo(repo_name)

    # Get the current commit SHA
    commit_sha = repo.head.commit.hexsha

    # Create a new GitHub reference for the tag
    ref = f"refs/tags/{version}"
    gh_repo.create_git_ref(ref=ref, sha=commit_sha)
    log_debug(f"Tag {version} created on GitHub at commit {commit_sha}")
    return version


def find_ancestral_release_version(repo, prefix=None, relative_to="HEAD"):
    """Finds the most recent semver tag in the commit history."""
    commit_log = repo.git.log("--simplify-by-decoration", "--pretty=format:%D", relative_to)

    tags_in_history = []
    for line in commit_log.splitlines():
        for entry in line.split(","):
            if "tag: " in entry:
                tags_in_history.append(entry.split("tag: ")[1].strip())

    for tag in tags_in_history:
        if prefix and not tag.startswith(prefix):
            continue

        tagVersion = tag[len(prefix):] if prefix else tag

        if semver.VersionInfo.is_valid(tagVersion):
            return tag
    return None


def get_semver_tags_on_commit(repo, prefix=""):
    """
    Retrieves all tags on the current commit and filters them to include only valid SemVer values.

    Args:
        repo (Repo): GitPython Repo object.
        prefix (str): Tag-stream prefix (e.g. "26.04/"); default "" == the bare
            single-stream behaviour. Tags outside the stream are ignored and the
            prefix is stripped from the returned versions.

    Returns:
        list: A list of valid SemVer tags (sorted by version, descending).
    """
    # Get all tags pointing to the current commit, reduced to this stream's semver.
    tags_on_commit = [
        v for v in (
            strip_tag_prefix(tag.name, prefix)
            for tag in repo.tags if tag.commit == repo.head.commit
        ) if v is not None
    ]

    # Filter tags to include only valid SemVer values
    semver_tags = [tag for tag in tags_on_commit if semver.Version.is_valid(tag) and not semver.Version.parse(tag).prerelease and not semver.Version.parse(tag).build]

    # Sort SemVer tags in descending order (highest version first)
    semver_tags_sorted = sorted(semver_tags, key=semver.Version.parse, reverse=True)

    return semver_tags_sorted

def get_stable_tags_on_commit(repo):
    """
    Retrieves all stable tags on the current commit and filters them to include only valid SemVer values.

    Args:
        repo (Repo): GitPython Repo object.

    Returns:
        list: A list of valid stable SemVer tags (sorted by version, descending).
    """
    # Get all tags pointing to the current commit
    tags_on_commit = [
        tag.name for tag in repo.tags if tag.commit == repo.head.commit
    ]

    # Filter tags to include only valid stable SemVer values
    stable_tags = []
    stable_prefix = "stable-"
    for tag in tags_on_commit:
        if tag.startswith(stable_prefix) and semver.Version.is_valid(tag[len(stable_prefix):]):
            version = semver.Version.parse(tag[len(stable_prefix):])
            if version.prerelease or version.build:
                raise ValueError(f"Tag {tag} is a pre-release version, which is not allowed for stable tags.  This tag should be removed.")
            if tag[len(stable_prefix):] not in tags_on_commit:
                raise ValueError(f"There is no matching version tag for {tag} on the current commit.  This needs to be fixed.")
            stable_tags.append(tag[len(stable_prefix):])

    # Sort stable SemVer tags in descending order (highest version first)
    stable_tags_sorted = sorted(stable_tags, key=semver.Version.parse, reverse=True)

    return stable_tags_sorted

def resolve_stable_version(repo):
    """Resolve the latest pre-existing version tag on this commit."""
    commit_versions = get_stable_tags_on_commit(repo)
    if commit_versions:
        # If there are existing tags on the commit, use the latest one rather than bumping the latest version
        return commit_versions[0]

    raise RuntimeError("No valid semver tags found on this commit.")

def resolve_release_version(repo, prefix=""):
    """Resolve the version number for a release build.

    `prefix` scopes resolution to a series-namespaced tag stream (e.g. "26.04/");
    default "" resolves the bare stream exactly as before. The returned version
    is always clean semver (the prefix is never part of the output).
    """
    latest_version = get_latest_version_tag(repo, prefix)
    commit_versions = get_semver_tags_on_commit(repo, prefix)
    if commit_versions:
        # If there are existing tags on the commit, use the latest one rather than bumping the latest version
        return commit_versions[0]

    return str(semver.VersionInfo.parse(latest_version).bump_patch())

def resolve_prerelease_version(repo, build_id, prefix="", seed_version="99.99.9999"):
    """Resolve the version number for a prerelease build.

    Anchors on the nearest ancestral release tag in this stream. `prefix` scopes
    to a series-namespaced stream; the prefix is stripped from the base version.
    `seed_version` is the fallback when the stream has no ancestral tag yet -- for
    a brand-new series this is how its first prereleases carry the intended
    number (e.g. 1.3.0) instead of the generic 99.99.9999 placeholder.
    """
    ancestral_tag = find_ancestral_release_version(repo, prefix or None)
    if not ancestral_tag:
        base_version = seed_version
    else:
        base_version = ancestral_tag[len(prefix):] if prefix else ancestral_tag
    return f"{base_version}-dev+{build_id}"


def main():
    parser = argparse.ArgumentParser(description="Resolve the version number for the current build.")
    parser.add_argument("--build-id", type=str, default="", help="The build ID to use for versioning")
    parser.add_argument("--build-type", type=str, default="prerelease", help="The build type to use for versioning")
    parser.add_argument("--release-channel", type=str, default="latest", help="The release channel to use for versioning")
    parser.add_argument("--get-previous-version", action="store_true", help="Get the previous version tag instead of resolving a new one")
    parser.add_argument("--create-tag", action="store_true", help="Create a new tag for the resolved version")
    parser.add_argument("--tag-prefix", type=str, default="",
                        help="Resolve within a series-namespaced tag stream, e.g. '26.04/'. "
                             "Default (empty) uses the single bare-semver stream. The resolved "
                             "version printed to stdout is always clean semver; the prefix is only "
                             "applied to the underlying git tag.")
    parser.add_argument("--seed-version", type=str, default="99.99.9999",
                        help="Fallback base version for a prerelease when the (prefixed) stream has "
                             "no ancestral release tag yet -- used to seed a brand-new series' first "
                             "prereleases at the intended number (e.g. 1.3.0).")
    args = parser.parse_args()

    repo = Repo(".")
    if repo.bare:
        raise RuntimeError("Not a valid git repository")

    # GitHub configuration
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token and args.create_tag:
        raise RuntimeError("Environment variable GITHUB_TOKEN must be set to create a tag")

    build_type = args.build_type
    release_channel = args.release_channel
    tag_prefix = args.tag_prefix

    if release_channel == "stable":
        if build_type != "release":
            raise ValueError("Release channel 'stable' can only be used with build type 'release'")
        if args.create_tag:
            raise ValueError("Create tag option cannot be used with release channel 'stable'")
        if tag_prefix:
            # The stable channel keys off a 'stable-<semver>' prefix; combining it with a
            # series prefix is not defined. 26.04's stable channel is out of scope for now.
            raise ValueError("--tag-prefix is not supported with release channel 'stable'")

    if build_type == "prerelease" and not args.build_id:
        raise ValueError("Build ID must be provided for prerelease builds")

    version = None

    if args.get_previous_version:
        if build_type == "release" and release_channel == "stable":
            version = find_ancestral_release_version(repo, "stable-", "HEAD~")
        elif build_type == "release":
            # Return the full (prefixed) tag: it must resolve as a git ref for the
            # downstream changelog range. For the bare stream this is unchanged.
            version = find_ancestral_release_version(repo, tag_prefix or None, "HEAD~")
        else:
            raise ValueError("Cannot get previous version for prerelease builds")
        print(version)
        return

    if build_type == "release" and release_channel == "stable":
        version = resolve_stable_version(repo)
    elif build_type == "release":
        version = resolve_release_version(repo, tag_prefix)
    else:
        version = resolve_prerelease_version(repo, args.build_id, tag_prefix, args.seed_version)

    if args.create_tag:
      # The git tag carries the stream prefix; the printed version stays clean semver.
      tag_name = f"{tag_prefix}{version}"
      if not tag_exists(repo, tag_name):
        create_version_tag_with_github(repo, tag_name, github_token)
      else:
        if version not in get_semver_tags_on_commit(repo, tag_prefix):
          raise RuntimeError(f"Tag {tag_name} already exists on the repository but is not on the current commit")
        else:
          log_debug(f"Tag {tag_name} already exists on this tag")

    # Output the resolved version to stdout
    print(version)

if __name__ == "__main__":
    try:
      main()
    except Exception as e:
      print(f"An error occurred: {e}")
      sys.exit(1)
