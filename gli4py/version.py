"""Version utility class for handling semantic versioning."""

import re


class Version:
    """A class to represent and parse semantic version numbers.

    Attributes:
        major (int): The major version number
        minor (int): The minor version number  
        patch (int): The patch version number
        build (int): The build version number
    """

    def __init__(self, major: int = 0, minor: int = 0, patch: int = 0, build: int = 0):
        """Initialize a Version instance.

        Args:
            major (int): The major version number (default: 0)
            minor (int): The minor version number (default: 0)
            patch (int): The patch version number (default: 0)
            build (int): The build version number (default: 0)
        """
        self.major = int(major)
        self.minor = int(minor)
        self.patch = int(patch)
        self.build = int(build)

    @classmethod
    def parse(cls, version_string: str) -> 'Version':
        """Parse a version string into a Version object.

        Args:
            version_string (str): A version string in the format "major.minor.patch" or "major.minor.patch.build"
                                 (e.g., "1.2.3", "12.34.56.78")

        Returns:
            Version: A Version instance with the parsed values

        Raises:
            ValueError: If the version string format is invalid
        """
        if not isinstance(version_string, str):
            raise ValueError("Version string must be a string")

        # Remove any leading 'v' if present (e.g., "v1.2.3" -> "1.2.3")
        version_string = version_string.lstrip('v')

        # Regular expression to match 3-part or 4-part version pattern
        pattern_3_part = r'^(\d+)\.(\d+)\.(\d+)$'
        pattern_4_part = r'^(\d+)\.(\d+)\.(\d+)\.(\d+)$'

        match_3 = re.match(pattern_3_part, version_string)
        match_4 = re.match(pattern_4_part, version_string)

        if match_4:
            # 4-part version: major.minor.patch.build
            major, minor, patch, build = match_4.groups()
            return cls(int(major), int(minor), int(patch), int(build))
        elif match_3:
            # 3-part version: major.minor.patch (build defaults to 0)
            major, minor, patch = match_3.groups()
            return cls(int(major), int(minor), int(patch), 0)
        else:
            raise ValueError(
                f"Invalid version string format: '{version_string}'. Expected format: 'major.minor.patch' or 'major.minor.patch.build'")

    def __str__(self) -> str:
        """Return the string representation of the version."""
        if self.build == 0:
            return f"{self.major}.{self.minor}.{self.patch}"
        else:
            return f"{self.major}.{self.minor}.{self.patch}.{self.build}"

    def __repr__(self) -> str:
        """Return the detailed string representation of the version."""
        return f"Version(major={self.major}, minor={self.minor}, patch={self.patch}, build={self.build})"

    def __eq__(self, other) -> bool:
        """Check if two versions are equal."""
        if not isinstance(other, Version):
            return False
        return (self.major, self.minor, self.patch, self.build) == (other.major, other.minor, other.patch, other.build)

    def __lt__(self, other) -> bool:
        """Check if this version is less than another version."""
        if not isinstance(other, Version):
            return NotImplemented
        return (self.major, self.minor, self.patch, self.build) < (other.major, other.minor, other.patch, other.build)

    def __le__(self, other) -> bool:
        """Check if this version is less than or equal to another version."""
        return self == other or self < other

    def __gt__(self, other) -> bool:
        """Check if this version is greater than another version."""
        if not isinstance(other, Version):
            return NotImplemented
        return (self.major, self.minor, self.patch, self.build) > (other.major, other.minor, other.patch, other.build)

    def __ge__(self, other) -> bool:
        """Check if this version is greater than or equal to another version."""
        return self == other or self > other

    def to_tuple(self) -> tuple[int, int, int, int]:
        """Return the version as a tuple (major, minor, patch, build)."""
        return (self.major, self.minor, self.patch, self.build)
