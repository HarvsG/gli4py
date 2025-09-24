"""Tests for the Version class."""

import pytest
from gli4py.version import Version


class TestVersion:
    """Test cases for the Version class."""

    def test_init_default(self):
        """Test Version initialization with default values."""
        version = Version()
        assert version.major == 0
        assert version.minor == 0
        assert version.patch == 0
        assert version.build == 0

    def test_init_with_values(self):
        """Test Version initialization with specific values."""
        version = Version(1, 2, 3, 4)
        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3
        assert version.build == 4

    def test_init_with_three_values(self):
        """Test Version initialization with three values (build defaults to 0)."""
        version = Version(1, 2, 3)
        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3
        assert version.build == 0

    def test_parse_valid_version_3_part(self):
        """Test parsing valid 3-part version strings."""
        version = Version.parse("1.2.3")
        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3
        assert version.build == 0

    def test_parse_valid_version_4_part(self):
        """Test parsing valid 4-part version strings."""
        version = Version.parse("12.34.56.78")
        assert version.major == 12
        assert version.minor == 34
        assert version.patch == 56
        assert version.build == 78

    def test_parse_with_v_prefix_3_part(self):
        """Test parsing 3-part version strings with 'v' prefix."""
        version = Version.parse("v2.5.1")
        assert version.major == 2
        assert version.minor == 5
        assert version.patch == 1
        assert version.build == 0

    def test_parse_with_v_prefix_4_part(self):
        """Test parsing 4-part version strings with 'v' prefix."""
        version = Version.parse("v2.5.1.9")
        assert version.major == 2
        assert version.minor == 5
        assert version.patch == 1
        assert version.build == 9

    def test_parse_zero_values_3_part(self):
        """Test parsing 3-part version strings with zero values."""
        version = Version.parse("0.0.0")
        assert version.major == 0
        assert version.minor == 0
        assert version.patch == 0
        assert version.build == 0

    def test_parse_zero_values_4_part(self):
        """Test parsing 4-part version strings with zero values."""
        version = Version.parse("0.0.0.0")
        assert version.major == 0
        assert version.minor == 0
        assert version.patch == 0
        assert version.build == 0

    def test_parse_large_numbers_3_part(self):
        """Test parsing 3-part version strings with large numbers."""
        version = Version.parse("123.456.789")
        assert version.major == 123
        assert version.minor == 456
        assert version.patch == 789
        assert version.build == 0

    def test_parse_large_numbers_4_part(self):
        """Test parsing 4-part version strings with large numbers."""
        version = Version.parse("123.456.789.101112")
        assert version.major == 123
        assert version.minor == 456
        assert version.patch == 789
        assert version.build == 101112

    def test_parse_invalid_format(self):
        """Test parsing invalid version string formats."""
        with pytest.raises(ValueError, match="Invalid version string format"):
            Version.parse("1.2")

        with pytest.raises(ValueError, match="Invalid version string format"):
            Version.parse("1.2.3.4.5")

        with pytest.raises(ValueError, match="Invalid version string format"):
            Version.parse("1.2.a")

        with pytest.raises(ValueError, match="Invalid version string format"):
            Version.parse("a.b.c")

        with pytest.raises(ValueError, match="Invalid version string format"):
            Version.parse("1-2-3")

        with pytest.raises(ValueError, match="Invalid version string format"):
            Version.parse("")

    def test_parse_non_string(self):
        """Test parsing non-string inputs."""
        with pytest.raises(ValueError, match="Version string must be a string"):
            Version.parse(123)

        with pytest.raises(ValueError, match="Version string must be a string"):
            Version.parse(None)

    def test_str_representation_3_part(self):
        """Test string representation of Version with build=0."""
        version = Version(1, 2, 3, 0)
        assert str(version) == "1.2.3"

    def test_str_representation_4_part(self):
        """Test string representation of Version with build>0."""
        version = Version(1, 2, 3, 4)
        assert str(version) == "1.2.3.4"

    def test_repr_representation(self):
        """Test repr representation of Version."""
        version = Version(1, 2, 3, 4)
        assert repr(version) == "Version(major=1, minor=2, patch=3, build=4)"

    def test_equality(self):
        """Test version equality comparison."""
        version1 = Version(1, 2, 3, 0)
        version2 = Version(1, 2, 3, 0)
        version3 = Version(1, 2, 4, 0)
        version4 = Version(1, 2, 3, 1)

        assert version1 == version2
        assert version1 != version3
        assert version1 != version4
        assert version1 != "1.2.3"  # Different type

    def test_comparison_operators(self):
        """Test version comparison operators."""
        v1_0_0_0 = Version(1, 0, 0, 0)
        v1_2_3_0 = Version(1, 2, 3, 0)
        v1_2_3_1 = Version(1, 2, 3, 1)
        v1_2_4_0 = Version(1, 2, 4, 0)
        v2_0_0_0 = Version(2, 0, 0, 0)

        # Less than
        assert v1_0_0_0 < v1_2_3_0
        assert v1_2_3_0 < v1_2_3_1
        assert v1_2_3_1 < v1_2_4_0
        assert v1_2_4_0 < v2_0_0_0

        # Less than or equal
        assert v1_0_0_0 <= v1_2_3_0
        assert v1_2_3_0 <= Version(1, 2, 3, 0)  # Equal case

        # Greater than
        assert v2_0_0_0 > v1_2_4_0
        assert v1_2_4_0 > v1_2_3_1
        assert v1_2_3_1 > v1_2_3_0
        assert v1_2_3_0 > v1_0_0_0

        # Greater than or equal
        assert v2_0_0_0 >= v1_2_4_0
        assert v1_2_3_0 >= Version(1, 2, 3, 0)  # Equal case

    def test_to_tuple(self):
        """Test conversion to tuple."""
        version = Version(1, 2, 3, 4)
        assert version.to_tuple() == (1, 2, 3, 4)

    def test_parse_and_str_roundtrip_3_part(self):
        """Test that parsing a 3-part version and converting back to string works."""
        original = "1.2.3"
        version = Version.parse(original)
        result = str(version)
        assert result == original

    def test_parse_and_str_roundtrip_4_part(self):
        """Test that parsing a 4-part version and converting back to string works."""
        original = "1.2.3.4"
        version = Version.parse(original)
        result = str(version)
        assert result == original
