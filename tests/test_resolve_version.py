import os, sys
import tempfile
import unittest
from git import Repo
from unittest.mock import patch, MagicMock
import semver


from tachyon_dist_tools.resolve_version import (
    main,
    resolve_stable_version,
    resolve_release_version,
    resolve_prerelease_version,
    infer_github_repo,
    get_latest_version_tag,
    find_ancestral_release_version,
    create_version_tag_with_github,
    get_semver_tags_on_commit,
    get_stable_tags_on_commit,
    tag_exists,
    strip_tag_prefix,
)

class TestGitFunctions(unittest.TestCase):

    def setUp(self):
        """Set up a temporary Git repository for testing with logging."""
        self.temp_dir = tempfile.mkdtemp()
        print(f"Creating temporary directory for the Git repository: {self.temp_dir}")

        # Initialize the Git repository
        self.repo = Repo.init(self.temp_dir)
        print("Initialized a new Git repository.")

        # Configure git identity and disable GPG signing for tests
        self.repo.config_writer().set_value("user", "name", "Test User").release()
        self.repo.config_writer().set_value("user", "email", "test@example.local").release()
        self.repo.config_writer().set_value("commit", "gpgsign", "false").release()
        self.repo.config_writer().set_value("tag", "gpgsign", "false").release()

        # Create an initial commit
        file_path = os.path.join(self.temp_dir, "README.md")
        with open(file_path, "w") as f:
            f.write("# Test Repository\n")
        print("Created README.md file.")

        self.repo.index.add([file_path])
        self.repo.index.commit("Initial commit")
        print("Committed the initial README.md file.")

        # Rename the default branch to 'develop'
        self.repo.git.branch("-M", "develop")
        print("Renamed the default branch to 'develop'.")

    def tearDown(self):
        """Clean up the temporary directory."""
        print(f"Cleaning up temporary directory: {self.temp_dir}")
        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.temp_dir)
        print("Temporary directory cleaned up.")

    def test_get_latest_version(self):
        # Add and tag multiple commits
        file_path = os.path.join(self.temp_dir, "CHANGELOG.md")
        for version in ["1.0.0", "1.1.0", "2.0.0"]:
            with open(file_path, "a") as f:
                f.write(f"\nVersion {version}")
            self.repo.index.add([file_path])
            self.repo.index.commit(f"Release {version}")
            self.repo.create_tag(version, message=f"Release {version}")

        latest_version = get_latest_version_tag(self.repo)
        self.assertEqual(latest_version, "2.0.0")


    def test_get_semver_tags_on_commit(self):
        """Test filtering and sorting valid SemVer tags on the current commit."""
        print("Running test_get_semver_tags_on_commit.")

        # Add valid and invalid tags to the current commit
        valid_tags = ["1.0.0", "2.0.0", "1.5.1"]
        invalid_tags = ["invalid", "version-1", "2.0.0-beta"]

        for tag in valid_tags + invalid_tags:
            self.repo.create_tag(tag, message=f"Tag {tag}")
            print(f"Created tag '{tag}'.")

        # Run the function under test
        result = get_semver_tags_on_commit(self.repo)
        print(f"Function result: {result}")

        # Expected result: valid tags sorted in descending order
        expected_result = sorted(valid_tags, key=semver.VersionInfo.parse, reverse=True)

        # Assert the function output matches the expected result
        self.assertEqual(result, expected_result)

    def test_get_stable_tags_on_commit(self):
        """Test filtering and sorting valid stable tags on the current commit."""
        print("Running test_get_stable_tags_on_commit.")

        # Add valid and invalid tags to the current commit
        stable_tags = ["stable-1.0.0", "stable-2.0.0", "stable-1.5.1"]
        matching_semver_tags = ["1.0.0", "2.0.0", "1.5.1"]
        other_tags = ["invalid", "version-1", "2.0.0-beta", "1.0.1"]

        for tag in stable_tags + matching_semver_tags + other_tags:
            self.repo.create_tag(tag, message=f"Tag {tag}")
            print(f"Created tag '{tag}'.")

        # Run the function under test
        result = get_stable_tags_on_commit(self.repo)
        print(f"Function result: {result}")

        # Expected result: valid tags sorted in descending order
        expected_result = sorted(matching_semver_tags, key=semver.VersionInfo.parse, reverse=True)

        # Assert the function output matches the expected result
        self.assertEqual(result, expected_result)

    def test_get_stable_tags_on_commit_mismatch(self):
        """Test finding stable tags on the current commit when there is a mismatch."""
        print("Running test_get_semver_tags_on_commit.")

        # Add valid and invalid tags to the current commit
        stable_tags = ["stable-1.0.0", "stable-2.0.0", "stable-1.5.1"]
        matching_semver_tags = ["1.0.0", "2.0.0"]
        other_tags = ["invalid", "version-1", "2.0.0-beta", "1.0.1"]

        for tag in stable_tags + matching_semver_tags + other_tags:
            self.repo.create_tag(tag, message=f"Tag {tag}")
            print(f"Created tag '{tag}'.")

        # Run the function under test
        # This should raise an error because the stable tag does not match the semver tag
        with self.assertRaises(ValueError) as context:
            get_stable_tags_on_commit(self.repo)

    def test_get_stable_tags_on_commit_build(self):
        """Test finding stable tags on the current commit when there is a stable tag incorrectly referencing a build tag."""
        print("Running test_get_semver_tags_on_commit.")

        # Add valid and invalid tags to the current commit
        stable_tags = ["stable-1.5.1-dev+build.1234"]

        for tag in stable_tags :
            self.repo.create_tag(tag, message=f"Tag {tag}")
            print(f"Created tag '{tag}'.")

        # Run the function under test
        # This should raise an error because the stable tag is invalid
        with self.assertRaises(ValueError) as context:
            get_stable_tags_on_commit(self.repo)

    def test_get_stable_tags_on_commit_pre(self):
        """Test finding stable tags on the current commit when there is a stable tag incorrectly referencing a pre-release tag."""
        print("Running test_get_semver_tags_on_commit.")

        # Add valid and invalid tags to the current commit
        stable_tags = ["stable-2.0.0-beta",]


        for tag in stable_tags:
            self.repo.create_tag(tag, message=f"Tag {tag}")
            print(f"Created tag '{tag}'.")

        # Run the function under test
        # This should raise an error because the stable tag is invalid
        with self.assertRaises(ValueError) as context:
            get_stable_tags_on_commit(self.repo)

    def test_tag_exists(self):
        """Tests the tag_exists function."""

        # Add valid and invalid tags to the current commit
        valid_tags = ["1.0.0", "2.0.0", "1.5.1"]
        invalid_tags = ["invalid", "version-1", "2.0.0-beta"]

        for tag in valid_tags + invalid_tags:
            self.repo.create_tag(tag, message=f"Tag {tag}")
            print(f"Created tag '{tag}'.")

        # Create a new commit without a tag
        file_path = os.path.join(self.temp_dir, "CHANGELOG.md")
        with open(file_path, "a") as f:
            f.write("\nNew version")
        self.repo.index.add([file_path])
        self.repo.index.commit("New commit")

        # Run the function under test
        for tag in valid_tags + invalid_tags:
            result = tag_exists(self.repo, tag)
            self.assertTrue(result)

        # Test a tag that doesn't exist
        result = tag_exists(self.repo, "99.99.9999")
        self.assertFalse(result)

    def test_find_ancestral_release_version_with_multiple_tags(self):
        """
        Tests finding the most recent semver tag in the current branch's history
        when two tagged releases exist on the develop branch,
        and a new branch is created from the earlier tagged version.
        """
        # Create and switch to the develop branch
        print("Creating and switching to the 'develop' branch.")
        develop_branch = self.repo.create_head("develop")
        develop_branch.checkout()

        # Add and tag multiple commits
        print("Adding and tagging multiple commits.")
        file_path = os.path.join(self.temp_dir, "CHANGELOG.md")
        for version in ["1.0.0", "2.0.0"]:
            print(f"Adding version {version} to the CHANGELOG.")
            with open(file_path, "a") as f:
                f.write(f"\nVersion {version}")
            print("Committing the CHANGELOG.")
            self.repo.index.add([file_path])
            self.repo.index.commit(f"Release {version}")
            print(f"Creating tag {version}.")
            self.repo.create_tag(version, message=f"Release {version}")

        # Create a new branch based on the earlier tag (1.0.0)
        earlier_tag_commit = self.repo.tags["1.0.0"].commit
        new_branch = self.repo.create_head("feature/new-branch", earlier_tag_commit)
        new_branch.checkout()

        # Test ancestral version detection on the new branch
        ancestral_version = find_ancestral_release_version(self.repo)
        self.assertEqual(ancestral_version, "1.0.0")

    def test_find_ancestral_prerelease_version_with_stable_tags(self):
        """
        Tests computation of the correct pre-release version when the most recent tag also
        includes stable tags.
        """
        # Create and switch to the develop branch
        print("Creating and switching to the 'develop' branch.")
        develop_branch = self.repo.create_head("develop")
        develop_branch.checkout()

        # Add and tag multiple commits
        print("Adding and tagging multiple commits.")
        file_path = os.path.join(self.temp_dir, "CHANGELOG.md")
        for versions in [["stable-1.0.0", "1.0.0"], ["1.0.1"], ["stable-2.0.0", "2.0.0"]]:
            version = versions[0]
            print(f"Adding version {version} to the CHANGELOG.")
            with open(file_path, "a") as f:
                f.write(f"\nVersion {version}")
            print("Committing the CHANGELOG.")
            self.repo.index.add([file_path])
            self.repo.index.commit(f"Release {version}")
            for v in versions:
                print(f"Creating tag {v}.")
                self.repo.create_tag(v, message=f"Release {v}")

        # Test ancestral version detection on the new branch
        ancestral_version = find_ancestral_release_version(self.repo)
        self.assertEqual(ancestral_version, "2.0.0")

    def test_find_ancestral_stable_release_version_with_multiple_tags(self):
        """
        Tests finding the most recent stable tag in the current branch's history
        when two tagged releases exist on the develop branch,
        and a new branch is created from the earlier tagged version.
        """
        # Create and switch to the develop branch
        print("Creating and switching to the 'develop' branch.")
        develop_branch = self.repo.create_head("develop")
        develop_branch.checkout()

        # Add and tag multiple commits
        print("Adding and tagging multiple commits.")
        file_path = os.path.join(self.temp_dir, "CHANGELOG.md")
        for version in ["stable-1.0.0", "1.0.1", "stable-2.0.0"]:
            print(f"Adding version {version} to the CHANGELOG.")
            with open(file_path, "a") as f:
                f.write(f"\nVersion {version}")
            print("Committing the CHANGELOG.")
            self.repo.index.add([file_path])
            self.repo.index.commit(f"Release {version}")
            print(f"Creating tag {version}.")
            self.repo.create_tag(version, message=f"Release {version}")

        # Test ancestral version detection on the new branch
        ancestral_version = find_ancestral_release_version(self.repo, "stable-", "HEAD~")
        self.assertEqual(ancestral_version, "stable-1.0.0")

    # ---- series-namespaced tag streams (--tag-prefix) --------------------

    def _commit_and_tag(self, marker, tags):
        """Add a commit and place `tags` (a list) on it."""
        file_path = os.path.join(self.temp_dir, "CHANGELOG.md")
        with open(file_path, "a") as f:
            f.write(f"\n{marker}")
        self.repo.index.add([file_path])
        self.repo.index.commit(f"commit {marker}")
        for t in tags:
            self.repo.create_tag(t, message=f"Tag {t}")

    def test_strip_tag_prefix(self):
        # Empty prefix is a passthrough (historical single-stream behaviour).
        self.assertEqual(strip_tag_prefix("1.2.3", ""), "1.2.3")
        self.assertEqual(strip_tag_prefix("26.04/1.3.0", ""), "26.04/1.3.0")
        # Non-empty prefix strips only matching tags; others are dropped.
        self.assertEqual(strip_tag_prefix("26.04/1.3.0", "26.04/"), "1.3.0")
        self.assertIsNone(strip_tag_prefix("1.2.3", "26.04/"))
        self.assertIsNone(strip_tag_prefix("24.04/1.2.3", "26.04/"))

    def test_get_latest_version_tag_streams_are_independent(self):
        # Bare (24.04) stream and a 26.04/ stream coexist on the same repo.
        self._commit_and_tag("a", ["1.2.19"])
        self._commit_and_tag("b", ["26.04/1.3.0"])
        self._commit_and_tag("c", ["26.04/1.3.1"])
        self._commit_and_tag("d", ["1.2.20"])
        # Bare stream ignores the namespaced tags entirely...
        self.assertEqual(get_latest_version_tag(self.repo), "1.2.20")
        self.assertEqual(get_latest_version_tag(self.repo, ""), "1.2.20")
        # ...and the 26.04 stream ignores the bare tags, returning clean semver.
        self.assertEqual(get_latest_version_tag(self.repo, "26.04/"), "1.3.1")
        # An empty stream falls back to the historical default.
        self.assertEqual(get_latest_version_tag(self.repo, "99.99/"), "1.0.0")

    def test_get_semver_tags_on_commit_with_prefix(self):
        self._commit_and_tag("x", ["1.2.19", "26.04/1.3.0"])
        self.assertEqual(get_semver_tags_on_commit(self.repo), ["1.2.19"])
        self.assertEqual(get_semver_tags_on_commit(self.repo, "26.04/"), ["1.3.0"])

    def test_resolve_release_version_prefixed_tag_on_commit(self):
        # A pushed 26.04/1.3.0 tag on HEAD resolves to exactly 1.3.0 (clean semver).
        self._commit_and_tag("seed", ["26.04/1.3.0"])
        self.assertEqual(resolve_release_version(self.repo, "26.04/"), "1.3.0")

    def test_resolve_release_version_prefixed_bumps_from_stream_max(self):
        # An untagged HEAD after 26.04/1.3.0 bumps the 26.04 stream, not the bare one.
        self._commit_and_tag("seed", ["1.2.50", "26.04/1.3.0"])
        self._commit_and_tag("next", [])
        self.assertEqual(resolve_release_version(self.repo, "26.04/"), "1.3.1")
        self.assertEqual(resolve_release_version(self.repo, ""), "1.2.51")

    def test_resolve_prerelease_version_prefixed_seed_before_first_tag(self):
        # No 26.04 tag yet: the seed carries the intended first number (1.3.0).
        self._commit_and_tag("only-bare", ["1.2.19"])
        self.assertEqual(
            resolve_prerelease_version(self.repo, "build.abc", "26.04/", "1.3.0"),
            "1.3.0-dev+build.abc",
        )
        # Bare stream still anchors on the bare ancestral tag, unaffected by the seed.
        self.assertEqual(
            resolve_prerelease_version(self.repo, "build.abc"),
            "1.2.19-dev+build.abc",
        )

    def test_resolve_prerelease_version_prefixed_uses_ancestral(self):
        # Once a 26.04 release tag exists in history, prereleases anchor on it (prefix stripped).
        self._commit_and_tag("rel", ["26.04/1.3.0"])
        self._commit_and_tag("work", [])
        self.assertEqual(
            resolve_prerelease_version(self.repo, "build.def", "26.04/", "9.9.9"),
            "1.3.0-dev+build.def",
        )

    @patch("tachyon_dist_tools.resolve_version.Repo")
    def test_infer_github_repo(self, mock_repo):
        """
        Test that infer_github_repo correctly parses repository names from remote URLs.
        """
        # Mock repository with different remote URLs
        mock_origin_remote = MagicMock()
        mock_repo.return_value.remotes.origin.url = "git@github.com:owner/repo.git"
        repo_name = infer_github_repo(mock_repo.return_value)
        self.assertEqual(repo_name, "owner/repo")

        mock_repo.return_value.remotes.origin.url = "https://github.com/owner/repo.git"
        repo_name = infer_github_repo(mock_repo.return_value)
        self.assertEqual(repo_name, "owner/repo")

        # Test invalid remote URL
        mock_repo.return_value.remotes.origin.url = "ftp://example.com/invalid/repo.git"
        with self.assertRaises(ValueError) as context:
            infer_github_repo(mock_repo.return_value)
        self.assertIn("Unsupported remote URL format", str(context.exception))

        # Test no remotes configured
        mock_repo.return_value.remotes = []
        with self.assertRaises(ValueError) as context:
            infer_github_repo(mock_repo.return_value)
        self.assertIn("No remotes found for the repository", str(context.exception))



class TestVersionResolution(unittest.TestCase):

    @patch("tachyon_dist_tools.resolve_version.get_stable_tags_on_commit", return_value=["1.0.1", "1.0.0", "0.9.9"])
    def test_resolve_stable_version(self, mock_get_stable_tags_on_commit):
        """
        Tests that resolve_stable_version correctly determines the latest stable version
        based on the tags in the commit history.
        """
        repo = unittest.mock.Mock()

        # Call the function under test
        resolved_version = resolve_stable_version(repo)
        print(f"Resolved stable version: {resolved_version}")

        mock_get_stable_tags_on_commit.assert_called_once_with(repo)

        # Assert the resolved version is the latest stable tag
        self.assertEqual(resolved_version, "1.0.1")
        print("Finished test: test_resolve_stable_version")

    @patch("tachyon_dist_tools.resolve_version.get_latest_version_tag", return_value="2.0.0")
    @patch("tachyon_dist_tools.resolve_version.get_semver_tags_on_commit", return_value=[])
    def test_resolve_release_version(self, mock_get_latest_version_tag, mock_get_semver_tags_on_commit):
        """
        Tests that resolve_release_version correctly determines the next patch version
        based on the latest version tag in the repository.
        """
        repo = unittest.mock.Mock()

        # Call the function under test
        resolved_version = resolve_release_version(repo)
        print(f"Resolved release version: {resolved_version}")

        mock_get_latest_version_tag.assert_called_once_with(repo, "")
        mock_get_semver_tags_on_commit.assert_called_once_with(repo, "")

        # Assert the resolved version is the next patch of the latest tag
        self.assertEqual(resolved_version, "2.0.1")
        print("Finished test: test_resolve_release_version")

    @patch("tachyon_dist_tools.resolve_version.get_latest_version_tag", return_value="2.0.0")
    @patch("tachyon_dist_tools.resolve_version.get_semver_tags_on_commit", return_value=["1.0.0"])
    def test_resolve_release_version_with_tag_on_commit(self, mock_get_latest_version_tag, mock_get_semver_tags_on_commit):
        """
        Tests that resolve_release_version correctly determines the next patch version
        based on the latest version tag in the repository.
        """
        repo = unittest.mock.Mock()

        # Call the function under test
        resolved_version = resolve_release_version(repo)
        print(f"Resolved release version: {resolved_version}")

        mock_get_latest_version_tag.assert_called_once_with(repo, "")
        mock_get_semver_tags_on_commit.assert_called_once_with(repo, "")

        # Assert the resolved version is the next patch of the latest tag
        self.assertEqual(resolved_version, "1.0.0")

    @patch("tachyon_dist_tools.resolve_version.find_ancestral_release_version", return_value="1.0.0")
    def test_resolve_prerelease_version(self, mock_find_ancestral_release_version):
        """
        Tests that resolve_prerelease_version correctly determines the next prerelease version
        based on the most recent semver tag in the commit history.
        """
        repo = unittest.mock.Mock()
        build_id = "build.12345"

        # Call the function under test
        resolved_version = resolve_prerelease_version(repo, build_id)
        print(f"Resolved prerelease version: {resolved_version}")

        mock_find_ancestral_release_version.assert_called_once_with(repo, None)

        # Assert the resolved version is the next prerelease version
        self.assertEqual(resolved_version, "1.0.0-dev+build.12345")
        print("Finished test: test_resolve_prerelease_version")

    @patch("tachyon_dist_tools.resolve_version.find_ancestral_release_version", return_value=None)
    def test_resolve_prerelease_version_no_ancestral_version(self, mock_find_ancestral_release_version):
        """
        Tests that resolve_prerelease_version correctly determines the next prerelease version
        based on the most recent semver tag in the commit history.
        """
        repo = unittest.mock.Mock()
        build_id = "build.12345"

        # Call the function under test
        resolved_version = resolve_prerelease_version(repo, build_id)
        print(f"Resolved prerelease version: {resolved_version}")

        mock_find_ancestral_release_version.assert_called_once_with(repo, None)

        # Assert the resolved version is the next prerelease version
        self.assertEqual(resolved_version, "99.99.9999-dev+build.12345")
        print("Finished test: test_resolve_prerelease_version")

class TestCreateVersionTagWithGithub(unittest.TestCase):

    @patch("tachyon_dist_tools.resolve_version.Github")
    @patch("tachyon_dist_tools.resolve_version.infer_github_repo")
    def test_create_tag_success(self, mock_infer_repo, mock_github):
        """Test that a tag is successfully created."""
        # Mock repository and commit
        mock_repo = MagicMock()
        mock_repo.head.commit.hexsha = "abc123"
        mock_infer_repo.return_value = "owner/repo"

        # Mock GitHub API behavior
        mock_gh_repo = MagicMock()
        mock_github.return_value.get_repo.return_value = mock_gh_repo

        # Call the function
        version = "1.0.0"
        github_token = "fake_token"
        result = create_version_tag_with_github(mock_repo, version, github_token)

        # Assertions
        mock_infer_repo.assert_called_once_with(mock_repo)
        mock_github.assert_called_once_with(github_token)
        mock_github.return_value.get_repo.assert_called_once_with("owner/repo")
        mock_gh_repo.create_git_ref.assert_called_once_with(ref=f"refs/tags/{version}", sha="abc123")
        self.assertEqual(result, version)

    @patch("tachyon_dist_tools.resolve_version.Github")
    @patch("tachyon_dist_tools.resolve_version.infer_github_repo")
    def test_create_tag_invalid_repo(self, mock_infer_repo, mock_github):
        """Test that an error is raised when the repository is invalid."""
        # Mock repository and commit
        mock_repo = MagicMock()
        mock_repo.head.commit.hexsha = "abc123"
        mock_infer_repo.return_value = "invalid/repo"

        # Mock GitHub API behavior
        mock_github.return_value.get_repo.side_effect = Exception("Repository not found")

        # Call the function and check for exception
        version = "1.0.0"
        github_token = "fake_token"
        with self.assertRaises(Exception) as context:
            create_version_tag_with_github(mock_repo, version, github_token)

        self.assertIn("Repository not found", str(context.exception))
        mock_infer_repo.assert_called_once_with(mock_repo)
        mock_github.assert_called_once_with(github_token)


    @patch("tachyon_dist_tools.resolve_version.Github")
    @patch("tachyon_dist_tools.resolve_version.infer_github_repo")
    def test_create_tag_duplicate_tag(self, mock_infer_repo, mock_github):
        """Test that an error is raised when the tag already exists."""
        # Mock repository and commit
        mock_repo = MagicMock()
        mock_repo.head.commit.hexsha = "abc123"
        mock_infer_repo.return_value = "owner/repo"

        # Mock GitHub API behavior
        mock_gh_repo = MagicMock()
        mock_gh_repo.create_git_ref.side_effect = Exception("Reference already exists")
        mock_github.return_value.get_repo.return_value = mock_gh_repo

        # Call the function and check for exception
        version = "1.0.0"
        github_token = "fake_token"
        with self.assertRaises(Exception) as context:
            create_version_tag_with_github(mock_repo, version, github_token)

        self.assertIn("Reference already exists", str(context.exception))
        mock_infer_repo.assert_called_once_with(mock_repo)
        mock_github.assert_called_once_with(github_token)
        mock_github.return_value.get_repo.assert_called_once_with("owner/repo")
        mock_gh_repo.create_git_ref.assert_called_once_with(ref=f"refs/tags/{version}", sha="abc123")


class TestMainFunction(unittest.TestCase):

    @patch("tachyon_dist_tools.resolve_version.Repo")
    @patch("tachyon_dist_tools.resolve_version.resolve_stable_version")
    @patch("tachyon_dist_tools.resolve_version.resolve_release_version")
    @patch("tachyon_dist_tools.resolve_version.resolve_prerelease_version")
    @patch("tachyon_dist_tools.resolve_version.create_version_tag_with_github")
    @patch("sys.stdout", new_callable=MagicMock)
    def test_stable_release_build(self, mock_stdout, mock_create_tag, mock_resolve_prerelease, mock_resolve_release, mock_resolve_stable, mock_repo):
        """Test main for a stable release build."""
        mock_repo.return_value.bare = False
        mock_resolve_stable.return_value = "1.0.1"

        with patch("sys.argv", ["resolve_version.py", "--build-type", "release", "--release-channel", "stable"]):
            main()

        mock_resolve_stable.assert_called_once()
        mock_resolve_release.assert_not_called()
        mock_resolve_prerelease.assert_not_called()
        mock_create_tag.assert_not_called()

        # Capture the output and verify
        output = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
        self.assertEqual(output.strip(), "1.0.1")

    @patch("tachyon_dist_tools.resolve_version.Repo")
    @patch("tachyon_dist_tools.resolve_version.resolve_stable_version")
    @patch("tachyon_dist_tools.resolve_version.resolve_release_version")
    @patch("tachyon_dist_tools.resolve_version.resolve_prerelease_version")
    @patch("tachyon_dist_tools.resolve_version.create_version_tag_with_github")
    @patch("sys.stdout", new_callable=MagicMock)
    def test_release_build(self, mock_stdout, mock_create_tag, mock_resolve_prerelease, mock_resolve_release, mock_resolve_stable, mock_repo):
        """Test main for a release build."""
        mock_repo.return_value.bare = False
        mock_resolve_release.return_value = "1.0.1"

        with patch("sys.argv", ["resolve_version.py", "--build-type", "release"]):
            main()

        mock_resolve_stable.assert_not_called()
        mock_resolve_release.assert_called_once()
        mock_resolve_prerelease.assert_not_called()
        mock_create_tag.assert_not_called()

        # Capture the output and verify
        output = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
        self.assertEqual(output.strip(), "1.0.1")

    @patch("tachyon_dist_tools.resolve_version.Repo")
    @patch("tachyon_dist_tools.resolve_version.resolve_release_version")
    @patch("tachyon_dist_tools.resolve_version.resolve_prerelease_version")
    @patch("tachyon_dist_tools.resolve_version.create_version_tag_with_github")
    @patch("sys.stdout", new_callable=MagicMock)
    def test_prerelease_build(self, mock_stdout, mock_create_tag, mock_resolve_prerelease, mock_resolve_release, mock_repo):
        """Test main for a prerelease build."""
        mock_repo.return_value.bare = False
        mock_resolve_prerelease.return_value = "1.0.0+build.1234"

        with patch("sys.argv", ["resolve_version.py", "--build-type", "prerelease", "--build-id", "1234"]):
            main()

        mock_resolve_release.assert_not_called()
        mock_resolve_prerelease.assert_called_once_with(mock_repo.return_value, "1234", "", "99.99.9999")
        mock_create_tag.assert_not_called()

        # Capture the output and verify
        output = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
        self.assertEqual(output.strip(), "1.0.0+build.1234")

    @patch("tachyon_dist_tools.resolve_version.Repo")
    @patch("tachyon_dist_tools.resolve_version.resolve_release_version")
    @patch("tachyon_dist_tools.resolve_version.resolve_prerelease_version")
    @patch("tachyon_dist_tools.resolve_version.create_version_tag_with_github")
    @patch("sys.stdout", new_callable=MagicMock)
    def test_create_tag_without_github_token(self, mock_stdout, mock_create_tag, mock_resolve_prerelease, mock_resolve_release, mock_repo):
        """Test main with --create-tag and no GITHUB_TOKEN."""
        mock_repo.return_value.bare = False

        with patch("sys.argv", ["resolve_version.py", "--build-type", "release", "--create-tag"]), patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError) as context:
                main()
            self.assertIn("Environment variable GITHUB_TOKEN must be set to create a tag", str(context.exception))

        mock_resolve_release.assert_not_called()
        mock_resolve_prerelease.assert_not_called()
        mock_create_tag.assert_not_called()
        mock_stdout.write.assert_not_called()

    @patch("tachyon_dist_tools.resolve_version.Repo")
    @patch("tachyon_dist_tools.resolve_version.resolve_release_version")
    @patch("tachyon_dist_tools.resolve_version.resolve_prerelease_version")
    @patch("tachyon_dist_tools.resolve_version.create_version_tag_with_github")
    @patch("sys.stdout", new_callable=MagicMock)
    def test_create_tag_with_github_token(self, mock_stdout, mock_create_tag, mock_resolve_prerelease, mock_resolve_release, mock_repo):
        """Test main with --create-tag and GITHUB_TOKEN set."""
        mock_repo.return_value.bare = False
        mock_resolve_release.return_value = "1.0.1"

        with patch("sys.argv", ["resolve_version.py", "--build-type", "release", "--create-tag"]), patch.dict(os.environ, {"GITHUB_TOKEN": "fake_token"}):
            main()

        mock_resolve_release.assert_called_once()
        mock_resolve_prerelease.assert_not_called()
        mock_create_tag.assert_called_once_with(mock_repo.return_value, "1.0.1", "fake_token")

        # Capture the output and verify
        output = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
        self.assertEqual(output.strip(), "1.0.1")

    @patch("tachyon_dist_tools.resolve_version.Repo")
    @patch("tachyon_dist_tools.resolve_version.resolve_release_version")
    @patch("tachyon_dist_tools.resolve_version.resolve_prerelease_version")
    @patch("tachyon_dist_tools.resolve_version.create_version_tag_with_github")
    @patch("tachyon_dist_tools.resolve_version.tag_exists", return_value=True)
    @patch("tachyon_dist_tools.resolve_version.get_semver_tags_on_commit", return_value=["2.0.0"])
    @patch("sys.stdout", new_callable=MagicMock)
    def test_create_tag_with_existing_tag_github_token(self, mock_stdout, mock_get_semver_tags_on_commit, mock_tag_exists, mock_create_tag, mock_resolve_prerelease, mock_resolve_release, mock_repo):
        """Test main with --create-tag and GITHUB_TOKEN set. Existing tag on commit."""
        mock_repo.return_value.bare = False
        mock_resolve_release.return_value = "2.0.0"

        with patch("sys.argv", ["resolve_version.py", "--build-type", "release", "--create-tag"]), patch.dict(os.environ, {"GITHUB_TOKEN": "fake_token"}):
            main()

        mock_resolve_release.assert_called_once()
        mock_resolve_prerelease.assert_not_called()

        # Should be skipped because this test simulates a release build of an existing tag
        mock_create_tag.assert_not_called()

        # Capture the output and verify
        output = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
        self.assertEqual(output.strip(), "2.0.0")

    @patch("tachyon_dist_tools.resolve_version.Repo")
    @patch("tachyon_dist_tools.resolve_version.resolve_release_version")
    @patch("tachyon_dist_tools.resolve_version.resolve_prerelease_version")
    @patch("tachyon_dist_tools.resolve_version.create_version_tag_with_github")
    @patch("tachyon_dist_tools.resolve_version.tag_exists", return_value=True)
    @patch("tachyon_dist_tools.resolve_version.get_semver_tags_on_commit", return_value=[])
    @patch("sys.stdout", new_callable=MagicMock)
    def test_create_tag_with_bad_existing_tag_github_token(self, mock_stdout, mock_get_semver_tags_on_commit, mock_tag_exists, mock_create_tag, mock_resolve_prerelease, mock_resolve_release, mock_repo):
        """Test main with --create-tag and GITHUB_TOKEN set. Existing tag on a different commit."""
        mock_repo.return_value.bare = False
        mock_resolve_release.return_value = "2.0.0"

        with patch("sys.argv", ["resolve_version.py", "--build-type", "release", "--create-tag"]), patch.dict(os.environ, {"GITHUB_TOKEN": "fake_token"}):
            with self.assertRaises(RuntimeError) as context:
                main()

        mock_resolve_release.assert_called_once()
        mock_resolve_prerelease.assert_not_called()

        # Should be skipped because this test simulates a release build of an existing tag
        mock_create_tag.assert_not_called()

        # Capture the output and verify
        output = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
        self.assertEqual(output.strip(), "")

    @patch("tachyon_dist_tools.resolve_version.Repo")
    @patch("tachyon_dist_tools.resolve_version.resolve_release_version")
    @patch("tachyon_dist_tools.resolve_version.resolve_prerelease_version")
    @patch("tachyon_dist_tools.resolve_version.create_version_tag_with_github")
    @patch("sys.stdout", new_callable=MagicMock)
    def test_prerelease_build_with_tag_prefix_and_seed(self, mock_stdout, mock_create_tag, mock_resolve_prerelease, mock_resolve_release, mock_repo):
        """main threads --tag-prefix and --seed-version into prerelease resolution."""
        mock_repo.return_value.bare = False
        mock_resolve_prerelease.return_value = "1.3.0-dev+build.1234"

        with patch("sys.argv", ["resolve_version.py", "--build-type", "prerelease",
                                 "--build-id", "build.1234", "--tag-prefix", "26.04/",
                                 "--seed-version", "1.3.0"]):
            main()

        mock_resolve_release.assert_not_called()
        mock_resolve_prerelease.assert_called_once_with(mock_repo.return_value, "build.1234", "26.04/", "1.3.0")
        output = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
        self.assertEqual(output.strip(), "1.3.0-dev+build.1234")

    @patch("tachyon_dist_tools.resolve_version.Repo")
    @patch("tachyon_dist_tools.resolve_version.resolve_release_version")
    @patch("tachyon_dist_tools.resolve_version.resolve_prerelease_version")
    @patch("sys.stdout", new_callable=MagicMock)
    def test_release_build_with_tag_prefix(self, mock_stdout, mock_resolve_prerelease, mock_resolve_release, mock_repo):
        """main threads --tag-prefix into release resolution and prints clean semver."""
        mock_repo.return_value.bare = False
        mock_resolve_release.return_value = "1.3.0"

        with patch("sys.argv", ["resolve_version.py", "--build-type", "release", "--tag-prefix", "26.04/"]):
            main()

        mock_resolve_prerelease.assert_not_called()
        mock_resolve_release.assert_called_once_with(mock_repo.return_value, "26.04/")
        output = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
        self.assertEqual(output.strip(), "1.3.0")

    @patch("tachyon_dist_tools.resolve_version.Repo")
    @patch("tachyon_dist_tools.resolve_version.resolve_release_version", return_value="1.3.0")
    @patch("tachyon_dist_tools.resolve_version.create_version_tag_with_github")
    @patch("tachyon_dist_tools.resolve_version.tag_exists", return_value=False)
    @patch("sys.stdout", new_callable=MagicMock)
    def test_create_tag_with_tag_prefix(self, mock_stdout, mock_tag_exists, mock_create_tag, mock_resolve_release, mock_repo):
        """--create-tag with --tag-prefix creates a namespaced tag but prints clean semver."""
        mock_repo.return_value.bare = False

        with patch("sys.argv", ["resolve_version.py", "--build-type", "release",
                                 "--tag-prefix", "26.04/", "--create-tag"]), \
             patch.dict(os.environ, {"GITHUB_TOKEN": "fake_token"}):
            main()

        # The git tag carries the prefix; stdout stays clean semver.
        mock_tag_exists.assert_called_once_with(mock_repo.return_value, "26.04/1.3.0")
        mock_create_tag.assert_called_once_with(mock_repo.return_value, "26.04/1.3.0", "fake_token")
        output = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
        self.assertEqual(output.strip(), "1.3.0")

    @patch("tachyon_dist_tools.resolve_version.Repo")
    def test_stable_with_tag_prefix_rejected(self, mock_repo):
        """--tag-prefix is not supported with the stable channel."""
        mock_repo.return_value.bare = False
        with patch("sys.argv", ["resolve_version.py", "--build-type", "release",
                                 "--release-channel", "stable", "--tag-prefix", "26.04/"]):
            with self.assertRaises(ValueError) as context:
                main()
            self.assertIn("--tag-prefix is not supported with release channel 'stable'", str(context.exception))

    @patch("tachyon_dist_tools.resolve_version.Repo")
    def test_invalid_git_repository(self, mock_repo):
        """Test main with an invalid Git repository."""
        mock_repo.return_value.bare = True

        with patch("sys.argv", ["resolve_version.py", "--build-type", "release"]):
            with self.assertRaises(Exception) as context:
                main()
            self.assertIn("Not a valid git repository", str(context.exception))


if __name__ == "__main__":
    unittest.main()
