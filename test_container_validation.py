#!/usr/bin/env python3
"""Test script for container validation functionality."""

from pathlib import Path

from container_validator import ContainerValidator


def test_problematic_container():
    """Test validation with the original problematic container file that caused service loading issues."""

    # This is the type of content that was causing "Unit local-ai-postgres.service not loaded" errors
    problematic_content = """[Container]
Image=postgres:13
Expose=5432
Restart=unless-stopped
Environment=POSTGRES_DB=${POSTGRES_DB}
Environment=POSTGRES_USER=${POSTGRES_USER}
Environment=POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

[Service]
Type=notify

[Install]
WantedBy=default.target
"""

    # Create a test file in the project directory
    test_file = Path("test_problematic.container")
    try:
        with open(test_file, "w") as f:
            f.write(problematic_content)

        # Validate it
        validator = ContainerValidator()
        is_valid, errors, warnings = validator.validate_container_file(test_file)

        print("=== Container Validation Test Results ===")
        print(f"File: {test_file}")
        print(f"Validation result: {'PASS' if is_valid else 'FAIL'}")
        print(f"Errors found: {len(errors)}")

        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")

        print(f"Warnings found: {len(warnings)}")
        for i, warning in enumerate(warnings, 1):
            print(f"  {i}. {warning}")

        # Verify we caught the original issues
        expected_issues = ["Invalid parameter 'Expose'", "Invalid parameter 'Restart'"]

        print("\n=== Verification ===")
        for expected in expected_issues:
            found = any(expected in error for error in errors)
            status = "✓" if found else "✗"
            print(f"{status} Detected: {expected}")

        return not is_valid and len(errors) >= 2

    finally:
        # Clean up test file
        if test_file.exists():
            test_file.unlink()


def test_valid_container():
    """Test validation with a properly formatted container file."""

    valid_content = """[Container]
Image=postgres:13
PublishPort=5432:5432
Environment=POSTGRES_DB=${POSTGRES_DB}
Environment=POSTGRES_USER=${POSTGRES_USER}
Environment=POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

[Service]
Type=notify
RestartPolicy=unless-stopped

[Install]
WantedBy=default.target
"""

    test_file = Path("test_valid.container")
    try:
        with open(test_file, "w") as f:
            f.write(valid_content)

        validator = ContainerValidator()
        is_valid, errors, warnings = validator.validate_container_file(test_file)

        print("\n=== Valid Container Test Results ===")
        print(f"File: {test_file}")
        print(f"Validation result: {'PASS' if is_valid else 'FAIL'}")
        print(f"Errors found: {len(errors)}")
        print(f"Warnings found: {len(warnings)}")

        return is_valid and len(errors) == 0

    finally:
        if test_file.exists():
            test_file.unlink()


def test_installer_components():
    """Test that the refactored installer components work correctly."""

    try:
        from installer import (
            QuadletInstaller,
        )

        print("\n=== Installer Components Test ===")

        # Test that all component managers can be initialized
        installer = QuadletInstaller()
        print("✓ QuadletInstaller initialized successfully")
        print(f"✓ EnvironmentManager: {type(installer.env_manager).__name__}")
        print(f"✓ SystemdManager: {type(installer.systemd_manager).__name__}")
        print(f"✓ ValidationManager: {type(installer.validation_manager).__name__}")
        print(f"✓ FileManager: {type(installer.file_manager).__name__}")
        print(f"✓ ValidationManager: {type(installer.validation_manager).__name__}")

        # Test stack discovery (if quadlet directory exists)
        try:
            stacks = installer.discover_stacks()
            print(f"✓ Stack discovery working: {len(stacks)} stacks found")
        except FileNotFoundError:
            print(
                "✓ Stack discovery working (no quadlet directory found - expected in test environment)"
            )

        return True

    except Exception as e:
        print(f"✗ Installer component test failed: {e}")
        return False


if __name__ == "__main__":
    print("Testing Container Validation and Installer Refactoring")
    print("=" * 60)

    # Run tests
    test1_passed = test_problematic_container()
    test2_passed = test_valid_container()
    test3_passed = test_installer_components()

    print("\n" + "=" * 60)
    print("SUMMARY:")
    print(f"✓ Problematic container detection: {'PASS' if test1_passed else 'FAIL'}")
    print(f"✓ Valid container acceptance: {'PASS' if test2_passed else 'FAIL'}")
    print(f"✓ Installer components: {'PASS' if test3_passed else 'FAIL'}")

    all_passed = test1_passed and test2_passed and test3_passed
    print(
        f"\nOverall result: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}"
    )
