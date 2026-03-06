"""
Filename sanitization for AWS Bedrock requirements
"""
import re


class FileSanitizer:
    """Sanitizes filenames for AWS Bedrock compatibility"""

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename to meet AWS Bedrock requirements:
        - Only alphanumeric, whitespace, hyphens, parentheses, and square brackets
        - No consecutive whitespace

        Args:
            filename: Original filename

        Returns:
            str: Sanitized filename
        """
        # Replace special characters (except allowed ones) with underscore
        sanitized = re.sub(r'[^a-zA-Z0-9\s\-\(\)\[\]]', '_', filename)

        # Replace consecutive whitespace with single space
        sanitized = re.sub(r'\s+', ' ', sanitized)

        # Trim whitespace
        sanitized = sanitized.strip()

        return sanitized
