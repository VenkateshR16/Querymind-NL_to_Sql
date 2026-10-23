"""
DuckDB service — handles all dataset loading and SQL execution.
Supports multiple tables, JOIN operations, smart column matching,
query caching, data profiling, and advanced chart detection.
"""
import duckdb
import os
import logging
import time
import re
import hashlib
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Column classification keywords ────────────────────────────────────────────
ID_KEYWORDS      = ['id', 'key', 'code', 'ref', 'uuid', 'no', 'num',
                    'number', 'pk', 'fk', 'serial', 'identifier']
NUMERIC_TYPES    = {'INTEGER','INT','DOUBLE','FLOAT','BIGINT','DECIMAL',
                    'HUGEINT','SMALLINT','TINYINT','REAL','NUMERIC',
                    'FLOAT4','FLOAT8','INT2','INT4','INT8','MONEY'}
CATEGORICAL_TYPES = {'VARCHAR','TEXT','CHAR','STRING','NVARCHAR',
                     'NCHAR','ENUM','CATEGORY'}
DATE_TYPES       = {'DATE','DATETIME','TIMESTAMP','TIME','INTERVAL',
                    'TIMESTAMPTZ','TIMETZ'}


class DuckDBService:
    def __init__(self):
        self.conn           = duckdb.connect(database=':memory:')
        self.loaded_tables: Dict[str, dict] = {}
        self._query_cache:  Dict[str, Any]  = {}   # sql_hash → result
        self._cache_limit   = 50                    # max cached queries

    # ══════════════════════════════════════════════════════════════════════════
    # CSV Loading
    # ══════════════════════════════════════════════════════════════════════════

    def load_csv(self, filepath: str, table_name: str) -> dict:
        safe_name = self._safe_name(table_name)
        try:
            # Try strict CSV first, fall back to lenient mode
            try:
                self.conn.execute(f"""
                    CREATE OR REPLACE TABLE {safe_name} AS
                    SELECT * FROM read_csv('{filepath}',
                        header=true,
                        auto_detect=true,
                        ignore_errors=true,
                        null_padding=true)
                """)
            except Exception:
                self.conn.execute(f"""
                    CREATE OR REPLACE TABLE {safe_name} AS
                    SELECT * FROM read_csv_auto('{filepath}')
                """)

            schema    = self.get_schema(safe_name)
            row_count = self.conn.execute(
                f"SELECT COUNT(*) FROM {safe_name}"
            ).fetchone()[0]
            col_stats = self.get_column_stats(safe_name)
            schema_list = self.get_schema_list(safe_name)

            self.loaded_tables[safe_name] = {
                "filepath":   filepath,
                "row_count":  row_count,
                "col_count":  len(schema_list),
                "schema":     schema,
                "schema_list": schema_list,
            }

            # Invalidate cache for any queries on this table
            self._evict_cache_for(safe_name)

            return {
                "success":    True,
                "table_name": safe_name,
                "schema":     schema,
                "schema_list": schema_list,
                "row_count":  row_count,
                "col_count":  len(schema_list),
                "stats":      col_stats,
                "preview":    self._get_preview(safe_name),
                "null_counts": self._get_null_counts(safe_name),
                "sample_values": self._get_sample_values(safe_name),
            }
        except Exception as e:
            logger.error(f"CSV load error for '{filepath}': {e}")
            return {"success": False, "error": str(e)}

    # ══════════════════════════════════════════════════════════════════════════
    # Schema helpers
    # ══════════════════════════════════════════════════════════════════════════

    def get_schema(self, table_name: str) -> str:
        """Return schema as a comma-separated string: col (TYPE), ..."""
        result = self.conn.execute(f"DESCRIBE {table_name}").fetchdf()
        return ", ".join([
            f"{row['column_name']} ({row['column_type']})"
            for _, row in result.iterrows()
        ])

    def get_schema_list(self, table_name: str) -> List[dict]:
        """Return schema as list of {name, type} dicts."""
        result = self.conn.execute(f"DESCRIBE {table_name}").fetchdf()
        return [
            {"name": row['column_name'], "type": row['column_type']}
            for _, row in result.iterrows()
        ]

    def get_multi_schema(self, table_names: list) -> str:
        """Combined schema string for multiple tables."""
        parts = []
        for t in table_names:
            try:
                schema = self.get_schema(t)
                parts.append(f"Table '{t}': {schema}")
            except Exception:
                pass
        return " | ".join(parts)

    # ══════════════════════════════════════════════════════════════════════════
    # Common column detection  (UPGRADED)
    # ══════════════════════════════════════════════════════════════════════════

    def get_common_columns(self, table1: str, table2: str) -> list:
        """
        Find columns shared by both tables, scored by:
          1. ID/key naming convention  (+10)
          2. Identical data type       (+5)
          3. 'id' substring            (+3)
          4. Non-null value presence   (required — skips null-only columns)
        Returns list sorted best-first.
        """
        try:
            df1 = self.conn.execute(f"DESCRIBE {table1}").fetchdf()
            df2 = self.conn.execute(f"DESCRIBE {table2}").fetchdf()

            cols1 = {row['column_name']: row['column_type']
                     for _, row in df1.iterrows()}
            cols2 = {row['column_name']: row['column_type']
                     for _, row in df2.iterrows()}

            common = set(cols1.keys()) & set(cols2.keys())
            if not common:
                return []

            # Verify each common column has non-null data in BOTH tables
            verified = []
            for col in common:
                try:
                    r1 = self.conn.execute(
                        f"SELECT COUNT(*) FROM {table1} "
                        f"WHERE {col} IS NOT NULL LIMIT 1"
                    ).fetchone()[0]
                    r2 = self.conn.execute(
                        f"SELECT COUNT(*) FROM {table2} "
                        f"WHERE {col} IS NOT NULL LIMIT 1"
                    ).fetchone()[0]
                    if r1 > 0 and r2 > 0:
                        verified.append(col)
                except Exception:
                    pass

            if not verified:
                return []

            def score(col: str) -> int:
                c  = col.lower()
                s  = 0
                # ID/key naming
                if any(c == k or c.endswith('_' + k) or c.startswith(k + '_')
                       for k in ID_KEYWORDS):
                    s += 10
                # Same type in both tables
                if cols1[col].upper() == cols2[col].upper():
                    s += 5
                # 'id' substring
                if 'id' in c:
                    s += 3
                return s

            return sorted(verified, key=score, reverse=True)

        except Exception as e:
            logger.error(f"get_common_columns error: {e}")
            return []

    # ══════════════════════════════════════════════════════════════════════════
    # Column statistics
    # ══════════════════════════════════════════════════════════════════════════

    def get_column_stats(self, table_name: str) -> List[dict]:
        schema_df = self.conn.execute(f"DESCRIBE {table_name}").fetchdf()
        stats = []
        for _, row in schema_df.iterrows():
            col   = row['column_name']
            dtype = row['column_type']
            entry = {"column": col, "type": dtype}
            base_type = re.sub(r'\(.*\)', '', dtype).upper()
            try:
                if base_type in NUMERIC_TYPES:
                    s = self.conn.execute(
                        f"SELECT MIN({col}), MAX({col}), "
                        f"ROUND(AVG({col})::DOUBLE, 2), "
                        f"COUNT(DISTINCT {col}), "
                        f"COUNT(*) - COUNT({col}) "
                        f"FROM {table_name}"
                    ).fetchone()
                    entry.update({
                        "min":      s[0],
                        "max":      s[1],
                        "avg":      s[2],
                        "distinct": s[3],
                        "nulls":    s[4],
                    })
                elif base_type in DATE_TYPES:
                    s = self.conn.execute(
                        f"SELECT MIN({col}), MAX({col}), "
                        f"COUNT(DISTINCT {col}), "
                        f"COUNT(*) - COUNT({col}) "
                        f"FROM {table_name}"
                    ).fetchone()
                    entry.update({
                        "min":      str(s[0]),
                        "max":      str(s[1]),
                        "distinct": s[2],
                        "nulls":    s[3],
                    })
                else:
                    s = self.conn.execute(
                        f"SELECT COUNT(DISTINCT {col}), "
                        f"COUNT(*) - COUNT({col}) "
                        f"FROM {table_name}"
                    ).fetchone()
                    entry.update({"distinct": s[0], "nulls": s[1]})

                    # Top 5 most frequent values for categorical columns
                    top = self.conn.execute(
                        f"SELECT {col}, COUNT(*) AS cnt "
                        f"FROM {table_name} "
                        f"WHERE {col} IS NOT NULL "
                        f"GROUP BY {col} ORDER BY cnt DESC LIMIT 5"
                    ).fetchdf()
                    entry["top_values"] = top[col].tolist()

            except Exception as ex:
                logger.debug(f"Stats error for {col}: {ex}")
            stats.append(entry)
        return stats

    # ══════════════════════════════════════════════════════════════════════════
    # Query execution  (with cache)
    # ══════════════════════════════════════════════════════════════════════════

    def execute_query(self, sql: str) -> Dict[str, Any]:
        start = time.time()

        # Check cache
        cache_key = hashlib.md5(sql.strip().upper().encode()).hexdigest()
        if cache_key in self._query_cache:
            cached = dict(self._query_cache[cache_key])
            cached['from_cache'] = True
            cached['elapsed_ms'] = 0
            return cached

        try:
            df         = self.conn.execute(sql).fetchdf()
            elapsed_ms = round((time.time() - start) * 1000, 1)
            columns    = list(df.columns)
            rows       = df.to_dict(orient='records')
            chart_hint = self._suggest_chart(df)

            result = {
                "success":    True,
                "columns":    columns,
                "rows":       rows,
                "row_count":  len(rows),
                "col_count":  len(columns),
                "elapsed_ms": elapsed_ms,
                "chart_hint": chart_hint,
                "from_cache": False,
                "dataframe":  df,
            }

            # Cache (evict oldest if full)
            if len(self._query_cache) >= self._cache_limit:
                oldest = next(iter(self._query_cache))
                del self._query_cache[oldest]
            # Don't cache result with dataframe (too heavy); store light copy
            light = {k: v for k, v in result.items() if k != 'dataframe'}
            self._query_cache[cache_key] = light

            return result

        except Exception as e:
            elapsed_ms = round((time.time() - start) * 1000, 1)
            logger.error(f"Query error: {e}")
            return {
                "success":    False,
                "error":      str(e),
                "elapsed_ms": elapsed_ms,
            }

    # ══════════════════════════════════════════════════════════════════════════
    # Chart suggestion  (UPGRADED)
    # ══════════════════════════════════════════════════════════════════════════

    def _suggest_chart(self, df) -> dict:
        if df is None or df.empty:
            return {"type": "none"}

        cols    = list(df.columns)
        dtypes  = df.dtypes

        numeric_cols     = [c for c in cols
                            if str(dtypes[c]) in
                            {'int64','float64','int32','float32',
                             'Int64','Float64','int16','float16'}]
        categorical_cols = [c for c in cols
                            if str(dtypes[c]) in
                            {'object','string','category','bool'}]
        date_cols        = [c for c in cols
                            if any(k in c.lower()
                                   for k in ['date','time','year',
                                             'month','period','week',
                                             'quarter','day'])]

        n_rows = len(df)

        # Time series → line chart
        if date_cols and numeric_cols:
            return {"type": "line",
                    "x":    date_cols[0],
                    "y":    numeric_cols[0],
                    "all_y": numeric_cols}

        # Single category + single numeric
        if len(categorical_cols) >= 1 and len(numeric_cols) >= 1:
            cat = categorical_cols[0]
            num = numeric_cols[0]
            # Pie for small cardinality
            if n_rows <= 6:
                return {"type": "pie", "label": cat, "value": num}
            # Horizontal bar for many categories
            if n_rows > 15:
                return {"type": "bar_horizontal", "x": num, "y": cat,
                        "all_y": numeric_cols}
            return {"type": "bar", "x": cat, "y": num,
                    "all_y": numeric_cols}

        # Two numerics → scatter
        if len(numeric_cols) >= 2:
            return {"type": "scatter",
                    "x":    numeric_cols[0],
                    "y":    numeric_cols[1],
                    "all_y": numeric_cols}

        # Single numeric column → histogram-style bar
        if len(numeric_cols) == 1:
            x_col = categorical_cols[0] if categorical_cols else cols[0]
            return {"type": "bar", "x": x_col, "y": numeric_cols[0]}

        # Multiple numeric columns → grouped bar
        if len(numeric_cols) > 2 and categorical_cols:
            return {"type": "grouped_bar",
                    "x":    categorical_cols[0],
                    "y":    numeric_cols[0],
                    "all_y": numeric_cols}

        return {"type": "table"}

    # ══════════════════════════════════════════════════════════════════════════
    # Data profiling helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _get_preview(self, table_name: str, n: int = 5) -> list:
        try:
            df = self.conn.execute(
                f"SELECT * FROM {table_name} LIMIT {n}"
            ).fetchdf()
            return df.to_dict(orient='records')
        except Exception:
            return []

    def _get_null_counts(self, table_name: str) -> dict:
        """Return {col: null_count} for every column."""
        try:
            schema_df = self.conn.execute(
                f"DESCRIBE {table_name}"
            ).fetchdf()
            cols  = list(schema_df['column_name'])
            exprs = [f"COUNT(*) - COUNT({c}) AS {c}" for c in cols]
            row   = self.conn.execute(
                f"SELECT {', '.join(exprs)} FROM {table_name}"
            ).fetchone()
            return dict(zip(cols, row))
        except Exception:
            return {}

    def _get_sample_values(self, table_name: str, n: int = 3) -> dict:
        """Return {col: [sample1, sample2, ...]} for every column."""
        try:
            schema_df = self.conn.execute(
                f"DESCRIBE {table_name}"
            ).fetchdf()
            cols   = list(schema_df['column_name'])
            result = {}
            for col in cols:
                try:
                    rows = self.conn.execute(
                        f"SELECT DISTINCT {col} FROM {table_name} "
                        f"WHERE {col} IS NOT NULL LIMIT {n}"
                    ).fetchdf()
                    result[col] = rows[col].tolist()
                except Exception:
                    result[col] = []
            return result
        except Exception:
            return {}

    def get_data_quality_report(self, table_name: str) -> dict:
        """
        Returns a comprehensive data quality report:
        total rows, null %, duplicate rows, column-level issues.
        """
        try:
            total = self.conn.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()[0]
            dupes = self.conn.execute(
                f"SELECT COUNT(*) - COUNT(*) OVER () FROM "
                f"(SELECT *, ROW_NUMBER() OVER () AS rn FROM {table_name}) t "
                f"WHERE rn > 1"
            ).fetchone()
            dup_count = 0
            try:
                dup_count = self.conn.execute(
                    f"SELECT COUNT(*) FROM {table_name} "
                    f"GROUP BY * HAVING COUNT(*) > 1"
                ).fetchdf().shape[0]
            except Exception:
                pass

            null_counts = self._get_null_counts(table_name)
            issues = []
            for col, nulls in null_counts.items():
                pct = round(nulls / total * 100, 1) if total > 0 else 0
                if pct > 0:
                    issues.append({
                        "column":    col,
                        "null_count": nulls,
                        "null_pct":  pct,
                    })

            return {
                "table":        table_name,
                "total_rows":   total,
                "duplicate_rows": dup_count,
                "null_issues":  issues,
                "quality_score": self._quality_score(total, dup_count, issues),
            }
        except Exception as e:
            logger.error(f"Data quality report error: {e}")
            return {}

    def _quality_score(self, total: int,
                       dupes: int, issues: list) -> int:
        """0–100 quality score."""
        score = 100
        if total == 0:
            return 0
        # Penalise duplicates
        score -= min(20, round(dupes / total * 100))
        # Penalise nulls
        for issue in issues:
            score -= min(5, round(issue['null_pct'] / 10))
        return max(0, score)

    # ══════════════════════════════════════════════════════════════════════════
    # Table management
    # ══════════════════════════════════════════════════════════════════════════

    def get_tables(self) -> List[str]:
        return list(self.loaded_tables.keys())

    def get_table_info(self, table_name: str) -> Optional[dict]:
        return self.loaded_tables.get(table_name)

    def drop_table(self, table_name: str) -> bool:
        """Remove a table from DuckDB and the registry."""
        try:
            self.conn.execute(f"DROP TABLE IF EXISTS {table_name}")
            self.loaded_tables.pop(table_name, None)
            self._evict_cache_for(table_name)
            return True
        except Exception as e:
            logger.error(f"Drop table error: {e}")
            return False

    def rename_table(self, old_name: str, new_name: str) -> bool:
        """Rename a loaded table."""
        try:
            safe_new = self._safe_name(new_name)
            self.conn.execute(
                f"ALTER TABLE {old_name} RENAME TO {safe_new}"
            )
            info = self.loaded_tables.pop(old_name, {})
            self.loaded_tables[safe_new] = info
            return True
        except Exception as e:
            logger.error(f"Rename table error: {e}")
            return False

    def reload_table(self, table_name: str) -> dict:
        """Reload a table from its original filepath."""
        info = self.loaded_tables.get(table_name)
        if not info:
            return {"success": False, "error": "Table not found"}
        return self.load_csv(info['filepath'], table_name)

    # ══════════════════════════════════════════════════════════════════════════
    # Query cache helpers
    # ══════════════════════════════════════════════════════════════════════════

    def clear_cache(self):
        self._query_cache.clear()

    def _evict_cache_for(self, table_name: str):
        """Remove cached results that reference a specific table."""
        to_delete = [k for k, v in self._query_cache.items()
                     if table_name.lower() in str(v).lower()]
        for k in to_delete:
            del self._query_cache[k]

    # ══════════════════════════════════════════════════════════════════════════
    # Utility
    # ══════════════════════════════════════════════════════════════════════════

    def _safe_name(self, name: str) -> str:
        name = os.path.splitext(os.path.basename(name))[0]
        name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        if name and name[0].isdigit():
            name = 't_' + name
        return name.lower()[:50] if name else 'table'

    def table_exists(self, table_name: str) -> bool:
        return table_name in self.loaded_tables

    def get_row_count(self, table_name: str) -> int:
        try:
            return self.conn.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()[0]
        except Exception:
            return 0

    def run_explain(self, sql: str) -> str:
        """Return EXPLAIN output for a query (dry-run, no data read)."""
        try:
            result = self.conn.execute(f"EXPLAIN {sql}").fetchdf()
            return result.to_string()
        except Exception as e:
            return str(e)

    def export_to_csv(self, sql: str, filepath: str) -> bool:
        """Execute query and write results to a CSV file."""
        try:
            self.conn.execute(
                f"COPY ({sql}) TO '{filepath}' (HEADER, DELIMITER ',')"
            )
            return True
        except Exception as e:
            logger.error(f"Export CSV error: {e}")
            return False


# ── Singleton ──────────────────────────────────────────────────────────────────
db_service = DuckDBService()