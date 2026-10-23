"""
models/flan_t5.py  —  QueryMind FLAN-T5 Hybrid SQL Generator  v10
=================================================================

WHAT'S NEW IN v10
-----------------
  - Fine-tuned model auto-downloaded from Google Drive (trained with Colab notebook)
  - DRIVE_FILE_ID  →  paste the shared file/folder ID from your Drive link
  - Falls back to HuggingFace Hub models if Drive is unavailable
  - All v9 multi-stage pipeline, validation, and fallback logic preserved

SETUP (one-time after Colab training)
--------------------------------------
  1. Open Google Drive → navigate to  QueryMind/flan-t5-sql-finetuned/
  2. Right-click the FOLDER → Share → "Anyone with the link" → Copy link
  3. Paste the link below — the ID is the part after /folders/
     e.g.  https://drive.google.com/drive/folders/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs
                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
     → DRIVE_FOLDER_ID = ""

MODEL SELECTION (priority order)
----------------------------------
  1. Fine-tuned model from Google Drive  ← best, your custom model
  2. Local checkpoint  (CHECKPOINT_DIR on disk)
  3. GPU → DuckDB-NSQL-7B  (HuggingFace Hub)
  4. CPU → gaussalgo T5    (HuggingFace Hub)
  Multi-table mode is MODEL-FIRST hybrid: primary/fine-tuned model -> juierror -> deterministic JOIN recovery -> rule-based fallback.

HOW TO RUN
-----------
  pip install transformers torch sentencepiece sqlparse accelerate gdown
  python app.py
"""

from __future__ import annotations

import logging
import os
import re
import json

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# ★  GOOGLE DRIVE CONFIG  ★
# Paste your Drive folder ID here after Colab training is done.
# Leave as "" to skip Drive and fall through to HuggingFace Hub models.
# ══════════════════════════════════════════════════════════════════════════════
DRIVE_FOLDER_ID = ""   # ← PASTE YOUR FOLDER ID HERE
#   Example: DRIVE_FOLDER_ID = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

MODEL_OVERRIDE = ""   # Force a specific HuggingFace model ID (leave "" for auto)

GPU_MODEL   = "motherduckdb/DuckDB-NSQL-7B-v0.1"
CPU_MODEL   = "gaussalgo/T5-LM-Large-text2sql-spider"
MULTI_MODEL = "juierror/flan-t5-text2sql-with-schema-v2"

_THIS_DIR      = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR   = os.path.dirname(_THIS_DIR)
CHECKPOINT_DIR = os.path.join(_BACKEND_DIR, "checkpoints", "flan-t5-sql")

# Where to cache the Drive download locally
DRIVE_CACHE_DIR = os.path.join(_BACKEND_DIR, "checkpoints", "flan-t5-drive")

# ══════════════════════════════════════════════════════════════════════════════
# Rule-based fallback
# ══════════════════════════════════════════════════════════════════════════════
try:
    from models.enhanced_sql import EnhancedSQLGenerator
except ImportError:
    try:
        from enhanced_sql import EnhancedSQLGenerator
    except ImportError:
        EnhancedSQLGenerator = None

_rule_based = EnhancedSQLGenerator() if EnhancedSQLGenerator else None

BLOCKED = re.compile(
    r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|TRUNCATE|EXEC|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


# ══════════════════════════════════════════════════════════════════════════════
# Google Drive downloader
# ══════════════════════════════════════════════════════════════════════════════

def _download_from_drive(folder_id: str, dest_dir: str) -> bool:
    """
    Downloads all files from a shared Google Drive FOLDER into dest_dir.
    Requires:  pip install gdown
    Returns True on success.

    The Colab notebook saves these files:
        config.json, generation_config.json, tokenizer.json,
        tokenizer_config.json, special_tokens_map.json,
        spiece.model, pytorch_model.bin (or model.safetensors),
        querymind_meta.json
    """
    try:
        import gdown
    except ImportError:
        logger.warning(
            "gdown not installed — run:  pip install gdown\n"
            "  Skipping Drive download."
        )
        return False

    # Check if already downloaded (look for config.json as sentinel)
    sentinel = os.path.join(dest_dir, "config.json")
    if os.path.isfile(sentinel):
        logger.info(f"Drive model already cached at {dest_dir}")
        return True

    os.makedirs(dest_dir, exist_ok=True)
    folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
    logger.info(f"Downloading fine-tuned model from Drive: {folder_url}")
    logger.info(f"  → Destination: {dest_dir}")

    try:
        # gdown.download_folder downloads all files in the shared folder
        gdown.download_folder(
            url=folder_url,
            output=dest_dir,
            quiet=False,
            use_cookies=False,
        )
        if os.path.isfile(sentinel):
            logger.info("✅ Drive model downloaded successfully")
            return True
        else:
            logger.warning(
                "Drive download ran but config.json not found.\n"
                "  Make sure the folder is shared as 'Anyone with the link'."
            )
            return False
    except Exception as exc:
        logger.warning(f"Drive download failed: {exc}")
        return False


def _load_drive_meta(dest_dir: str) -> dict:
    """Loads querymind_meta.json saved by the Colab notebook."""
    meta_path = os.path.join(dest_dir, "querymind_meta.json")
    if os.path.isfile(meta_path):
        with open(meta_path) as f:
            return json.load(f)
    return {"prompt_format": "gaussalgo"}


# ══════════════════════════════════════════════════════════════════════════════
# GPU Detection
# ══════════════════════════════════════════════════════════════════════════════

def _detect_gpu() -> bool:
    try:
        import torch
        if not torch.cuda.is_available():
            return False
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        logger.info(
            f"GPU: {torch.cuda.get_device_name(0)} ({vram_gb:.1f} GB VRAM)"
        )
        return vram_gb >= 4.0
    except Exception:
        return False


def _select_primary_model() -> tuple[str, str]:
    """
    Returns (model_id_or_path, model_type).
    model_type: 'gaussalgo' | 'duckdb'

    Priority:
      1. Fine-tuned model from Google Drive
      2. MODEL_OVERRIDE
      3. Local checkpoint
      4. GPU → DuckDB-NSQL-7B
      5. CPU → gaussalgo
    """
    # ── 1. Google Drive fine-tuned model ─────────────────────────────────
    if DRIVE_FOLDER_ID:
        ok = _download_from_drive(DRIVE_FOLDER_ID, DRIVE_CACHE_DIR)
        if ok:
            meta = _load_drive_meta(DRIVE_CACHE_DIR)
            fmt  = meta.get("prompt_format", "gaussalgo")
            logger.info(
                f"Using Drive fine-tuned model: {DRIVE_CACHE_DIR} (format={fmt})"
            )
            return DRIVE_CACHE_DIR, fmt

    # ── 2. MODEL_OVERRIDE ─────────────────────────────────────────────────
    if MODEL_OVERRIDE:
        logger.info(f"Model override: {MODEL_OVERRIDE}")
        mtype = "duckdb" if "duckdb" in MODEL_OVERRIDE.lower() else "gaussalgo"
        return MODEL_OVERRIDE, mtype

    # ── 3. Local checkpoint ───────────────────────────────────────────────
    if os.path.isdir(CHECKPOINT_DIR) and os.listdir(CHECKPOINT_DIR):
        logger.info(f"Local checkpoint: {CHECKPOINT_DIR}")
        return CHECKPOINT_DIR, "gaussalgo"

    # ── 4/5. HuggingFace Hub auto-select ─────────────────────────────────
    if _detect_gpu():
        logger.info("GPU → DuckDB-NSQL-7B")
        return GPU_MODEL, "duckdb"

    logger.info("CPU → gaussalgo")
    return CPU_MODEL, "gaussalgo"


# ══════════════════════════════════════════════════════════════════════════════
# Prompt Builders
# ══════════════════════════════════════════════════════════════════════════════

class PromptBuilder:

    MAX_SAMPLES = 5

    # ── gaussalgo / fine-tuned model format ───────────────────────────────
    def build_gaussalgo(self, question: str, schema: str,
                        table_name: str, sample_values: dict | None = None,
                        foreign_keys: list | None = None) -> str:
        schema_str = self._format_compact(
            table_name, schema, sample_values or {}, foreign_keys or [])
        return (
            f"convert question and schema to SQL query.\n"
            f"question: {question}\n"
            f"schema: {schema_str}\n"
            f"SQL:"
        )

    def build_gaussalgo_multi(self, question: str, tables_info: list) -> str:
        parts = [
            self._format_compact(t["name"], t.get("schema", ""),
                                 t.get("sample_values", {}),
                                 t.get("foreign_keys", []))
            for t in tables_info
        ]
        return (
            f"convert question and schema to SQL query.\n"
            f"question: {question}\n"
            f"schema: {' | '.join(parts)}\n"
            f"SQL:"
        )

    def _format_compact(self, table_name: str, schema: str,
                        sample_values: dict, foreign_keys: list) -> str:
        col_parts = []
        for part in schema.split(","):
            pts = part.strip().split()
            if pts:
                col   = pts[0].strip().strip('"`')
                dtype = re.sub(r"\(.*\)", "",
                               pts[1].upper() if len(pts) > 1 else "TEXT")
                vals  = sample_values.get(col, [])
                if vals:
                    col_parts.append(
                        f"{col} {dtype} [sample: "
                        f"{','.join(str(v) for v in vals[:self.MAX_SAMPLES])}]"
                    )
                else:
                    col_parts.append(f"{col} {dtype}")
        fk_note = (" FK: " + " | ".join(foreign_keys)) if foreign_keys else ""
        return f"{table_name}({', '.join(col_parts)}{fk_note})"

    # ── DuckDB-NSQL-7B format ─────────────────────────────────────────────
    def build_duckdb(self, question: str, schema: str,
                     table_name: str, sample_values: dict | None = None) -> str:
        col_defs   = self._parse_schema_to_create(schema, table_name)
        sv_comment = self._sample_values_comment(schema, sample_values or {})
        return (
            f"### Instruction:\n"
            f"Your task is to generate valid duckdb SQL to answer the following question.\n"
            f"### Input:\n"
            f"Here is the database schema that the SQL query will run on:\n"
            f"{col_defs}\n"
            f"{sv_comment}"
            f"### Question:\n"
            f"{question}\n"
            f"### Response (use duckdb shorthand if possible):\n"
        )

    def build_duckdb_multi(self, question: str, tables_info: list) -> str:
        creates = "\n".join(
            self._parse_schema_to_create(
                t.get("schema", ""), t["name"], t.get("foreign_keys", [])
            )
            for t in tables_info
        )
        sv_comments = "".join(
            self._sample_values_comment(t.get("schema", ""),
                                        t.get("sample_values", {}))
            for t in tables_info
        )
        return (
            f"### Instruction:\n"
            f"Your task is to generate valid duckdb SQL to answer the following question.\n"
            f"### Input:\n"
            f"Here is the database schema that the SQL query will run on:\n"
            f"{creates}\n"
            f"{sv_comments}"
            f"### Question:\n"
            f"{question}\n"
            f"### Response (use duckdb shorthand if possible):\n"
        )

    def _parse_schema_to_create(self, schema: str, table_name: str,
                                 foreign_keys: list | None = None) -> str:
        col_parts = []
        for part in schema.split(","):
            pts = part.strip().split()
            if pts:
                col   = pts[0].strip().strip('"`')
                dtype = pts[1].upper() if len(pts) > 1 else "TEXT"
                col_parts.append(f"    {col} {dtype}")
        fk_lines = ""
        if foreign_keys:
            fk_lines = "\n    -- FK: " + " | ".join(foreign_keys)
        return (
            f'CREATE TABLE "{table_name}"(\n'
            + ",\n".join(col_parts)
            + fk_lines
            + "\n);"
        )

    def _sample_values_comment(self, schema: str, sample_values: dict) -> str:
        if not sample_values:
            return ""
        lines = []
        for part in schema.split(","):
            pts = part.strip().split()
            if pts:
                col  = pts[0].strip().strip('"`')
                vals = sample_values.get(col, [])
                if vals:
                    lines.append(
                        f"-- {col}: {', '.join(str(v) for v in vals[:self.MAX_SAMPLES])}"
                    )
        return ("-- Sample values:\n" + "\n".join(lines) + "\n") if lines else ""

    # ── juierror multi-table refinement ───────────────────────────────────
    def build_juierror_refine(self, question: str, tables_info: list,
                               previous_sql: str | None) -> str:
        """
        Stage-2 prompt with a deterministic JOIN contract.

        The relationship resolver decides JOIN keys. juierror is no longer
        asked to invent them. It only interprets the user's requested columns,
        filters, grouping and ordering.
        """
        schema_str = self.build_gaussalgo_multi(question, tables_info)

        # Stable alias assignment based on selected-table order.
        alias_map = {
            t["name"]: f"T{i + 1}"
            for i, t in enumerate(tables_info)
        }

        alias_lines = []
        column_lines = []

        for t in tables_info:
            table_name = t["name"]
            alias = alias_map[table_name]

            cols = []
            for part in t.get("schema", "").split(","):
                pts = part.strip().split()
                if pts:
                    cols.append(pts[0].strip().strip('"`'))

            alias_lines.append(f"{alias} = {table_name}")
            column_lines.append(
                f"{alias} allowed columns: {', '.join(cols)}"
            )

        # Extract only resolver-verified relationships.
        verified = []
        for t in tables_info:
            for hint in t.get("foreign_keys", []):
                if not hint.startswith("VERIFIED JOIN:"):
                    continue

                relation = hint.split("VERIFIED JOIN:", 1)[1].strip()

                # Remove any optional confidence annotation.
                relation = re.sub(
                    r"\s*\(confidence=.*?\)\s*$", "",
                    relation
                ).strip()

                if relation and relation not in verified:
                    verified.append(relation)

        join_contract_lines = []

        for relation in verified:
            m = re.match(
                r'([A-Za-z_]\w*)\.([A-Za-z_]\w*)\s*=\s*'
                r'([A-Za-z_]\w*)\.([A-Za-z_]\w*)',
                relation
            )

            if not m:
                continue

            left_table, left_col, right_table, right_col = m.groups()

            if left_table not in alias_map or right_table not in alias_map:
                continue

            join_contract_lines.append(
                f'{alias_map[left_table]}.{left_col} = '
                f'{alias_map[right_table]}.{right_col}'
            )

        aliases_text = "\n".join(alias_lines)
        columns_text = "\n".join(column_lines)

        if join_contract_lines:
            joins_text = "\n".join(
                f"- {line}" for line in join_contract_lines
            )
        else:
            joins_text = "- No verified relationship available."

        rules = (
            "STRICT RULES:\n"
            "1. Use only the aliases listed in TABLE ALIASES.\n"
            "2. Use only columns listed for that exact alias.\n"
            "3. When joining tables, use the MANDATORY VERIFIED JOIN exactly.\n"
            "4. Do not invent another JOIN key.\n"
            "5. Do not create aliases other than the listed aliases.\n"
            "6. Do not invent filters or literal values.\n"
            "7. Add WHERE only when the user's question explicitly asks for filtering.\n"
            "8. LIMIT is a SQL clause and is never a column.\n"
            "9. Never output alias.limit, table.limit, an empty WHERE, or duplicate LIMIT.\n"
            "10. Return exactly one valid SELECT statement and no explanation.\n"
        )

        contract = (
            f"TABLE ALIASES:\n{aliases_text}\n\n"
            f"ALLOWED COLUMNS:\n{columns_text}\n\n"
            f"MANDATORY VERIFIED JOIN:\n{joins_text}\n"
        )

        if previous_sql:
            return (
                f"Refine the SQL for the user's multi-table request.\n"
                f"question: {question}\n"
                f"schema: {schema_str}\n\n"
                f"{contract}\n"
                f"{rules}\n"
                f"previous SQL: {previous_sql}\n"
                f"SQL:"
            )

        return (
            f"Generate SQL for the user's multi-table request.\n"
            f"question: {question}\n"
            f"schema: {schema_str}\n\n"
            f"{contract}\n"
            f"{rules}\n"
            f"SQL:"
        )


# ══════════════════════════════════════════════════════════════════════════════
# FLAN-T5 SQL Generator
# ══════════════════════════════════════════════════════════════════════════════

class FLANT5SQLGenerator:

    def __init__(self):
        self.primary_model      = None
        self.primary_tokenizer  = None
        self.primary_model_type = "gaussalgo"
        self.multi_model        = None
        self.multi_tokenizer    = None
        self.torch              = None
        self.available          = False
        self.multi_available    = False
        self.prompt_builder     = PromptBuilder()
        self._load_models()

    # ── Model loading ──────────────────────────────────────────────────────

    def _load_models(self):
        try:
            import torch
            from transformers import (AutoTokenizer, AutoModelForSeq2SeqLM,
                                      AutoModelForCausalLM)

            self.torch = torch

            primary_id, model_type  = _select_primary_model()
            self.primary_model_type = model_type

            logger.info(f"Loading primary model: {primary_id} (type={model_type})")

            self.primary_tokenizer = AutoTokenizer.from_pretrained(
                primary_id, legacy=False)

            if model_type == "duckdb":
                self.primary_model = AutoModelForCausalLM.from_pretrained(
                    primary_id,
                    torch_dtype=torch.float16 if torch.cuda.is_available()
                                else torch.float32,
                    device_map="auto" if torch.cuda.is_available() else None,
                )
            else:
                # gaussalgo format covers both the HF model AND our fine-tuned model
                self.primary_model = AutoModelForSeq2SeqLM.from_pretrained(
                    primary_id, torch_dtype=torch.float32)

            self.primary_model.eval()
            self.available = True
            logger.info(f"✅ Primary model loaded: {primary_id}")

            # ── juierror for multi-table JOIN refinement ───────────────────
            logger.info(f"Loading multi-table model: {MULTI_MODEL}")
            self.multi_tokenizer = AutoTokenizer.from_pretrained(
                MULTI_MODEL, legacy=False)
            self.multi_model = AutoModelForSeq2SeqLM.from_pretrained(
                MULTI_MODEL, torch_dtype=torch.float32)
            self.multi_model.eval()
            self.multi_available = True
            logger.info(f"✅ Multi-table model loaded: {MULTI_MODEL}")

        except Exception as exc:
            logger.warning(
                f"⚠️  Model load failed: {exc}\n"
                "    → Using rule-based SQL fallback."
            )

    # ── Schema helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _extract_schema_cols(schema: str) -> list[str]:
        cols = []
        for part in schema.split(","):
            pts = part.strip().split()
            if pts:
                cols.append(pts[0].strip().strip('"`'))
        return cols

    @staticmethod
    def _extract_schema_cols_multi(tables_info: list) -> list[str]:
        cols = []
        for t in tables_info:
            for part in t.get("schema", "").split(","):
                pts = part.strip().split()
                if pts:
                    cols.append(pts[0].strip().strip('"`'))
        return cols

    @staticmethod
    def _extract_schema_map_multi(tables_info: list) -> dict[str, set[str]]:
        """Return {table_name_lower: {column_name_lower, ...}} for validation."""
        schema_map: dict[str, set[str]] = {}
        for t in tables_info:
            table_name = str(t.get("name", "")).strip()
            if not table_name:
                continue
            cols: set[str] = set()
            for part in t.get("schema", "").split(","):
                pts = part.strip().split()
                if pts:
                    cols.add(pts[0].strip().strip('"`').lower())
            schema_map[table_name.lower()] = cols
        return schema_map

    @staticmethod
    def _schema_column_names(schema: str) -> list[str]:
        """Extract original-cased column names from the compact schema string."""
        cols = []
        for part in schema.split(","):
            pts = part.strip().split()
            if pts:
                cols.append(pts[0].strip().strip('"`'))
        return cols

    # ── Public API ─────────────────────────────────────────────────────────

    def generate_sql(self, question: str, schema: str,
                     table_name: str, db_service=None) -> str:
        if self.available:
            samples     = self._get_sample_values(table_name, schema, db_service)
            schema_cols = self._extract_schema_cols(schema)

            if self.primary_model_type == "duckdb":
                prompt = self.prompt_builder.build_duckdb(
                    question, schema, table_name, samples)
            else:
                # gaussalgo format — used for both HF model and Drive fine-tuned model
                prompt = self.prompt_builder.build_gaussalgo(
                    question, schema, table_name, samples)

            sql = self._llm_generate(prompt, use_multi=False)
            if sql and self._is_valid(sql, table_name, schema_cols):
                logger.info(f"[{self.primary_model_type.upper()}] {sql[:120]}")
                return sql
            logger.warning(f"[{self.primary_model_type.upper()}] invalid — fallback")

        if _rule_based:
            return _rule_based.generate_sql(question, schema, table_name)
        return f"SELECT * FROM {table_name} LIMIT 100"


    @staticmethod
    def _multi_table_aliases(tables_info: list) -> dict:
        """Stable aliases used only by the deterministic multi-table path."""
        return {
            t["name"]: f"T{i + 1}"
            for i, t in enumerate(tables_info)
        }

    @staticmethod
    def _schema_columns_for_table(schema: str) -> list[str]:
        cols = []
        for part in (schema or "").split(","):
            pts = part.strip().split()
            if pts:
                col = pts[0].strip().strip('"`')
                if col and col not in cols:
                    cols.append(col)
        return cols

    @staticmethod
    def _question_requests_simple_join(question: str) -> bool:
        """
        Conservative gate.

        The deterministic builder handles retrieval/projection JOIN queries.
        Aggregate, grouping, ordering and explicit filtering queries continue
        through the existing LLM + validator + fallback pipeline.
        """
        q = (question or "").lower()

        complex_markers = (
            " where ", " greater than ", " less than ", " above ", " below ",
            " between ", " equals ", " equal to ", " not equal ",
            " count ", " average ", " avg ", " sum ", " total ",
            " minimum ", " maximum ", " min ", " max ",
            " group by ", " grouped by ", " order by ", " sort ",
            " highest ", " lowest ", " top ", " bottom ",
            " having ", " per ", " each "
        )

        padded = f" {q} "
        return not any(marker in padded for marker in complex_markers)

    @staticmethod
    def _question_requests_all_columns(question: str) -> bool:
        q = (question or "").lower()
        phrases = (
            "all data", "all records", "all rows", "everything",
            "all columns", "complete data", "entire data",
            "data from both", "records from both",
            "data from all", "records from all"
        )
        return any(p in q for p in phrases)

    def _infer_requested_projection(self, question: str,
                                    tables_info: list,
                                    alias_map: dict) -> list[str]:
        """
        Infer only columns explicitly named in the user's question.

        Rules:
        - Unique column names are mapped directly to their owning table.
        - Duplicate names are associated with an explicitly mentioned table
          using nearby "... columns ... from <table>" wording when possible.
        - JOIN-key mentions such as "matching IDs" are not automatically added
          unless the column was also requested as output.
        """
        q_original = question or ""
        q = q_original.lower()

        table_cols = {}
        ownership = {}

        for t in tables_info:
            name = t["name"]
            cols = self._schema_columns_for_table(t.get("schema", ""))
            table_cols[name] = cols
            for col in cols:
                ownership.setdefault(col.lower(), []).append((name, col))

        selected = []
        selected_keys = set()

        def add(table_name: str, col: str):
            key = (table_name.lower(), col.lower())
            if key in selected_keys:
                return
            selected_keys.add(key)
            selected.append(f'{alias_map[table_name]}."{col}"')

        # Capture wording like:
        # "id and name from random3"
        # "age, city and score from random_data"
        for table_name, cols in table_cols.items():
            table_re = re.escape(table_name.lower())

            # Up to ~140 chars before "from <table>".
            for m in re.finditer(rf'(.{{0,140}}?)\bfrom\s+{table_re}\b', q):
                context = m.group(1)

                # Keep the most recent clause so an earlier table phrase does
                # not steal columns belonging to a later "... from table".
                cut_points = [
                    context.rfind("along with"),
                    context.rfind(" together with"),
                    context.rfind(" and also "),
                    context.rfind(";"),
                ]
                cut = max(cut_points)
                if cut >= 0:
                    context = context[cut:]

                for col in cols:
                    if re.search(rf'\b{re.escape(col.lower())}\b', context):
                        add(table_name, col)

            # Wording like "random3 id", "random3.id", "random3's id".
            for col in cols:
                direct_patterns = (
                    rf'\b{table_re}\s*\.\s*{re.escape(col.lower())}\b',
                    rf"\b{table_re}'s\s+{re.escape(col.lower())}\b",
                    rf'\b{table_re}\s+{re.escape(col.lower())}\b',
                )
                if any(re.search(p, q) for p in direct_patterns):
                    add(table_name, col)

        # Map globally mentioned columns.
        for col_lower, owners in ownership.items():
            if not re.search(rf'\b{re.escape(col_lower)}\b', q):
                continue

            # Unique ownership is safe.
            if len(owners) == 1:
                table_name, actual_col = owners[0]
                add(table_name, actual_col)
                continue

            # Duplicate column name: keep any explicit association already found.
            already = [
                (t, c) for t, c in owners
                if (t.lower(), c.lower()) in selected_keys
            ]
            if already:
                continue

            # Otherwise associate the mention with the nearest "from <table>"
            # that follows the column mention.
            col_positions = [m.start() for m in re.finditer(
                rf'\b{re.escape(col_lower)}\b', q
            )]
            best = None

            for col_pos in col_positions:
                for table_name, actual_col in owners:
                    after = q.find(f"from {table_name.lower()}", col_pos)
                    if after != -1:
                        distance = after - col_pos
                        if distance <= 120 and (best is None or distance < best[0]):
                            best = (distance, table_name, actual_col)

            if best:
                add(best[1], best[2])

        return selected

    def _build_deterministic_join_sql(self, question: str,
                                      tables_info: list) -> str | None:
        """
        Build a safe FROM/JOIN skeleton from resolver-verified relationships.

        This path intentionally does NOT let an LLM invent table aliases,
        JOIN keys, GROUP BY, HAVING, filters, or literal values.
        """
        if len(tables_info) < 2:
            return None

        if not self._question_requests_simple_join(question):
            return None

        verified = self._verified_join_pairs_from_tables_info(tables_info)
        if not verified:
            return None

        alias_map = self._multi_table_aliases(tables_info)
        selected_tables = [t["name"] for t in tables_info]
        selected_lookup = {t.lower(): t for t in selected_tables}

        # Build a connected JOIN tree using only verified relationships.
        root = selected_tables[0]
        joined = {root.lower()}
        join_clauses = []
        remaining = set(t.lower() for t in selected_tables[1:])

        # Several relationships may exist for >2 tables. Add only edges that
        # connect a new table to the already-connected component.
        progress = True
        while remaining and progress:
            progress = False

            for left_table, left_col, right_table, right_col in verified:
                lkey = left_table.lower()
                rkey = right_table.lower()

                if lkey not in selected_lookup or rkey not in selected_lookup:
                    continue

                if lkey in joined and rkey in remaining:
                    lt = selected_lookup[lkey]
                    rt = selected_lookup[rkey]
                    join_clauses.append(
                        f'JOIN "{rt}" AS {alias_map[rt]} '
                        f'ON {alias_map[lt]}."{left_col}" = '
                        f'{alias_map[rt]}."{right_col}"'
                    )
                    joined.add(rkey)
                    remaining.remove(rkey)
                    progress = True
                    break

                if rkey in joined and lkey in remaining:
                    lt = selected_lookup[lkey]
                    rt = selected_lookup[rkey]
                    join_clauses.append(
                        f'JOIN "{lt}" AS {alias_map[lt]} '
                        f'ON {alias_map[rt]}."{right_col}" = '
                        f'{alias_map[lt]}."{left_col}"'
                    )
                    joined.add(lkey)
                    remaining.remove(lkey)
                    progress = True
                    break

        # Do not guess if all selected tables cannot be connected safely.
        if remaining:
            logger.warning(
                "[DETERMINISTIC JOIN] verified relationships do not connect "
                f"all selected tables: {sorted(remaining)}"
            )
            return None

        if self._question_requests_all_columns(question):
            projection = [
                f'{alias_map[t["name"]]}.*'
                for t in tables_info
            ]
        else:
            projection = self._infer_requested_projection(
                question, tables_info, alias_map
            )

        # If the user did not explicitly request any recognizable columns,
        # leave the query to the existing model/fallback path rather than guess.
        if not projection:
            return None

        sql = (
            "SELECT " + ", ".join(projection) + "\n"
            f'FROM "{root}" AS {alias_map[root]}\n'
            + "\n".join(join_clauses)
            + "\nLIMIT 100"
        )

        return sql

    def generate_multi_sql(self, question: str,
                           tables: list, db_service) -> str:
        if len(tables) == 1:
            schema = db_service.get_schema(tables[0])
            return self.generate_sql(question, schema, tables[0], db_service)

        # ═══════════════════════════════════════════════════════════════════
        # ULTIMATE HYBRID MULTI-TABLE PIPELINE
        #
        # MODEL-FIRST by design:
        #   Stage 1  -> primary / fine-tuned model
        #   Stage 2  -> juierror multi-table refinement
        #   Stage 3  -> deterministic JOIN recovery (verified relationships)
        #   Stage 4  -> existing EnhancedSQLGenerator rule-based fallback
        #
        # This guarantees that, whenever the models are available, they are
        # actually invoked before deterministic/rule-based recovery.
        # ═══════════════════════════════════════════════════════════════════
        tables_info      = self._build_tables_info(tables, db_service)
        schema_cols      = self._extract_schema_cols_multi(tables_info)
        table_schema_map = self._extract_schema_map_multi(tables_info)

        if self.available:
            # ── Stage 1: primary model / user fine-tuned replacement ───────
            if self.primary_model_type == "duckdb":
                prompt1 = self.prompt_builder.build_duckdb_multi(
                    question, tables_info
                )
            else:
                prompt1 = self.prompt_builder.build_gaussalgo_multi(
                    question, tables_info
                )

            sql_1 = self._llm_generate(prompt1, use_multi=False)

            print(
                f"[HYBRID STAGE 1 - {self.primary_model_type.upper()}] "
                f"MODEL ACTIVATED"
            )
            print(f"[PRIMARY MODEL GENERATED SQL] {sql_1}")

            stage1_ok = bool(
                sql_1
                and self._is_valid_multi(
                    sql_1, tables, schema_cols, table_schema_map
                )
                and self._uses_verified_join_contract(
                    sql_1, tables_info
                )
                and self._duckdb_valid_sql(
                    sql_1, db_service
                )
            )

            if stage1_ok:
                print("[HYBRID STAGE 1] valid model SQL")
            else:
                print("[HYBRID STAGE 1] invalid — attempting Stage 2")

            # ── Stage 2: juierror refinement model ─────────────────────────
            if self.multi_available:
                prompt2 = self.prompt_builder.build_juierror_refine(
                    question,
                    tables_info,
                    previous_sql=sql_1 if stage1_ok else None
                )

                sql_2 = self._llm_generate(prompt2, use_multi=True)

                print("🔥 JUIERROR STAGE ACTIVATED")
                print(f"[JUIERROR GENERATED SQL] {sql_2}")

                stage2_ok = bool(
                    sql_2
                    and self._is_valid_multi(
                        sql_2, tables, schema_cols, table_schema_map
                    )
                    and self._uses_verified_join_contract(
                        sql_2, tables_info
                    )
                    and self._duckdb_valid_sql(
                        sql_2, db_service
                    )
                )

                if stage2_ok:
                    print("[HYBRID RESULT] accepted juierror model SQL")
                    return sql_2

                print("[HYBRID STAGE 2] invalid juierror SQL")

            # If refinement fails but Stage-1 itself was valid, preserve the
            # primary model result. This ensures a valid fine-tuned-model SQL
            # is never discarded merely because the refiner failed.
            if stage1_ok:
                print("[HYBRID RESULT] accepted primary model SQL")
                return sql_1

            print(
                "[HYBRID] model stages failed validation — "
                "starting deterministic recovery"
            )
        else:
            print(
                "[HYBRID] primary model unavailable — "
                "starting deterministic recovery"
            )

        # ── Stage 3: deterministic JOIN recovery ───────────────────────────
        # This is a fallback, NOT the primary generator. It handles simple
        # multi-table retrieval only and uses resolver-verified relationships.
        deterministic_sql = self._build_deterministic_join_sql(
            question, tables_info
        )

        if deterministic_sql:
            deterministic_ok = bool(
                self._is_valid_multi(
                    deterministic_sql,
                    tables,
                    schema_cols,
                    table_schema_map
                )
                and self._uses_verified_join_contract(
                    deterministic_sql,
                    tables_info
                )
                and self._duckdb_valid_sql(
                    deterministic_sql,
                    db_service
                )
            )

            if deterministic_ok:
                print("[HYBRID STAGE 3] deterministic recovery accepted")
                print(f"[DETERMINISTIC JOIN SQL] {deterministic_sql}")
                return deterministic_sql

            print(
                "[HYBRID STAGE 3] deterministic SQL failed validation — "
                "using rule-based fallback"
            )

        # ── Stage 4: preserve existing rule-based fallback ─────────────────
        if _rule_based:
            print("[HYBRID STAGE 4] EnhancedSQLGenerator fallback activated")
            fallback_sql = _rule_based.generate_multi_sql(
                question, tables, db_service
            )
            print(f"[RULE-BASED GENERATED SQL] {fallback_sql}")
            return fallback_sql

        return f"SELECT * FROM {tables[0]} LIMIT 100"

    # ── Sample values ──────────────────────────────────────────────────────

    def _get_sample_values(self, table_name: str,
                           schema: str, db_service) -> dict:
        if db_service is None:
            return {}
        TEXT_TYPES = {"VARCHAR","TEXT","CHAR","STRING","NVARCHAR","ENUM"}
        NUM_TYPES  = {"INT","INTEGER","FLOAT","DOUBLE","DECIMAL",
                      "NUMERIC","BIGINT","REAL","SMALLINT"}
        result = {}
        for part in schema.split(","):
            pts = part.strip().split()
            if not pts:
                continue
            col   = pts[0].strip().strip('"`')
            dtype = re.sub(r"\(.*\)", "",
                           pts[1].upper() if len(pts) > 1 else "TEXT")
            try:
                if dtype in TEXT_TYPES:
                    rows = db_service.conn.execute(
                        f'SELECT DISTINCT "{col}" FROM "{table_name}" '
                        f'WHERE "{col}" IS NOT NULL LIMIT 5'
                    ).fetchall()
                    result[col] = [r[0] for r in rows if r[0] is not None]
                elif dtype in NUM_TYPES:
                    row = db_service.conn.execute(
                        f'SELECT MIN("{col}"), MAX("{col}") FROM "{table_name}"'
                    ).fetchone()
                    if row and row[0] is not None:
                        result[col] = [row[0], row[1]]
            except Exception:
                pass
        return result


    @staticmethod
    def _parse_join_schema(schema: str) -> list[dict]:
        cols = []
        numeric = {
            "INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT",
            "FLOAT", "DOUBLE", "REAL", "DECIMAL", "NUMERIC"
        }
        text_types = {"VARCHAR", "TEXT", "CHAR", "STRING", "NVARCHAR", "ENUM"}

        for part in schema.split(","):
            pts = part.strip().split()
            if not pts:
                continue

            name = pts[0].strip().strip('"`')
            dtype = pts[1].upper() if len(pts) > 1 else "TEXT"
            dtype = re.sub(r"\(.*\)", "", dtype)

            if dtype in numeric:
                group = "NUMERIC"
            elif dtype in text_types:
                group = "TEXT"
            elif "DATE" in dtype or "TIME" in dtype:
                group = "DATETIME"
            else:
                group = dtype

            cols.append({"name": name, "type_group": group})

        return cols

    @staticmethod
    def _join_column_name_score(left: str, right: str) -> float:
        left = left.lower().strip()
        right = right.lower().strip()

        if left == right:
            return 1.0

        if left.replace("_", "") == right.replace("_", ""):
            return 0.95

        if ((left == "id" and right.endswith("_id")) or
                (right == "id" and left.endswith("_id"))):
            return 0.92

        def base(x: str) -> str:
            return x[:-3] if x.endswith("_id") else x

        if base(left) == base(right):
            return 0.90

        return 0.0

    def _join_value_overlap(self, left_table: str, left_col: str,
                            right_table: str, right_col: str,
                            db_service) -> float:
        try:
            sql = (
                'WITH l AS ('
                f'SELECT DISTINCT "{left_col}" AS v FROM "{left_table}" '
                f'WHERE "{left_col}" IS NOT NULL LIMIT 100'
                '), r AS ('
                f'SELECT DISTINCT "{right_col}" AS v FROM "{right_table}" '
                f'WHERE "{right_col}" IS NOT NULL LIMIT 100'
                ') '
                'SELECT COUNT(*), '
                '(SELECT COUNT(*) FROM l), '
                '(SELECT COUNT(*) FROM r) '
                'FROM l INNER JOIN r USING(v)'
            )

            row = db_service.conn.execute(sql).fetchone()
            if not row:
                return 0.0

            overlap = int(row[0] or 0)
            left_count = int(row[1] or 0)
            right_count = int(row[2] or 0)
            denominator = max(1, min(left_count, right_count))

            return min(1.0, overlap / denominator)

        except Exception:
            return 0.0

    def _join_uniqueness(self, table: str, column: str, db_service) -> float:
        try:
            row = db_service.conn.execute(
                f'SELECT COUNT("{column}"), '
                f'COUNT(DISTINCT "{column}") FROM "{table}"'
            ).fetchone()

            if not row or not row[0]:
                return 0.0

            return min(1.0, float(row[1] or 0) / float(row[0]))

        except Exception:
            return 0.0

    def _resolve_join_relationships(self, tables: list,
                                    schema_cache: dict,
                                    db_service) -> list[dict]:
        relationships = []

        for i, left_table in enumerate(tables):
            left_cols = self._parse_join_schema(
                schema_cache.get(left_table, "")
            )

            for right_table in tables[i + 1:]:
                right_cols = self._parse_join_schema(
                    schema_cache.get(right_table, "")
                )

                candidates = []

                for left_col in left_cols:
                    for right_col in right_cols:
                        name_score = self._join_column_name_score(
                            left_col["name"], right_col["name"]
                        )

                        if name_score == 0.0:
                            continue

                        if left_col["type_group"] != right_col["type_group"]:
                            continue

                        overlap = self._join_value_overlap(
                            left_table, left_col["name"],
                            right_table, right_col["name"],
                            db_service
                        )

                        uniqueness = max(
                            self._join_uniqueness(
                                left_table, left_col["name"], db_service
                            ),
                            self._join_uniqueness(
                                right_table, right_col["name"], db_service
                            )
                        )

                        score = (
                            0.45 * name_score +
                            0.15 +
                            0.25 * overlap +
                            0.15 * uniqueness
                        )

                        candidates.append({
                            "left_table": left_table,
                            "left_column": left_col["name"],
                            "right_table": right_table,
                            "right_column": right_col["name"],
                            "score": score,
                            "overlap": overlap
                        })

                if candidates:
                    candidates.sort(
                        key=lambda item: item["score"],
                        reverse=True
                    )

                    best = candidates[0]

                    # Require a meaningful deterministic confidence.
                    if best["score"] >= 0.55:
                        relationships.append(best)

        relationships.sort(
            key=lambda item: item["score"],
            reverse=True
        )
        return relationships

    def _build_tables_info(self, tables: list, db_service) -> list:
        infos = []
        schema_cache = {}

        # Read each schema once.
        for table in tables:
            try:
                schema_cache[table] = db_service.get_schema(table)
            except Exception:
                schema_cache[table] = ""

        # Deterministically discover the strongest JOIN relationship.
        relationships = self._resolve_join_relationships(
            tables, schema_cache, db_service
        )

        if relationships:
            print("[JOIN RESOLVER] Verified relationships:")
            for rel in relationships:
                print(
                    f'  - {rel["left_table"]}.{rel["left_column"]} = '
                    f'{rel["right_table"]}.{rel["right_column"]} '
                    f'(confidence={rel["score"]:.2f}, '
                    f'overlap={rel["overlap"]:.2f})'
                )
        else:
            print("[JOIN RESOLVER] No high-confidence relationship found")

        for table in tables:
            try:
                schema = schema_cache.get(table, "")
                samples = self._get_sample_values(
                    table, schema, db_service
                )

                fk_hints = []

                # Preserve the pre-existing DB-service relationship hints.
                for other in tables:
                    if other == table:
                        continue

                    try:
                        common = db_service.get_common_columns(
                            table, other
                        ) or []
                    except Exception:
                        common = []

                    for col in common:
                        hint = f"{table}.{col} -> {other}.{col}"
                        if hint not in fk_hints:
                            fk_hints.append(hint)

                # Add resolver-verified relationships.
                for rel in relationships:
                    if rel["left_table"] == table:
                        hint = (
                            f'VERIFIED JOIN: '
                            f'{rel["left_table"]}.{rel["left_column"]} = '
                            f'{rel["right_table"]}.{rel["right_column"]}'
                        )
                        if hint not in fk_hints:
                            fk_hints.append(hint)

                    elif rel["right_table"] == table:
                        hint = (
                            f'VERIFIED JOIN: '
                            f'{rel["left_table"]}.{rel["left_column"]} = '
                            f'{rel["right_table"]}.{rel["right_column"]}'
                        )
                        if hint not in fk_hints:
                            fk_hints.append(hint)

                infos.append({
                    "name": table,
                    "schema": schema,
                    "sample_values": samples,
                    "foreign_keys": fk_hints
                })

            except Exception:
                infos.append({
                    "name": table,
                    "schema": "",
                    "sample_values": {},
                    "foreign_keys": []
                })

        return infos

    # ── LLM inference ──────────────────────────────────────────────────────

    def _llm_generate(self, prompt: str, use_multi: bool = False):
        try:
            if use_multi and self.multi_available:
                tokenizer = self.multi_tokenizer
                model     = self.multi_model
                is_causal = False
            elif self.available:
                tokenizer = self.primary_tokenizer
                model     = self.primary_model
                is_causal = (self.primary_model_type == "duckdb")
            else:
                return None

            inputs = tokenizer(
                prompt,
                return_tensors="pt",
                max_length=512,     # FLAN-T5-large encoder limit
                truncation=True,
                padding=False,
            )

            if hasattr(model, "device"):
                inputs = {k: v.to(model.device) for k, v in inputs.items()}

            with self.torch.no_grad():
                if is_causal:
                    outputs = model.generate(
                        **inputs,
                        max_new_tokens=256,
                        temperature=0.1,
                        do_sample=False,
                        pad_token_id=tokenizer.eos_token_id,
                    )
                    input_len = inputs["input_ids"].shape[1]
                    raw = tokenizer.decode(
                        outputs[0][input_len:], skip_special_tokens=True)
                else:
                    outputs = model.generate(
                        **inputs,
                        max_new_tokens=150,    # fine-tuned on 150 max — matches Colab
                        num_beams=6,
                        early_stopping=True,
                        no_repeat_ngram_size=3,
                        length_penalty=1.2,
                    )
                    raw = tokenizer.decode(outputs[0], skip_special_tokens=True)

            return self._post_process(raw)

        except Exception as exc:
            logger.error(f"LLM inference error: {exc}")
            return None

    # ── Post-processing ────────────────────────────────────────────────────

    def _post_process(self, raw: str) -> str:
        sql = raw.strip()
        sql = re.sub(r"```(?:sql)?", "", sql, flags=re.IGNORECASE).strip()
        sql = re.sub(r"```", "", sql).strip()
        sql = re.sub(r"^(?:SQL|Answer|A|Query)\s*:\s*", "",
                     sql, flags=re.IGNORECASE).strip()

        sql = re.sub(r'((?:=|!=|<>|<=|>=|<|>)\s*)"([^"]+)"', r"\1'\2'", sql)
        sql = re.sub(r'(LIKE\s+)"([^"]+)"', r"\1'\2'", sql, flags=re.IGNORECASE)
        def _fix_in_clause(m):
            return m.group(0).replace('"', "'")
        sql = re.sub(r'\bIN\s*\([^)]+\)', _fix_in_clause, sql, flags=re.IGNORECASE)

        upper = sql.upper()
        if upper.count("SELECT") > 1:
            sql = sql[upper.rfind("SELECT"):]
        if not sql.upper().lstrip().startswith("SELECT"):
            sql = "SELECT " + sql
        stmts = [s.strip() for s in sql.split(";") if s.strip()]
        sql   = stmts[0] if stmts else sql
        sql   = re.sub(r"\n--.*$", "", sql, flags=re.MULTILINE).strip()
        sql   = self._fix_clause_order(sql)
        try:
            import sqlparse
            sql = sqlparse.format(sql, reindent=True,
                                  keyword_case="upper", strip_whitespace=True)
        except Exception:
            pass
        return sql.strip()

    def _fix_clause_order(self, sql: str) -> str:
        # Targeted safe repair: if the model emitted multiple LIMIT clauses,
        # keep one final LIMIT before normal clause reconstruction.
        limit_matches = re.findall(
            r'\bLIMIT\s+\d+(?:\s+OFFSET\s+\d+)?',
            sql,
            re.IGNORECASE
        )
        if len(limit_matches) > 1:
            final_limit = limit_matches[-1]
            sql = re.sub(
                r'\s*\bLIMIT\s+\d+(?:\s+OFFSET\s+\d+)?',
                '',
                sql,
                flags=re.IGNORECASE
            ).strip()
            sql = f"{sql} {final_limit}"

        PATS = {
            "select":   r"(SELECT\s+.+?)(?=\s+FROM\b)",
            "from":     r"(FROM\s+.+?)(?=\s+(?:WHERE|GROUP|HAVING|ORDER|LIMIT)\b|$)",
            "where":    r"(WHERE\s+.+?)(?=\s+(?:GROUP|HAVING|ORDER|LIMIT)\b|$)",
            "group_by": r"(GROUP\s+BY\s+.+?)(?=\s+(?:HAVING|ORDER|LIMIT)\b|$)",
            "having":   r"(HAVING\s+.+?)(?=\s+(?:ORDER|LIMIT)\b|$)",
            "order_by": r"(ORDER\s+BY\s+.+?)(?=\s+LIMIT\b|$)",
            "limit":    r"(LIMIT\s+\d+(?:\s+OFFSET\s+\d+)?)",
        }
        clauses = {}
        for key, pat in PATS.items():
            m = re.search(pat, sql, re.IGNORECASE | re.DOTALL)
            if m:
                clauses[key] = m.group(1).strip()

        if "select" not in clauses or "from" not in clauses:
            if "limit" in clauses:
                sql = re.sub(
                    r"\s*LIMIT\s+\d+(?:\s+OFFSET\s+\d+)?",
                    "",
                    sql,
                    flags=re.IGNORECASE
                ).strip()
                return sql + " " + clauses["limit"]
            return sql

        parts = [clauses["select"], clauses["from"]]
        for key in ("where", "group_by", "having", "order_by"):
            if key in clauses:
                parts.append(clauses[key])

        if "limit" in clauses:
            parts.append(clauses["limit"])
        elif not re.search(
            r"SELECT\s+(COUNT|SUM|AVG|MIN|MAX)\s*\(",
            sql,
            re.IGNORECASE
        ):
            parts.append("LIMIT 100")

        return "\n".join(parts)

    # ── Validation ─────────────────────────────────────────────────────────

    def _is_valid(self, sql: str, table_name: str,
                  schema_cols: list[str] | None = None) -> bool:
        if not sql or BLOCKED.search(sql):
            return False
        if not sql.strip().upper().startswith("SELECT"):
            return False
        if table_name.lower() not in sql.lower():
            return False
        if schema_cols:
            schema_lower = {c.lower() for c in schema_cols}
            where_cols   = re.findall(
                r'(?:WHERE|AND|OR)\s+["`]?(\w+)["`]?\s*(?:=|!=|<|>|LIKE|IN\b)',
                sql, re.IGNORECASE
            )
            for col in where_cols:
                if col.lower() not in schema_lower:
                    logger.warning(
                        f"[LLM] hallucinated column '{col}' not in "
                        f"{list(schema_cols)} — rejecting"
                    )
                    return False
            select_match = re.search(r'SELECT\s+(.+?)\s+FROM', sql,
                                     re.IGNORECASE | re.DOTALL)
            if select_match:
                select_part = select_match.group(1)
                if select_part.strip() != "*" and not re.search(
                    r'\b(COUNT|SUM|AVG|MIN|MAX)\s*\(', select_part, re.IGNORECASE
                ):
                    for col in re.findall(r'["`]?(\w+)["`]?', select_part):
                        if (col.lower() not in schema_lower
                                and col.upper() not in
                                {"DISTINCT","AS","ALL","TOP"}):
                            logger.warning(
                                f"[LLM] hallucinated SELECT col '{col}' — rejecting"
                            )
                            return False
        try:
            import sqlparse
            parsed = sqlparse.parse(sql)
            return bool(parsed and parsed[0].tokens)
        except Exception:
            return True

    def _is_valid_multi(self, sql: str, tables: list,
                        schema_cols: list[str] | None = None,
                        table_schema_map: dict[str, set[str]] | None = None) -> bool:
        """
        Structural validation for multi-table SQL only.

        Single-table validation is intentionally left unchanged.
        """
        if not sql or BLOCKED.search(sql):
            return False

        sql_clean = sql.strip()

        if not sql_clean.upper().startswith("SELECT"):
            return False

        # Reject multiple statements. _post_process normally keeps one, but this
        # is a final guard for multi-table mode.
        statements = [s.strip() for s in sql_clean.split(";") if s.strip()]
        if len(statements) > 1:
            logger.warning("[LLM multi] multiple SQL statements — rejecting")
            return False

        # Empty WHERE such as:
        #   WHERE
        #   LIMIT 100
        if re.search(
            r'\bWHERE\s*(?=GROUP\s+BY|HAVING|ORDER\s+BY|LIMIT|$)',
            sql_clean,
            re.IGNORECASE | re.DOTALL
        ):
            logger.warning("[LLM multi] empty WHERE clause — rejecting")
            return False

        # LIMIT must be a clause, not a table/alias column.
        if re.search(
            r'\b[A-Za-z_]\w*\.["`]?limit["`]?\s*(?:=|!=|<>|<=|>=|<|>|LIKE|IN\b)',
            sql_clean,
            re.IGNORECASE
        ):
            logger.warning("[LLM multi] LIMIT hallucinated as a column — rejecting")
            return False

        # More than one LIMIT should never leave post-processing.
        if len(re.findall(r'\bLIMIT\s+\d+', sql_clean, re.IGNORECASE)) > 1:
            logger.warning("[LLM multi] duplicate LIMIT clauses — rejecting")
            return False

        # Parse FROM/JOIN table references and aliases.
        # Examples:
        #   FROM random_data
        #   FROM random_data AS T1
        #   JOIN random3 T2
        table_ref_pattern = re.compile(
            r'\b(?:FROM|JOIN)\s+'
            r'["`]?([A-Za-z_]\w*)["`]?'
            r'(?:\s+(?:AS\s+)?["`]?([A-Za-z_]\w*)["`]?)?',
            re.IGNORECASE
        )

        sql_keywords = {
            "WHERE", "JOIN", "INNER", "LEFT", "RIGHT", "FULL", "CROSS",
            "ON", "GROUP", "ORDER", "HAVING", "LIMIT", "OFFSET",
            "UNION", "EXCEPT", "INTERSECT"
        }

        selected_lookup = {t.lower(): t for t in tables}
        alias_to_table: dict[str, str] = {}
        used_tables: set[str] = set()

        for table_token, alias_token in table_ref_pattern.findall(sql_clean):
            table_key = table_token.lower()

            # A generated query must not pull in a table that was not selected.
            if table_key not in selected_lookup:
                logger.warning(
                    f"[LLM multi] unknown/unselected table '{table_token}' — rejecting"
                )
                return False

            actual_table = selected_lookup[table_key]
            used_tables.add(actual_table)
            alias_to_table[table_key] = actual_table

            if alias_token and alias_token.upper() not in sql_keywords:
                alias_to_table[alias_token.lower()] = actual_table

        # In multi-table mode, the generated SQL must really use at least two
        # selected tables. This prevents "FROM random3" from being accepted as
        # a valid JOIN query.
        if len(tables) > 1 and len(used_tables) < 2:
            logger.warning(
                f"[LLM multi] expected >=2 selected tables, found {sorted(used_tables)}"
            )
            return False

        # Validate every qualified alias.column reference against the exact
        # schema of the aliased table.
        if table_schema_map:
            qualified_refs = re.findall(
                r'\b([A-Za-z_]\w*)\.["`]?([A-Za-z_]\w*)["`]?',
                sql_clean
            )

            for alias, column in qualified_refs:
                alias_key = alias.lower()

                if alias_key not in alias_to_table:
                    logger.warning(
                        f"[LLM multi] unknown alias/table '{alias}' — rejecting"
                    )
                    return False

                actual_table = alias_to_table[alias_key]
                allowed_cols = table_schema_map.get(actual_table.lower(), set())

                if column.lower() not in allowed_cols:
                    logger.warning(
                        f"[LLM multi] hallucinated/wrong column "
                        f"'{alias}.{column}' for table '{actual_table}' — rejecting"
                    )
                    return False

        # Keep the previous broad WHERE-column check as an additional guard for
        # unqualified references.
        if schema_cols:
            schema_lower = {c.lower() for c in schema_cols}
            where_cols = re.findall(
                r'(?:WHERE|AND|OR)\s+(?:["`]?\w+["`]?\.)?'
                r'["`]?([A-Za-z_]\w*)["`]?\s*'
                r'(?:=|!=|<>|<=|>=|<|>|LIKE|IN\b)',
                sql_clean,
                re.IGNORECASE
            )

            for col in where_cols:
                if col.lower() not in schema_lower:
                    logger.warning(
                        f"[LLM multi] hallucinated WHERE col '{col}' — rejecting"
                    )
                    return False

        return True

    @staticmethod
    def _verified_join_pairs_from_tables_info(tables_info: list) -> list[tuple]:
        pairs = []

        for t in tables_info:
            for hint in t.get("foreign_keys", []):
                if not hint.startswith("VERIFIED JOIN:"):
                    continue

                relation = hint.split("VERIFIED JOIN:", 1)[1].strip()
                relation = re.sub(
                    r"\s*\(confidence=.*?\)\s*$", "",
                    relation
                ).strip()

                m = re.match(
                    r'([A-Za-z_]\w*)\.([A-Za-z_]\w*)\s*=\s*'
                    r'([A-Za-z_]\w*)\.([A-Za-z_]\w*)',
                    relation
                )

                if not m:
                    continue

                pair = m.groups()
                if pair not in pairs:
                    pairs.append(pair)

        return pairs

    def _uses_verified_join_contract(self, sql: str,
                                     tables_info: list) -> bool:
        """
        Confirm that a generated JOIN uses one of the resolver-verified
        relationships. This does not alter SQL; it only rejects violations.
        """
        verified_pairs = self._verified_join_pairs_from_tables_info(
            tables_info
        )

        # No verified relationship -> allow existing fallback/validation path.
        if not verified_pairs:
            return True

        # Build alias -> table map from generated SQL.
        alias_to_table = {}
        ref_pattern = re.compile(
            r'\b(?:FROM|JOIN)\s+'
            r'["`]?([A-Za-z_]\w*)["`]?'
            r'(?:\s+(?:AS\s+)?["`]?([A-Za-z_]\w*)["`]?)?',
            re.IGNORECASE
        )

        keywords = {
            "WHERE", "JOIN", "INNER", "LEFT", "RIGHT", "FULL", "CROSS",
            "ON", "GROUP", "ORDER", "HAVING", "LIMIT", "OFFSET"
        }

        for table, alias in ref_pattern.findall(sql):
            alias_to_table[table.lower()] = table
            if alias and alias.upper() not in keywords:
                alias_to_table[alias.lower()] = table

        # Collect simple ON alias.col = alias.col expressions.
        on_pairs = re.findall(
            r'\bON\s+'
            r'([A-Za-z_]\w*)\.["`]?([A-Za-z_]\w*)["`]?\s*=\s*'
            r'([A-Za-z_]\w*)\.["`]?([A-Za-z_]\w*)["`]?',
            sql,
            re.IGNORECASE
        )

        for left_alias, left_col, right_alias, right_col in on_pairs:
            left_table = alias_to_table.get(left_alias.lower())
            right_table = alias_to_table.get(right_alias.lower())

            if not left_table or not right_table:
                continue

            for vt1, vc1, vt2, vc2 in verified_pairs:
                forward = (
                    left_table.lower() == vt1.lower()
                    and left_col.lower() == vc1.lower()
                    and right_table.lower() == vt2.lower()
                    and right_col.lower() == vc2.lower()
                )
                reverse = (
                    left_table.lower() == vt2.lower()
                    and left_col.lower() == vc2.lower()
                    and right_table.lower() == vt1.lower()
                    and right_col.lower() == vc1.lower()
                )

                if forward or reverse:
                    return True

        logger.warning(
            "[JOIN CONTRACT] generated SQL did not use a verified JOIN — rejecting"
        )
        return False

    @staticmethod
    def _duckdb_valid_sql(sql: str, db_service) -> bool:
        """
        Execution-guided validation for multi-table SQL.

        EXPLAIN asks DuckDB to parse/bind the statement without executing the
        user's SELECT. This catches errors that regex validation cannot safely
        detect, including:
          - alias/table binder errors
          - nonexistent columns
          - malformed WHERE/LIMIT syntax
          - invalid GROUP BY / aggregate semantics
          - type errors visible during binding
        """
        if not sql or db_service is None:
            return False

        try:
            db_service.conn.execute(f"EXPLAIN {sql}").fetchall()
            return True
        except Exception as exc:
            logger.warning(f"[Multi SQL EXPLAIN] rejecting invalid SQL: {exc}")
            return False


# ══════════════════════════════════════════════════════════════════════════════
# QueryMind Ultimate Model-First Hybrid Extension
# Preserves model loading, fine-tuned replacement paths, prompts, validation,
# deterministic JOIN recovery and EnhancedSQLGenerator fallback above.
# ══════════════════════════════════════════════════════════════════════════════

class FLANT5SQLGenerator(FLANT5SQLGenerator):
    """
    Final model-first hybrid orchestrator.

    Priority
    --------
    1. Primary model (including the existing user fine-tuned replacement path)
    2. juierror multi-table model
    3. one bounded execution-guided juierror repair
    4. deterministic verified-JOIN recovery
    5. EnhancedSQLGenerator rule fallback

    No table, database, CSV or column names are hard-coded.
    """

    def __init__(self):
        super().__init__()
        self.max_repair_attempts = 1

    # ── Generic execution-guided helpers ───────────────────────────────────

    @staticmethod
    def _duckdb_explain_error(sql: str, db_service):
        if not sql or db_service is None:
            return "empty SQL"
        try:
            db_service.conn.execute(f"EXPLAIN {sql}").fetchall()
            return None
        except Exception as exc:
            return str(exc)

    @staticmethod
    def _compact_error(error: str, max_chars: int = 700):
        e = re.sub(r"\s+", " ", str(error or "")).strip()
        return e[:max_chars]

    def _repair_prompt_multi(self, question, tables_info, invalid_sql, error):
        """
        One bounded repair attempt. The model is shown its own invalid SQL,
        DuckDB's binder/parser message, exact schema and verified relationships.
        """
        base = self.prompt_builder.build_juierror_refine(
            question, tables_info, previous_sql=None
        )
        return (
            f"{base}\n\n"
            "The previous SQL failed DuckDB validation.\n"
            f"INVALID SQL:\n{invalid_sql}\n"
            f"DUCKDB ERROR:\n{self._compact_error(error)}\n\n"
            "Repair it using ONLY the supplied schema and MANDATORY VERIFIED JOIN.\n"
            "Do not invent filters, aliases, tables, columns or literal values.\n"
            "Return exactly one corrected SELECT statement.\nSQL:"
        )

    def _valid_multi_candidate(self, sql, tables, schema_cols,
                               table_schema_map, tables_info, db_service):
        if not sql:
            return False
        if not self._is_valid_multi(
            sql, tables, schema_cols, table_schema_map
        ):
            return False
        if not self._uses_verified_join_contract(
            sql, tables_info
        ):
            return False
        return self._duckdb_valid_sql(sql, db_service)

    # ── Single-table model-first override ──────────────────────────────────

    def generate_sql(self, question: str, schema: str,
                     table_name: str, db_service=None) -> str:
        """
        Preserve model-first single-table behavior and add EXPLAIN validation
        when a DuckDB service is available.
        """
        if self.available:
            samples = self._get_sample_values(
                table_name, schema, db_service
            )
            schema_cols = self._extract_schema_cols(schema)

            if self.primary_model_type == "duckdb":
                prompt = self.prompt_builder.build_duckdb(
                    question, schema, table_name, samples
                )
            else:
                prompt = self.prompt_builder.build_gaussalgo(
                    question, schema, table_name, samples
                )

            sql = self._llm_generate(prompt, use_multi=False)
            print(
                f"[HYBRID SINGLE - {self.primary_model_type.upper()}] "
                "MODEL ACTIVATED"
            )
            print(f"[PRIMARY MODEL GENERATED SQL] {sql}")

            valid = bool(
                sql and self._is_valid(
                    sql, table_name, schema_cols
                )
            )

            if valid and db_service is not None:
                valid = self._duckdb_valid_sql(
                    sql, db_service
                )

            if valid:
                print("[HYBRID SINGLE RESULT] accepted model SQL")
                return sql

            print("[HYBRID SINGLE] model SQL invalid — rule fallback")

        if _rule_based:
            fallback = _rule_based.generate_sql(
                question, schema, table_name
            )
            if db_service is None or self._duckdb_valid_sql(
                fallback, db_service
            ):
                print("[HYBRID SINGLE FALLBACK] EnhancedSQLGenerator accepted")
                return fallback

        return f'SELECT * FROM "{table_name}" LIMIT 100'

    # ── Multi-table final model-first hybrid override ──────────────────────

    def generate_multi_sql(self, question: str,
                           tables: list, db_service) -> str:
        if not tables:
            return "SELECT 1 WHERE FALSE"
        if len(tables) == 1:
            schema = db_service.get_schema(tables[0])
            return self.generate_sql(
                question, schema, tables[0], db_service
            )

        tables_info = self._build_tables_info(
            tables, db_service
        )
        schema_cols = self._extract_schema_cols_multi(
            tables_info
        )
        table_schema_map = self._extract_schema_map_multi(
            tables_info
        )

        # ── Stage 1: primary/fine-tuned model ──────────────────────────────
        sql_1 = None
        stage1_ok = False

        if self.available:
            if self.primary_model_type == "duckdb":
                prompt1 = self.prompt_builder.build_duckdb_multi(
                    question, tables_info
                )
            else:
                prompt1 = self.prompt_builder.build_gaussalgo_multi(
                    question, tables_info
                )

            sql_1 = self._llm_generate(
                prompt1, use_multi=False
            )

            print(
                f"[HYBRID STAGE 1 - {self.primary_model_type.upper()}] "
                "MODEL ACTIVATED"
            )
            print(f"[PRIMARY MODEL GENERATED SQL] {sql_1}")

            stage1_ok = self._valid_multi_candidate(
                sql_1, tables, schema_cols, table_schema_map,
                tables_info, db_service
            )

            if stage1_ok:
                print("[HYBRID STAGE 1] valid primary-model SQL")
            else:
                print("[HYBRID STAGE 1] invalid — trying juierror")

        # ── Stage 2: juierror refinement ───────────────────────────────────
        sql_2 = None
        stage2_ok = False
        stage2_error = None

        if self.multi_available:
            prompt2 = self.prompt_builder.build_juierror_refine(
                question,
                tables_info,
                previous_sql=sql_1 if stage1_ok else None,
            )

            sql_2 = self._llm_generate(
                prompt2, use_multi=True
            )

            print("🔥 JUIERROR STAGE ACTIVATED")
            print(f"[JUIERROR GENERATED SQL] {sql_2}")

            if sql_2 and self._is_valid_multi(
                sql_2, tables, schema_cols, table_schema_map
            ) and self._uses_verified_join_contract(
                sql_2, tables_info
            ):
                stage2_error = self._duckdb_explain_error(
                    sql_2, db_service
                )
                stage2_ok = stage2_error is None

            if stage2_ok:
                print("[HYBRID RESULT] accepted juierror model SQL")
                return sql_2

            print("[HYBRID STAGE 2] invalid juierror SQL")

            # ── Stage 2R: one bounded model repair ─────────────────────────
            # Repair only if there is a concrete invalid model output.
            if sql_2 and self.max_repair_attempts > 0:
                if stage2_error is None:
                    stage2_error = (
                        "Schema/alias/JOIN-contract validation failed."
                    )

                repair_prompt = self._repair_prompt_multi(
                    question,
                    tables_info,
                    sql_2,
                    stage2_error,
                )
                repaired = self._llm_generate(
                    repair_prompt, use_multi=True
                )

                print("[HYBRID STAGE 2R] JUIERROR REPAIR ACTIVATED")
                print(f"[JUIERROR REPAIRED SQL] {repaired}")

                if self._valid_multi_candidate(
                    repaired, tables, schema_cols,
                    table_schema_map, tables_info, db_service
                ):
                    print(
                        "[HYBRID RESULT] accepted repaired model SQL"
                    )
                    return repaired

                print(
                    "[HYBRID STAGE 2R] repair invalid — "
                    "continuing recovery"
                )

        # A valid Stage-1 model result remains preferable to non-model recovery.
        if stage1_ok:
            print("[HYBRID RESULT] accepted primary model SQL")
            return sql_1

        # ── Stage 3: deterministic verified-JOIN recovery ──────────────────
        print(
            "[HYBRID] model stages exhausted — "
            "starting deterministic recovery"
        )

        deterministic_sql = self._build_deterministic_join_sql(
            question, tables_info
        )

        if deterministic_sql and self._valid_multi_candidate(
            deterministic_sql,
            tables,
            schema_cols,
            table_schema_map,
            tables_info,
            db_service,
        ):
            print(
                "[HYBRID STAGE 3] deterministic recovery accepted"
            )
            print(
                f"[DETERMINISTIC JOIN SQL] {deterministic_sql}"
            )
            return deterministic_sql

        # ── Stage 4: generic EnhancedSQLGenerator fallback ─────────────────
        if _rule_based:
            print(
                "[HYBRID STAGE 4] EnhancedSQLGenerator "
                "fallback activated"
            )
            fallback_sql = _rule_based.generate_multi_sql(
                question, tables, db_service
            )

            # The fallback is execution-checked before it leaves the generator.
            if fallback_sql and self._duckdb_valid_sql(
                fallback_sql, db_service
            ):
                print(
                    f"[RULE-BASED GENERATED SQL] {fallback_sql}"
                )
                return fallback_sql

            logger.warning(
                "[HYBRID STAGE 4] fallback SQL failed EXPLAIN"
            )

        # Absolute safe terminal fallback.
        return f'SELECT * FROM "{tables[0]}" LIMIT 100'

# ══════════════════════════════════════════════════════════════════════════════
# QueryMind v12 FAST HYBRID override
#
# Latency policy:
#   1) Primary / fine-tuned model is ALWAYS tried first.
#   2) If Stage 1 is valid, return IMMEDIATELY.
#   3) If Stage 1 fails, juierror gets exactly ONE attempt.
#   4) No normal execution-guided second LLM repair pass.
#   5) Then deterministic verified-JOIN recovery.
#   6) Then EnhancedSQLGenerator fallback.
#
# This keeps the system genuinely model-first while preventing unnecessary
# sequential inference calls from making the frontend wait too long.
# ══════════════════════════════════════════════════════════════════════════════

class FLANT5SQLGenerator(FLANT5SQLGenerator):

    def generate_multi_sql(self, question: str, tables: list, db_service) -> str:
        import time

        started = time.perf_counter()

        def elapsed():
            return time.perf_counter() - started

        if not tables:
            print(f"[FAST HYBRID] finished in {elapsed():.2f}s")
            return "SELECT 1 WHERE FALSE"

        # Preserve single-table model-first behavior.
        if len(tables) == 1:
            schema = db_service.get_schema(tables[0])
            sql = self.generate_sql(question, schema, tables[0], db_service)
            print(f"[FAST HYBRID] finished in {elapsed():.2f}s")
            return sql

        # Generic schema + verified relationship grounding.
        tables_info = self._build_tables_info(tables, db_service)
        schema_cols = self._extract_schema_cols_multi(tables_info)
        table_schema_map = self._extract_schema_map_multi(tables_info)

        # ──────────────────────────────────────────────────────────────────
        # Stage 1: primary model / fine-tuned replacement
        # ──────────────────────────────────────────────────────────────────
        if self.available:
            stage1_started = time.perf_counter()

            if self.primary_model_type == "duckdb":
                prompt1 = self.prompt_builder.build_duckdb_multi(
                    question, tables_info
                )
            else:
                prompt1 = self.prompt_builder.build_gaussalgo_multi(
                    question, tables_info
                )

            sql_1 = self._llm_generate(prompt1, use_multi=False)

            print(
                f"[FAST HYBRID STAGE 1 - {self.primary_model_type.upper()}] "
                f"MODEL ACTIVATED ({time.perf_counter()-stage1_started:.2f}s)"
            )
            print(f"[PRIMARY MODEL GENERATED SQL] {sql_1}")

            stage1_ok = self._valid_multi_candidate(
                sql_1,
                tables,
                schema_cols,
                table_schema_map,
                tables_info,
                db_service
            )

            # IMPORTANT latency optimization:
            # a valid primary/fine-tuned-model result is returned immediately.
            if stage1_ok:
                print("[FAST HYBRID RESULT] accepted primary model SQL")
                print(f"[FAST HYBRID] finished in {elapsed():.2f}s")
                return sql_1

            print(
                "[FAST HYBRID STAGE 1] invalid — "
                "trying one juierror pass"
            )

        else:
            print(
                "[FAST HYBRID STAGE 1] primary model unavailable — "
                "trying remaining recovery stages"
            )

        # ──────────────────────────────────────────────────────────────────
        # Stage 2: ONE juierror refinement pass
        # ──────────────────────────────────────────────────────────────────
        if self.multi_available:
            stage2_started = time.perf_counter()

            # Do not send an invalid Stage-1 query as a trusted previous SQL.
            # The schema + verified JOIN contract remain the source of truth.
            prompt2 = self.prompt_builder.build_juierror_refine(
                question,
                tables_info,
                previous_sql=None
            )

            sql_2 = self._llm_generate(prompt2, use_multi=True)

            print(
                "🔥 FAST JUIERROR STAGE ACTIVATED "
                f"({time.perf_counter()-stage2_started:.2f}s)"
            )
            print(f"[JUIERROR GENERATED SQL] {sql_2}")

            stage2_ok = self._valid_multi_candidate(
                sql_2,
                tables,
                schema_cols,
                table_schema_map,
                tables_info,
                db_service
            )

            if stage2_ok:
                print("[FAST HYBRID RESULT] accepted juierror model SQL")
                print(f"[FAST HYBRID] finished in {elapsed():.2f}s")
                return sql_2

            print(
                "[FAST HYBRID STAGE 2] invalid — "
                "skipping extra model repair to save latency"
            )
        else:
            print("[FAST HYBRID STAGE 2] juierror unavailable")

        # ──────────────────────────────────────────────────────────────────
        # Stage 3: deterministic verified-JOIN recovery
        # ──────────────────────────────────────────────────────────────────
        deterministic_started = time.perf_counter()

        deterministic_sql = self._build_deterministic_join_sql(
            question, tables_info
        )

        if deterministic_sql and self._valid_multi_candidate(
            deterministic_sql,
            tables,
            schema_cols,
            table_schema_map,
            tables_info,
            db_service
        ):
            print(
                "[FAST HYBRID STAGE 3] deterministic recovery accepted "
                f"({time.perf_counter()-deterministic_started:.2f}s)"
            )
            print(f"[DETERMINISTIC JOIN SQL] {deterministic_sql}")
            print(f"[FAST HYBRID] finished in {elapsed():.2f}s")
            return deterministic_sql

        print(
            "[FAST HYBRID STAGE 3] no valid deterministic result — "
            "using rule fallback"
        )

        # ──────────────────────────────────────────────────────────────────
        # Stage 4: existing / upgraded EnhancedSQLGenerator fallback
        # ──────────────────────────────────────────────────────────────────
        if _rule_based:
            fallback_started = time.perf_counter()

            fallback_sql = _rule_based.generate_multi_sql(
                question, tables, db_service
            )

            if fallback_sql and self._duckdb_valid_sql(
                fallback_sql, db_service
            ):
                print(
                    "[FAST HYBRID STAGE 4] rule fallback accepted "
                    f"({time.perf_counter()-fallback_started:.2f}s)"
                )
                print(f"[RULE-BASED GENERATED SQL] {fallback_sql}")
                print(f"[FAST HYBRID] finished in {elapsed():.2f}s")
                return fallback_sql

            print("[FAST HYBRID STAGE 4] rule fallback failed EXPLAIN")

        # Absolute safe terminal fallback.
        safe_sql = f'SELECT * FROM "{tables[0]}" LIMIT 100'
        print(f"[FAST HYBRID] safe terminal fallback in {elapsed():.2f}s")
        return safe_sql

# ── Singleton ──────────────────────────────────────────────────────────────
sql_generator = FLANT5SQLGenerator()


# ── CLI test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    print("\n" + "="*60)
    print("QueryMind SQL Generator v10 — Quick Test")
    print(f"Drive folder: {DRIVE_FOLDER_ID or '(not set — using HuggingFace Hub)'}")
    print("="*60)

    schema   = "id BIGINT, name VARCHAR, salary BIGINT, department VARCHAR"
    question = "Get all employees with salary greater than 50000"
    result   = sql_generator.generate_sql(question, schema, "employees")
    print(f"\n[Test 1]\nQ  : {question}\nSQL: {result}")

    schema2   = "order_id BIGINT, customer VARCHAR, status VARCHAR, total FLOAT"
    question2 = "Show all completed orders with total above 1000"
    result2   = sql_generator.generate_sql(question2, schema2, "orders")
    print(f"\n[Test 2]\nQ  : {question2}\nSQL: {result2}")

    print("\n✅ Done.")