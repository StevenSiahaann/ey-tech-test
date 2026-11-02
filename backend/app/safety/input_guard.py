"""
Input Guardrail for Conversational BI Agent.
Intercepts credential exfiltration, prompt injection, malicious instructions,
and destructive DML/DDL intents before LLM processing.
"""

import re
from typing import Optional
from backend.app.core.logger import log_security_event, get_logger

logger = get_logger("safety.input_guard")

CREDENTIAL_PATTERNS = [
    r"\b(password|passwd|secret_key|api_key|credential|credentials|connection\s+string|database_url|db_url|env\s+var|pg_shadow|pg_authid|pg_user)\b",
    r"\b(user\s+dan\s+password|username\s+dan\s+password|kredensial|kata\s+sandi|token\s+rahasia)\b",
]

DESTRUCTIVE_PATTERNS = [
    r"\b(drop|truncate|delete|alter|insert|update|create|grant|revoke)\s+(table|database|schema|user|role|column|from|into)\b",
    r"\b(hapus|tambahkan|rubah|ubah|ganti|edit|update|delete|kosongkan)\s+(tabel|database|data|pesanan|harga|produk|toko|transaksi)\b",
]

INJECTION_PATTERNS = [
    r"\b(ignore\s+(all\s+)?(previous|prior)\s+instructions?)\b",
    r"\b(abaikan\s+(semua\s+)?(instruksi|perintah|aturan)\s+sebelumnya)\b",
    r"\b(system\s+prompt|bypass\s+guardrails?|jailbreak|dan\s+mode)\b",
]


class GuardResult:
    def __init__(
        self,
        is_safe: bool,
        violation_type: Optional[str] = None,
        refusal_reason: Optional[str] = None,
        suggested_alternative: Optional[str] = None,
    ):
        self.is_safe = is_safe
        self.violation_type = violation_type
        self.refusal_reason = refusal_reason
        self.suggested_alternative = suggested_alternative


def check_input_safety(user_text: str, language: Optional[str] = "id") -> GuardResult:
    """
    Checks if user text violates security policies, attempts credential exfiltration,
    prompt injection, or write operations.
    Returns GuardResult with `violation_type`, `refusal_reason`, and `suggested_alternative`.
    """
    t = user_text.lower().strip()
    is_en = (language or "").lower() == "en"

    # 1. Credential & Secret Exfiltration Guardrail
    for pattern in CREDENTIAL_PATTERNS:
        if re.search(pattern, t, re.IGNORECASE):
            log_security_event(
                event_type="INPUT_CREDENTIAL_EXFILTRATION",
                status="BLOCKED",
                detail=f"Matched pattern='{pattern}' on input='{user_text[:100]}'",
            )
            return GuardResult(
                is_safe=False,
                violation_type="credential_exfiltration",
                refusal_reason=(
                    "Sorry, for enterprise security and data governance reasons, I cannot disclose database credentials, usernames, passwords, API keys, or internal connection strings."
                    if is_en else
                    "Maaf, demi keamanan sistem dan tata kelola data perusahaan, saya tidak diizinkan menampilkan informasi kredensial, username, password, API key, maupun konfigurasi internal database."
                ),
                suggested_alternative=(
                    "You can safely explore public analytical schema metadata or run business metrics such as GMV, Net Revenue, Gross Margin, or Top Products."
                    if is_en else
                    "Anda dapat menanyakan metrik analitik bisnis yang sah seperti GMV, Net Revenue, Gross Margin, Cancel Rate, atau daftar kategori produk."
                ),
            )

    # 2. Destructive DML / DDL Guardrail
    for pattern in DESTRUCTIVE_PATTERNS:
        if re.search(pattern, t, re.IGNORECASE):
            log_security_event(
                event_type="INPUT_DESTRUCTIVE_DML_DDL",
                status="BLOCKED",
                detail=f"Matched pattern='{pattern}' on input='{user_text[:100]}'",
            )
            return GuardResult(
                is_safe=False,
                violation_type="destructive_dml_ddl",
                refusal_reason=(
                    "Sorry, this Conversational BI system operates strictly in Read-Only mode. Data modification, insertion, or deletion commands (DDL/DML) are not permitted."
                    if is_en else
                    "Maaf, sistem Conversational BI ini beroperasi secara ketat dalam mode Read-Only analitik. Perintah modifikasi, penambahan, atau penghapusan data (DML/DDL) tidak diizinkan."
                ),
                suggested_alternative=(
                    "You can query read-only business analytics such as 'MTD GMV for Java region?' or 'Top 5 products by revenue last month?'."
                    if is_en else
                    "Silakan ajukan pertanyaan analisis data (read-only) seperti 'GMV MTD untuk region Jawa?' atau 'Top 5 produk berdasarkan revenue bulan lalu?'."
                ),
            )

    # 3. Prompt Injection & Guardrail Bypass
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, t, re.IGNORECASE):
            log_security_event(
                event_type="INPUT_PROMPT_INJECTION",
                status="BLOCKED",
                detail=f"Matched pattern='{pattern}' on input='{user_text[:100]}'",
            )
            return GuardResult(
                is_safe=False,
                violation_type="prompt_injection",
                refusal_reason=(
                    "Sorry, instructions attempting to override security guardrails or extract internal system prompts cannot be processed."
                    if is_en else
                    "Maaf, instruksi untuk mengabaikan batasan keamanan atau mengekstrak prompt internal sistem tidak dapat diproses."
                ),
                suggested_alternative=(
                    "Please ask a standard retail business analytics question regarding revenue, margin, products, or stores."
                    if is_en else
                    "Silakan ajukan pertanyaan analitik bisnis ritel terkait penjualan, revenue, margin, produk, atau cabang toko."
                ),
            )

    logger.debug(f"Input passed L1 guardrail check: '{user_text[:80]}'")
    return GuardResult(is_safe=True, violation_type=None)
