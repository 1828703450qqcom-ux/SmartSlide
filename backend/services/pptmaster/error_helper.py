#!/usr/bin/env python3
"""
PPT Master - Error Message Helper

Provides user-friendly error messages and specific fix suggestions.
"""

from typing import Dict, List, Optional


class ErrorHelper:
    """Error message helper."""

    # Error types and their corresponding fix suggestions
    ERROR_SOLUTIONS = {
        'missing_readme': {
            'message': 'Missing README.md file',
            'solutions': [
                'Create a README.md file with project description, usage instructions, etc.',
            ],
            'severity': 'error'
        },
        'missing_spec': {
            'message': 'Missing design specification file',
            'solutions': [
                'Create a design_spec.md file',
                'Include: canvas specs, color scheme, font specs, layout specs, content outline',
            ],
            'severity': 'warning'
        },
        'missing_svg_output': {
            'message': 'Missing svg_output directory',
            'solutions': [
                'Create the svg_output directory: mkdir svg_output',
                'Place generated SVG files in this directory',
            ],
            'severity': 'error'
        },
        'empty_svg_output': {
            'message': 'svg_output directory is empty',
            'solutions': [
                'Generate SVG files',
                'Save SVG files to the svg_output directory',
            ],
            'severity': 'warning'
        },
    }

    @classmethod
    def get_solution(cls, error_type: str, context: Optional[Dict] = None) -> Dict:
        """
        Get the solution for an error.

        Args:
            error_type: Error type
            context: Context information (optional)

        Returns:
            Dictionary containing message, solutions, severity
        """
        if error_type in cls.ERROR_SOLUTIONS:
            solution = cls.ERROR_SOLUTIONS[error_type].copy()

            # Customize message based on context
            if context:
                solution = cls._customize_solution(solution, context)

            return solution

        # Unknown error type
        return {
            'message': 'Unknown error',
            'solutions': ['Please check the documentation'],
            'severity': 'error'
        }

    @classmethod
    def _customize_solution(cls, solution: Dict, context: Dict) -> Dict:
        """
        Customize solution based on context.

        Args:
            solution: Original solution
            context: Context information

        Returns:
            Customized solution
        """
        customized = solution.copy()

        # Customize based on project path
        if 'project_path' in context:
            project_path = context['project_path']
            customized['solutions'] = [
                s.replace('<project_path>', project_path).replace(
                    '<your_project>', project_path)
                for s in customized['solutions']
            ]

        # Customize based on filename
        if 'file_name' in context:
            file_name = context['file_name']
            customized['message'] = f"{customized['message']}: {file_name}"

        return customized

    @classmethod
    def format_error_message(cls, error_type: str, context: Optional[Dict] = None) -> str:
        """
        Format error message (for terminal output).

        Args:
            error_type: Error type
            context: Context information

        Returns:
            Formatted error message string
        """
        solution = cls.get_solution(error_type, context)

        lines = []

        # Error message
        severity_icon = "[ERROR]" if solution['severity'] == 'error' else "[WARN]"
        lines.append(f"{severity_icon} {solution['message']}")

        # Solutions
        if solution['solutions']:
            lines.append("\nSuggested fixes:")
            for i, sol in enumerate(solution['solutions'], 1):
                lines.append(f"   {i}. {sol}")

        return "\n".join(lines)

    @classmethod
    def print_error(cls, error_type: str, context: Optional[Dict] = None):
        """
        Print formatted error message.

        Args:
            error_type: Error type
            context: Context information
        """
        print(cls.format_error_message(error_type, context))

    @classmethod
    def get_all_error_types(cls) -> List[str]:
        """Get all supported error types."""
        return list(cls.ERROR_SOLUTIONS.keys())


def main() -> None:
    """Run the CLI entry point for error lookup."""
    import sys

    if len(sys.argv) > 1:
        error_type = sys.argv[1]
        context = {}

        # Parse context parameters
        for arg in sys.argv[2:]:
            if '=' in arg:
                key, value = arg.split('=', 1)
                context[key] = value

        print(ErrorHelper.format_error_message(error_type, context))


if __name__ == '__main__':
    main()
