"""
Adversarial Input Sanitization & Prompt-Injection Defense Shield
Protects the agentic investigation pipeline from prompt injections, jailbreaks,
instruction overriding, and toxic payload injection in customer replies and merchant strings.
"""

import re
from typing import Tuple, Dict, Any, List

# Compiled regex patterns for prompt injection signatures
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules|commands)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(in|a)\s+(maintenance|developer|jailbreak|unrestricted|god)\s+mode", re.IGNORECASE),
    re.compile(r"system\s+override\b", re.IGNORECASE),
    re.compile(r"(act|roleplay)\s+as\s+(an?\s+)?(unrestricted|dan|evil|admin)\b", re.IGNORECASE),
    re.compile(r"###\s*(System|Instruction|Assistant)", re.IGNORECASE),
    re.compile(r"<\s*\|?\s*(system|im_start|im_end|endoftext)\s*\|?\s*>", re.IGNORECASE),
    re.compile(r"\[/?INST\]", re.IGNORECASE),
    re.compile(r"verdict\s*[:=]\s*(legitimate|fraud|cleared)", re.IGNORECASE),
    re.compile(r"action\s*[:=]\s*(ALLOW_TRANSACTION|CLOSE_NO_FRAUD)", re.IGNORECASE),
]

# Control / zero-width character filter
CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F\u200B-\u200D\uFEFF]")


class InputSanitizer:
    @staticmethod
    def sanitize_untrusted_text(
        text: str,
        max_length: int = 500,
        source: str = "customer",
    ) -> Tuple[str, bool, List[str]]:
        """
        Sanitizes untrusted text from external sources.
        Returns:
            sanitized_text (str): Neutralized and normalized string.
            is_malicious (bool): True if prompt injection attempt was detected.
            threats_detected (List[str]): List of detected attack signatures.
        """
        if not text:
            return "", False, []

        # 1. Remove control and zero-width characters
        cleaned = CONTROL_CHARS_PATTERN.sub("", str(text))

        # 2. Length truncation
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length] + " [TRUNCATED]"

        # 3. Detect prompt injections
        threats_detected = []
        is_malicious = False

        for pattern in PROMPT_INJECTION_PATTERNS:
            matches = pattern.findall(cleaned)
            if matches:
                is_malicious = True
                threats_detected.append(pattern.pattern)
                # Defang the matched phrase by quoting and neutralizing
                cleaned = pattern.sub("[DEFANGED_INJECTION_ATTEMPT]", cleaned)

        # 4. Normalize whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned, is_malicious, threats_detected

    @staticmethod
    def inspect_and_defang_payload(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """
        Recursively scans and sanitizes string fields in dictionary payloads.
        """
        sanitized = {}
        any_threat = False

        for k, v in payload.items():
            if isinstance(v, str):
                s_text, has_threat, _ = InputSanitizer.sanitize_untrusted_text(v)
                sanitized[k] = s_text
                if has_threat:
                    any_threat = True
            elif isinstance(v, dict):
                s_sub, has_threat = InputSanitizer.inspect_and_defang_payload(v)
                sanitized[k] = s_sub
                if has_threat:
                    any_threat = True
            elif isinstance(v, list):
                s_list = []
                for item in v:
                    if isinstance(item, str):
                        s_text, has_threat, _ = InputSanitizer.sanitize_untrusted_text(item)
                        s_list.append(s_text)
                        if has_threat:
                            any_threat = True
                    else:
                        s_list.append(item)
                sanitized[k] = s_list
            else:
                sanitized[k] = v

        return sanitized, any_threat
