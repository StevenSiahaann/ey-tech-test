"""
Input Guardrail for Conversational BI Agent.
Intercepts prompt injection, malicious instructions, and destructive intents before LLM processing.
"""

import re
from typing import Tuple, Optional

# Patterns indicating malicious or destructive intents
MALICIOUS_PATTERNS = [
    r"\b(drop|truncate|delete|alter|insert|update|create|grant|revoke)\s+(table|database|schema|user|role|column)\b",
    r"\b(hapus|tambahkan|rubah|ganti|edit|update|delete)\s+(tabel|database|data|pesanan|harga)\b",
    r"\b(ignore\s+(all\s+)?(previous|prior)\s+instructions?)\b",
    r"\b(abaikan\s+(semua\s+)?(instruksi|perintah)\s+sebelumnya)\b",
    r"\b(system\s+prompt|bypass\s+guardrails?|jailbreak|dan\s+mode)\b",
    r"\b(password|secret_key|api_key|credential)\b"
]


class GuardResult:
    def __init__(self, is_safe: bool, refusal_reason: Optional[str] = None, suggested_alternative: Optional[str] = None):
        self.is_safe = is_safe
        self.refusal_reason = refusal_reason
        self.suggested_alternative = suggested_alternative


def check_input_safety(user_text: str) -> GuardResult:
    """
    Checks if user text violates safety policies or attempts write operations.
    Returns GuardResult.
    """
    t = user_text.lower().strip()

    for pattern in MALICIOUS_PATTERNS:
        if re.search(pattern, t, re.IGNORECASE):
            return GuardResult(
                is_safe=False,
                refusal_reason=(
                    "Sistem Conversational BI ini beroperasi dalam mode Read-Only analitik. "
                    "Perintah modifikasi data (DML/DDL), penghapusan, atau instruksi sistem di luar domain analisis data tidak diizinkan."
                ),
                suggested_alternative=(
                    "Anda dapat menanyakan metrik analitik bisnis seperti: "
                    "'Berapa GMV MTD untuk region Jawa?', 'Top 5 produk berdasarkan revenue bulan lalu?', "
                    "atau 'Perbandingan revenue POS vs E-commerce'."
                )
            )

    return GuardResult(is_safe=True)
