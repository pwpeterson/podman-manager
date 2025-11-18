"""Specialized troubleshooter for llama.cpp service issues.

This module provides automatic detection and fixing of common llama.cpp
container configuration issues, particularly the 'invalid argument: llama-server' error.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.config import console, verbose_print


class LlamaCppTroubleshooter:
    """Troubleshooter for llama.cpp service configuration issues."""

    def __init__(self):
        self.common_issues = {
            "invalid_argument_llama_server": {
                "pattern": r"error: invalid argument: llama-server",
                "description": "Container receiving 'llama-server' as invalid argument",
                "fix_method": "fix_llama_server_argument"
            },
            "missing_model_file": {
                "pattern": r"error: failed to load model",
                "description": "Model file not found or inaccessible",
                "fix_method": "suggest_model_path_fix"
            },
            "port_binding_error": {
                "pattern": r"bind: address already in use",
                "description": "Port 8005 already in use by another service",
                "fix_method": "suggest_port_conflict_resolution"
            }
        }

    def diagnose_service_failure(self, service_name: str, error_logs: str) -> Dict[str, any]:
        """Diagnose llama.cpp service failure from error logs.
        
        Args:
            service_name: Name of the failing service
            error_logs: Recent error logs from the service
            
        Returns:
            Dictionary containing diagnosis results and suggested fixes
        """
        verbose_print(f"[cyan]Diagnosing llama.cpp service failure for {service_name}[/cyan]")
        
        diagnosis = {
            "service_name": service_name,
            "issues_found": [],
            "suggested_fixes": [],
            "auto_fixable": False
        }
        
        # Check for known issues
        for issue_key, issue_info in self.common_issues.items():
            if re.search(issue_info["pattern"], error_logs, re.IGNORECASE):
                diagnosis["issues_found"].append({
                    "type": issue_key,
                    "description": issue_info["description"],
                    "fix_method": issue_info["fix_method"]
                })
                
                # Generate fix suggestion
                fix_method = getattr(self, issue_info["fix_method"], None)
                if fix_method:
                    fix_suggestion = fix_method(service_name, error_logs)
                    if fix_suggestion:
                        diagnosis["suggested_fixes"].append(fix_suggestion)
                        if fix_suggestion.get("auto_fixable", False):
                            diagnosis["auto_fixable"] = True
        
        return diagnosis

    def fix_llama_server_argument(self, service_name: str, error_logs: str) -> Dict[str, any]:
        """Fix the 'invalid argument: llama-server' issue.
        
        Args:
            service_name: Name of the service
            error_logs: Error logs (for context)
            
        Returns:
            Fix suggestion dictionary
        """
        container_file = self._find_container_file(service_name)
        if not container_file:
            return {
                "type": "manual_fix",
                "description": "Container file not found - manual intervention required",
                "auto_fixable": False
            }
        
        try:
            content = container_file.read_text()
            
            # Check if the issue exists in the container file
            if "llama-server" not in content:
                return {
                    "type": "no_fix_needed",
                    "description": "Container file doesn't contain 'llama-server' argument",
                    "auto_fixable": False
                }
            
            # Prepare fixes
            fix_option_1 = content.replace("llama-server", "--server")
            
            # Option 2: Remove the argument entirely
            fix_option_2 = content
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if "llama-server" in line and line.strip().startswith('Exec='):
                    new_line = line.replace(" llama-server", "").replace("llama-server ", "")
                    lines[i] = new_line
            fix_option_2 = '\n'.join(lines)
            
            return {
                "type": "container_file_fix",
                "description": "Fix 'llama-server' argument in container file",
                "auto_fixable": True,
                "container_file": str(container_file),
                "original_content": content,
                "fix_options": [
                    {
                        "name": "Replace with --server",
                        "content": fix_option_1,
                        "recommended": True
                    },
                    {
                        "name": "Remove argument entirely",
                        "content": fix_option_2,
                        "recommended": False
                    }
                ]
            }
            
        except Exception as e:
            verbose_print(f"[cyan]Error analyzing container file: {e}[/cyan]")
            return {
                "type": "analysis_error",
                "description": f"Error analyzing container file: {e}",
                "auto_fixable": False
            }

    def suggest_model_path_fix(self, service_name: str, error_logs: str) -> Dict[str, any]:
        """Suggest fixes for model file loading issues."""
        return {
            "type": "model_path_fix",
            "description": "Check model file path and permissions",
            "auto_fixable": False,
            "suggestions": [
                "Verify model file exists in the specified path",
                "Check file permissions (should be readable by container user)",
                "Ensure volume mount is correctly configured",
                "Verify model file format is compatible with llama.cpp"
            ]
        }

    def suggest_port_conflict_resolution(self, service_name: str, error_logs: str) -> Dict[str, any]:
        """Suggest fixes for port binding conflicts."""
        return {
            "type": "port_conflict_fix",
            "description": "Resolve port 8005 conflict",
            "auto_fixable": False,
            "suggestions": [
                "Check if another model service is running on port 8005",
                "Use 'pm list' to see active services",
                "Stop conflicting service or change port configuration",
                "Consider using the models-stack architecture for proper model switching"
            ]
        }

    def apply_automatic_fix(self, fix_suggestion: Dict[str, any]) -> bool:
        """Apply an automatic fix if possible.
        
        Args:
            fix_suggestion: Fix suggestion from diagnose_service_failure
            
        Returns:
            True if fix was applied successfully, False otherwise
        """
        if not fix_suggestion.get("auto_fixable", False):
            return False
        
        if fix_suggestion["type"] == "container_file_fix":
            return self._apply_container_file_fix(fix_suggestion)
        
        return False

    def _apply_container_file_fix(self, fix_suggestion: Dict[str, any]) -> bool:
        """Apply container file fix.
        
        Args:
            fix_suggestion: Container file fix suggestion
            
        Returns:
            True if fix was applied successfully
        """
        try:
            container_file = Path(fix_suggestion["container_file"])
            
            # Create backup
            backup_file = container_file.with_suffix(".container.backup")
            container_file.rename(backup_file)
            console.print(f"[green]Created backup: {backup_file}[/green]")
            
            # Apply the recommended fix (first option)
            recommended_fix = None
            for option in fix_suggestion["fix_options"]:
                if option.get("recommended", False):
                    recommended_fix = option
                    break
            
            if not recommended_fix:
                recommended_fix = fix_suggestion["fix_options"][0]
            
            # Write the fixed content
            container_file.write_text(recommended_fix["content"])
            console.print(f"[green]Applied fix: {recommended_fix['name']}[/green]")
            console.print(f"[green]Updated container file: {container_file}[/green]")
            
            return True
            
        except Exception as e:
            console.print(f"[red]Error applying container file fix: {e}[/red]")
            return False

    def _find_container_file(self, service_name: str) -> Optional[Path]:
        """Find the container file for a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Path to container file or None if not found
        """
        # Clean service name (remove .service suffix)
        clean_name = service_name.replace(".service", "")
        
        # Common locations
        possible_paths = [
            Path.home() / f".config/containers/systemd/{clean_name}.container",
            Path.home() / f".config/containers/systemd/{clean_name.replace('-', '_')}.container",
            Path.home() / f".config/containers/systemd/{clean_name.replace('_', '-')}.container",
        ]
        
        for path in possible_paths:
            if path.exists():
                verbose_print(f"[cyan]Found container file: {path}[/cyan]")
                return path
        
        verbose_print(f"[cyan]Container file not found for {service_name}[/cyan]")
        return None

    def generate_troubleshooting_report(self, diagnosis: Dict[str, any]) -> str:
        """Generate a human-readable troubleshooting report.
        
        Args:
            diagnosis: Diagnosis results from diagnose_service_failure
            
        Returns:
            Formatted troubleshooting report
        """
        report_lines = [
            f"🔍 llama.cpp Service Diagnosis: {diagnosis['service_name']}",
            "=" * 60,
            ""
        ]
        
        if not diagnosis["issues_found"]:
            report_lines.extend([
                "✅ No known issues detected in error logs.",
                "   This might be a new issue or require manual investigation.",
                ""
            ])
        else:
            report_lines.append("🚨 Issues Found:")
            for i, issue in enumerate(diagnosis["issues_found"], 1):
                report_lines.extend([
                    f"   {i}. {issue['description']}",
                    f"      Type: {issue['type']}",
                    ""
                ])
        
        if diagnosis["suggested_fixes"]:
            report_lines.append("🔧 Suggested Fixes:")
            for i, fix in enumerate(diagnosis["suggested_fixes"], 1):
                report_lines.extend([
                    f"   {i}. {fix['description']}",
                    f"      Auto-fixable: {'Yes' if fix.get('auto_fixable', False) else 'No'}",
                ])
                
                if fix["type"] == "container_file_fix":
                    report_lines.extend([
                        f"      Container file: {fix['container_file']}",
                        "      Fix options:"
                    ])
                    for option in fix["fix_options"]:
                        marker = "(Recommended)" if option.get("recommended") else ""
                        report_lines.append(f"        - {option['name']} {marker}")
                
                elif "suggestions" in fix:
                    report_lines.append("      Suggestions:")
                    for suggestion in fix["suggestions"]:
                        report_lines.append(f"        - {suggestion}")
                
                report_lines.append("")
        
        if diagnosis["auto_fixable"]:
            report_lines.extend([
                "⚡ Automatic Fix Available!",
                "   Run the troubleshooter with --apply-fix to automatically fix the issue.",
                ""
            ])
        
        return "\n".join(report_lines)
