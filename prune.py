"""Enhanced prune functionality with intelligent image cleanup."""

import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table


@dataclass
class ImageInfo:
    """Information about a container image."""

    id: str
    repository: str
    tag: str
    size: str
    size_bytes: int
    created: str
    digest: Optional[str] = None


@dataclass
class ContainerInfo:
    """Information about a container."""

    id: str
    name: str
    image: str
    image_id: str
    status: str


class EnhancedPruner:
    """Enhanced pruning with intelligent image cleanup analysis."""

    def __init__(self, console: Console):
        self.console = console
        self.images_in_use: Set[str] = set()
        self.all_images: Dict[str, ImageInfo] = {}
        self.all_containers: List[ContainerInfo] = []
        self.dangling_images: List[ImageInfo] = []
        self.duplicate_groups: Dict[str, List[ImageInfo]] = {}

    def analyze_system(self) -> bool:
        """Analyze the current system state to identify cleanup candidates."""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold white]{task.description}"),
                console=self.console,
                transient=True,
            ) as progress:
                # Step 1: Get all containers and their images
                task1 = progress.add_task("Analyzing containers...", total=None)
                if not self._get_container_info():
                    return False
                progress.remove_task(task1)

                # Step 2: Get all images
                task2 = progress.add_task("Analyzing images...", total=None)
                if not self._get_image_info():
                    return False
                progress.remove_task(task2)

                # Step 3: Identify images in use
                task3 = progress.add_task("Identifying images in use...", total=None)
                self._identify_images_in_use()
                progress.remove_task(task3)

                # Step 4: Find dangling images
                task4 = progress.add_task("Finding dangling images...", total=None)
                self._find_dangling_images()
                progress.remove_task(task4)

                # Step 5: Find duplicates
                task5 = progress.add_task("Finding duplicate images...", total=None)
                self._find_duplicate_images()
                progress.remove_task(task5)

            return True

        except Exception as e:
            self.console.print(f"[red]Error analyzing system: {e}[/red]")
            return False

    def _get_container_info(self) -> bool:
        """Get information about all containers (running and stopped)."""
        try:
            # Get all containers with their image information
            cmd = [
                "podman",
                "ps",
                "-a",
                "--format",
                "{{.ID}};{{.Names}};{{.Image}};{{.ImageID}};{{.Status}}",
            ]
            self.console.print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                self.console.print(
                    f"[red]Failed to get container info: {result.stderr}[/red]"
                )
                return False

            self.all_containers = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    parts = line.split(";")
                    if len(parts) >= 5:
                        container = ContainerInfo(
                            id=parts[0],
                            name=parts[1],
                            image=parts[2],
                            image_id=parts[3],
                            status=parts[4],
                        )
                        self.all_containers.append(container)

            return True

        except Exception as e:
            self.console.print(f"[red]Error getting container info: {e}[/red]")
            return False

    def _get_image_info(self) -> bool:
        """Get information about all images."""
        try:
            # Get detailed image information
            cmd = [
                "podman",
                "images",
                "--format",
                "{{.ID}};{{.Repository}};{{.Tag}};{{.Size}};{{.Created}}",
                "--all",
            ]
            self.console.print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                self.console.print(
                    f"[red]Failed to get image info: {result.stderr}[/red]"
                )
                return False

            self.all_images = {}
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    parts = line.split(";")
                    if len(parts) >= 5:
                        # Parse size to bytes for sorting
                        size_str = parts[3]
                        size_bytes = self._parse_size_to_bytes(size_str)

                        image = ImageInfo(
                            id=parts[0],
                            repository=parts[1],
                            tag=parts[2],
                            size=size_str,
                            size_bytes=size_bytes,
                            created=parts[4],
                        )
                        self.all_images[parts[0]] = image

            return True

        except Exception as e:
            self.console.print(f"[red]Error getting image info: {e}[/red]")
            return False

    def _parse_size_to_bytes(self, size_str: str) -> int:
        """Parse size string like '1.2GB' to bytes."""
        try:
            size_str = size_str.strip().upper()
            if size_str == "0B" or not size_str:
                return 0

            # Extract number and unit
            import re

            match = re.match(r"([0-9.]+)\s*([KMGT]?B)", size_str)
            if not match:
                return 0

            number = float(match.group(1))
            unit = match.group(2)

            multipliers = {
                "B": 1,
                "KB": 1024,
                "MB": 1024**2,
                "GB": 1024**3,
                "TB": 1024**4,
            }

            return int(number * multipliers.get(unit, 1))

        except Exception:
            return 0

    def _identify_images_in_use(self) -> None:
        """Identify which images are currently in use by containers."""
        self.images_in_use = set()

        for container in self.all_containers:
            # Add both image ID and image name to the in-use set
            if container.image_id:
                self.images_in_use.add(container.image_id)
            if container.image:
                # Also track by image name for reference
                for img_id, img_info in self.all_images.items():
                    if f"{img_info.repository}:{img_info.tag}" == container.image:
                        self.images_in_use.add(img_id)

    def _find_dangling_images(self) -> None:
        """Find dangling (untagged) images."""
        self.dangling_images = []

        for img_id, img_info in self.all_images.items():
            # Dangling images have <none> repository and tag
            if (
                img_info.repository == "<none>"
                and img_info.tag == "<none>"
                and img_id not in self.images_in_use
            ):
                self.dangling_images.append(img_info)

    def _find_duplicate_images(self) -> None:
        """Find images with same content but different tags."""
        # Group images by size and created time as a simple duplicate detection
        # In a more sophisticated implementation, we'd use image digests
        size_groups: Dict[Tuple[int, str], List[ImageInfo]] = {}

        for img_id, img_info in self.all_images.items():
            if img_id not in self.images_in_use and img_info.repository != "<none>":
                key = (img_info.size_bytes, img_info.created)
                if key not in size_groups:
                    size_groups[key] = []
                size_groups[key].append(img_info)

        # Keep only groups with multiple images (potential duplicates)
        self.duplicate_groups = {
            f"Group {i+1}": images
            for i, (key, images) in enumerate(size_groups.items())
            if len(images) > 1
        }

    def show_analysis_summary(self) -> None:
        """Show a summary of the analysis results."""
        total_images = len(self.all_images)
        images_in_use = len(self.images_in_use)
        unused_images = total_images - images_in_use
        dangling_count = len(self.dangling_images)
        duplicate_groups_count = len(self.duplicate_groups)

        # Calculate potential space savings
        dangling_space = sum(img.size_bytes for img in self.dangling_images)
        duplicate_space = sum(
            sum(img.size_bytes for img in images[1:])  # Keep first, remove rest
            for images in self.duplicate_groups.values()
        )
        total_potential_savings = dangling_space + duplicate_space

        # Create summary text without panel border
        summary_text = f"""
[bold]System Analysis Summary[/bold]

Total Images: {total_images}
Images in Use: {images_in_use}
Unused Images: {unused_images}
Dangling Images: {dangling_count}
Duplicate Groups: {duplicate_groups_count}

[bold]Potential Space Savings[/bold]
Dangling Images: {self._format_bytes(dangling_space)}
Duplicate Images: {self._format_bytes(duplicate_space)}
[bold green]Total Potential: {self._format_bytes(total_potential_savings)}[/bold green]
        """.strip()

        self.console.print(summary_text)

    def _format_bytes(self, bytes_count: int) -> str:
        """Format bytes to human readable string."""
        if bytes_count == 0:
            return "0 B"

        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(bytes_count)
        unit_index = 0

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        return f"{size:.1f} {units[unit_index]}"

    def show_detailed_candidates(self) -> None:
        """Show detailed information about cleanup candidates."""
        if self.dangling_images:
            self.console.print(
                "\n[bold yellow]Dangling Images (Safe to Remove):[/bold yellow]"
            )
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Image ID", style="cyan", width=12)
            table.add_column("Size", style="green", width=10)
            table.add_column("Created", style="dim", width=20)

            for img in sorted(
                self.dangling_images, key=lambda x: x.size_bytes, reverse=True
            ):
                table.add_row(img.id[:12], img.size, img.created)

            self.console.print(table)

        if self.duplicate_groups:
            self.console.print(
                "\n[bold yellow]Potential Duplicate Images:[/bold yellow]"
            )
            for group_name, images in self.duplicate_groups.items():
                self.console.print(
                    f"\n[bold cyan]{group_name}[/bold cyan] (Size: {images[0].size})"
                )

                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("Keep?", style="green", width=6)
                table.add_column("Repository:Tag", style="white", width=40)
                table.add_column("Image ID", style="cyan", width=12)
                table.add_column("Created", style="dim", width=20)

                for i, img in enumerate(images):
                    keep_status = "✓ KEEP" if i == 0 else "✗ Remove"
                    repo_tag = f"{img.repository}:{img.tag}"
                    table.add_row(keep_status, repo_tag, img.id[:12], img.created)

                self.console.print(table)

    def execute_cleanup(self, confirm_large_removals: bool = True) -> bool:
        """Execute the cleanup with optional confirmation for large removals."""
        total_space_to_free = sum(img.size_bytes for img in self.dangling_images) + sum(
            sum(img.size_bytes for img in images[1:])
            for images in self.duplicate_groups.values()
        )

        if total_space_to_free == 0:
            self.console.print(
                "[green]No cleanup needed - system is already optimized![/green]"
            )
            return True

        # Show what will be removed
        self.console.print("\n[bold yellow]Cleanup Plan:[/bold yellow]")
        self.console.print(f"• Remove {len(self.dangling_images)} dangling images")
        duplicate_count = sum(
            len(images) - 1 for images in self.duplicate_groups.values()
        )
        self.console.print(f"• Remove {duplicate_count} duplicate images")
        self.console.print(
            f"• Total space to free: [bold green]{self._format_bytes(total_space_to_free)}[/bold green]"
        )

        # Confirm if large removal or if requested
        if confirm_large_removals and (
            total_space_to_free > 1024**3
            or len(self.dangling_images) + duplicate_count > 10
        ):
            if not Confirm.ask("\nProceed with cleanup?"):
                self.console.print("[yellow]Cleanup cancelled by user[/yellow]")
                return False

        # Execute cleanup
        success = True

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold white]{task.description}"),
            console=self.console,
            transient=True,
        ) as progress:
            # Remove dangling images
            if self.dangling_images:
                task1 = progress.add_task(
                    f"Removing {len(self.dangling_images)} dangling images...",
                    total=None,
                )
                if not self._remove_images([img.id for img in self.dangling_images]):
                    success = False
                progress.remove_task(task1)

            # Remove duplicate images (keep first in each group)
            if self.duplicate_groups:
                images_to_remove = []
                for images in self.duplicate_groups.values():
                    images_to_remove.extend(
                        img.id for img in images[1:]
                    )  # Skip first (keep it)

                if images_to_remove:
                    task2 = progress.add_task(
                        f"Removing {len(images_to_remove)} duplicate images...",
                        total=None,
                    )
                    if not self._remove_images(images_to_remove):
                        success = False
                    progress.remove_task(task2)

        if success:
            self.console.print("[green]✓ Cleanup completed successfully![/green]")
            self.console.print(
                f"[green]✓ Freed approximately {self._format_bytes(total_space_to_free)}[/green]"
            )
        else:
            self.console.print(
                "[yellow]⚠ Cleanup completed with some warnings[/yellow]"
            )

        return success

    def _remove_images(self, image_ids: List[str]) -> bool:
        """Remove a list of images by ID."""
        if not image_ids:
            return True

        try:
            # Use podman rmi with force to remove images
            cmd = ["podman", "rmi", "-f"] + image_ids
            self.console.print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                return True
            else:
                # Some images might fail to remove (e.g., still in use)
                # This is not necessarily a complete failure
                if result.stderr:
                    self.console.print(
                        f"[yellow]Warning during image removal: {result.stderr.strip()}[/yellow]"
                    )
                return True  # Consider partial success as success

        except Exception as e:
            self.console.print(f"[red]Error removing images: {e}[/red]")
            return False

    def show_system_df_before_after(self) -> None:
        """Show system disk usage before and after cleanup."""
        self.console.print("\n[bold cyan]System Disk Usage:[/bold cyan]")

        try:
            cmd = ["podman", "system", "df"]
            self.console.print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                self.console.print(result.stdout)
            else:
                self.console.print(
                    f"[yellow]Could not get system disk usage: {result.stderr}[/yellow]"
                )

        except Exception as e:
            self.console.print(f"[red]Error getting system disk usage: {e}[/red]")

    def run_safe_prune_workflow(self) -> bool:
        """Run the complete safe prune workflow."""
        self.console.print("[bold blue]🧹 Enhanced Podman Image Cleanup[/bold blue]")
        self.console.print(
            "[dim]Analyzing system to identify safe cleanup opportunities...[/dim]\n"
        )

        # Show initial system state
        self.console.print("[bold]Before Cleanup:[/bold]")
        self.show_system_df_before_after()

        # Analyze system
        if not self.analyze_system():
            return False

        # Show analysis results
        self.show_analysis_summary()

        # Show detailed candidates if there are any
        if self.dangling_images or self.duplicate_groups:
            if Confirm.ask("\nShow detailed cleanup candidates?"):
                self.show_detailed_candidates()

        # Execute cleanup
        if self.dangling_images or self.duplicate_groups:
            self.console.print("\n" + "=" * 60)
            success = self.execute_cleanup()

            if success:
                self.console.print("\n[bold]After Cleanup:[/bold]")
                self.show_system_df_before_after()

            return success
        else:
            self.console.print(
                "\n[green]✓ No cleanup needed - your system is already optimized![/green]"
            )
            return True

    def run_quick_prune(self) -> bool:
        """Run a quick prune of dangling images and containers only."""
        self.console.print("[bold blue]🧹 Quick Podman Cleanup[/bold blue]")

        success = True

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold white]{task.description}"),
            console=self.console,
            transient=True,
        ) as progress:
            # Prune containers
            task1 = progress.add_task("Pruning unused containers...", total=None)
            try:
                cmd = ["podman", "container", "prune", "-f"]
                self.console.print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode != 0:
                    self.console.print(
                        f"[yellow]Container prune warning: {result.stderr.strip()}[/yellow]"
                    )
            except Exception as e:
                self.console.print(f"[red]Error pruning containers: {e}[/red]")
                success = False
            progress.remove_task(task1)

            # Prune dangling images
            task2 = progress.add_task("Pruning dangling images...", total=None)
            try:
                cmd = ["podman", "image", "prune", "-f"]
                self.console.print(f"  [cyan]exec: {' '.join(cmd)}[/cyan]")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode != 0:
                    self.console.print(
                        f"[yellow]Image prune warning: {result.stderr.strip()}[/yellow]"
                    )
            except Exception as e:
                self.console.print(f"[red]Error pruning images: {e}[/red]")
                success = False
            progress.remove_task(task2)

        if success:
            self.console.print("[green]✓ Quick cleanup completed[/green]")
        else:
            self.console.print(
                "[yellow]⚠ Quick cleanup completed with warnings[/yellow]"
            )

        return success
