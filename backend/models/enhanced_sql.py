"""
enhanced_sql.py  —  Rule-based NL→SQL fallback
Used by flan_t5.py when the LLM is unavailable or produces invalid output.

CHANGES:
  - All string value comparisons now use LOWER(col) = 'lowercase value'
    for case-insensitive matching (fixes 'Credit Card' vs 'credit card' etc.)
"""

import re
import logging

logger = logging.getLogger(__name__)

# ── Keyword banks ──────────────────────────────────────────────────────────────

NUMERIC_KW  = ['amount','price','revenue','sales','cost','value',
               'qty','quantity','total','salary','score','age',
               'count','num','number','profit','loss','balance',
               'income','expense','tax','discount','rate','fee',
               'weight','height','distance','speed','marks','grade',
               'budget','spend','spending','payment','paid','charge',
               'earning','wages','bonus','commission','margin','units']

CATEGORY_KW = ['name','region','city','country','type','category',
               'status','class','group','segment','product',
               'department','brand','gender','role','title',
               'description','label','tag','code','id','method',
               'mode','channel','source','medium','platform','plan',
               'tier','level','state','province','zip','email',
               'phone','address','currency','language','color',
               'size','format','flag','indicator','reference']

DATE_KW     = ['date','time','year','month','day','created',
               'updated','timestamp','period','week','quarter',
               'start','end','deadline','due','birth','hired',
               'joined','closed','opened','expired','modified']

NUMERIC_TYPES  = {'INT','INTEGER','FLOAT','DOUBLE','DECIMAL','NUMERIC',
                  'BIGINT','REAL','SMALLINT','TINYINT','MONEY','NUMBER'}
CATEGORY_TYPES = {'VARCHAR','TEXT','CHAR','STRING','NVARCHAR','NCHAR','ENUM'}
DATE_TYPES     = {'DATE','DATETIME','TIMESTAMP','TIME','INTERVAL'}

PAYMENT_METHODS = ['credit card','debit card','cash','paypal','upi','net banking',
                   'bank transfer','wire transfer','cheque','check','wallet',
                   'cryptocurrency','crypto','bitcoin','stripe','apple pay',
                   'google pay','amazon pay','emi','cod','voucher','coupon',
                   'gift card','prepaid','postpaid','subscription','invoice']
GENDERS         = ['male','female','non-binary','other']
STATUS_VALUES   = ['active','inactive','pending','approved','rejected','cancelled',
                   'completed','processing','shipped','delivered','returned',
                   'failed','success','open','closed','draft','archived','new']


class EnhancedSQLGenerator:
    def __init__(self):
        self.model = None
        self.tokenizer = None

    # ── Public API ────────────────────────────────────────────────────────────
    def generate_sql(self, question: str, schema: str, table_name: str) -> str:
        cols, col_types = self._parse_schema(schema)
        ctx = self._build_context(question, cols, col_types, table_name)
        return self._generate(ctx)

    def generate_multi_sql(self, question: str, tables: list, db_service) -> str:
        if len(tables) == 1:
            schema = db_service.get_schema(tables[0])
            return self.generate_sql(question, schema, tables[0])
        return self._multi_table(question, tables, db_service)

    # ── Schema parsing ────────────────────────────────────────────────────────
    def _parse_schema(self, schema: str):
        cols, col_types = [], {}
        for part in schema.split(','):
            parts = part.strip().split()
            if parts:
                col   = parts[0].strip().strip('"').strip('`')
                dtype = parts[1].upper() if len(parts) > 1 else 'TEXT'
                dtype = re.sub(r'\(.*\)', '', dtype)
                cols.append(col)
                col_types[col] = dtype
        return cols, col_types

    # ── Context ───────────────────────────────────────────────────────────────
    def _build_context(self, question, cols, col_types, table_name):
        q = question.lower().strip()
        num_cols  = [c for c in cols if self._is_numeric(c,  col_types)]
        cat_cols  = [c for c in cols if self._is_category(c, col_types)]
        date_cols = [c for c in cols if self._is_date(c,     col_types)]
        mentioned = [c for c in cols
                     if c.lower() in q or c.lower().replace('_', ' ') in q]
        return dict(q=q, raw_q=question, table=table_name,
                    cols=cols, col_types=col_types,
                    num_cols=num_cols, cat_cols=cat_cols, date_cols=date_cols,
                    mentioned=mentioned,
                    m_num=[c for c in mentioned if c in num_cols],
                    m_cat=[c for c in mentioned if c in cat_cols],
                    m_date=[c for c in mentioned if c in date_cols])

    def _is_numeric(self, col, col_types):
        return (any(k in col.lower() for k in NUMERIC_KW) or
                col_types.get(col,'') in NUMERIC_TYPES)

    def _is_category(self, col, col_types):
        return (any(k in col.lower() for k in CATEGORY_KW) or
                col_types.get(col,'') in CATEGORY_TYPES)

    def _is_date(self, col, col_types):
        return (any(k in col.lower() for k in DATE_KW) or
                col_types.get(col,'') in DATE_TYPES)

    def _best(self, ctx, kind='num'):
        lst = ctx[f"m_{kind}"] or ctx[f"{kind}_cols"]
        return lst[0] if lst else None

    # ── WHERE ─────────────────────────────────────────────────────────────────
    def _extract_where(self, ctx):
        q, cols = ctx['q'], ctx['cols']
        num_cols, cat_cols, date_cols = ctx['num_cols'], ctx['cat_cols'], ctx['date_cols']
        col_types = ctx['col_types']
        conditions = []

        # ── Numeric conditions ────────────────────────────────────────────────
        numeric_patterns = [
            (r'(?:more than|greater than|above|over|exceeds?|higher than)\s+(\d+(?:\.\d+)?)', '>'),
            (r'(?:less than|lower than|below|under|fewer than)\s+(\d+(?:\.\d+)?)',            '<'),
            (r'(?:at least|minimum of?|>=)\s+(\d+(?:\.\d+)?)',                                '>='),
            (r'(?:at most|maximum of?|no more than|<=)\s+(\d+(?:\.\d+)?)',                    '<='),
            (r'(?:not equal to|!=|<>)\s+(\d+(?:\.\d+)?)',                                     '!='),
            (r'(?:equal to|equals?\s+exactly|exactly)\s+(\d+(?:\.\d+)?)',                     '='),
        ]
        for pattern, op in numeric_patterns:
            for m in re.finditer(pattern, q):
                threshold = m.group(1)
                context   = q[max(0, m.start()-80):m.end()]
                target    = next((c for c in num_cols
                                  if c.lower() in context
                                  or c.lower().replace('_',' ') in context),
                                 self._best(ctx,'num'))
                if target:
                    cond = f"{target} {op} {threshold}"
                    if cond not in conditions:
                        conditions.append(cond)

        for m in re.finditer(r'between\s+(\d+(?:\.\d+)?)\s+and\s+(\d+(?:\.\d+)?)', q):
            target = self._best(ctx,'num')
            if target:
                conditions.append(f"{target} BETWEEN {m.group(1)} AND {m.group(2)}")

        # ── Date conditions ───────────────────────────────────────────────────
        m = re.search(r'(?:from|since|after)\s+["\']?(\d{4}-\d{2}-\d{2})["\']?'
                      r'(?:\s+(?:to|until|before)\s+["\']?(\d{4}-\d{2}-\d{2})["\']?)?', q)
        if m and date_cols:
            dc = date_cols[0]
            if m.group(2):
                conditions.append(f"{dc} BETWEEN '{m.group(1)}' AND '{m.group(2)}'")
            else:
                conditions.append(f"{dc} >= '{m.group(1)}'")

        m = re.search(r'\b(in\s+)?(20\d{2}|19\d{2})\b', q)
        if m and date_cols:
            conditions.append(f"YEAR({date_cols[0]}) = {m.group(2)}")

        months = {'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,
                  'july':7,'august':8,'september':9,'october':10,'november':11,'december':12}
        for mname, mnum in months.items():
            if mname in q and date_cols:
                conditions.append(f"MONTH({date_cols[0]}) = {mnum}")
                break

        # ── Categorical conditions (FIXED: LOWER() for case-insensitive match) ─
        for c in cat_cols:
            cref    = re.escape(c.lower())
            cref_sp = re.escape(c.lower().replace('_',' '))
            ref     = rf'(?:{cref}|{cref_sp})'

            # col is/equals 'value'
            m = re.search(
                rf'{ref}\s+(?:is|=|equals?|named?|called|like|was|are)\s+'
                rf'["\']?([a-zA-Z0-9 _\-]+?)["\']?'
                rf'(?:\s+(?:and|or|where|having|order|group|limit|$)|\s*$)', q)
            if m:
                val = m.group(1).strip()
                if val and val not in ('not','null','true','false'):
                    conditions.append(f"LOWER({c}) = '{val.lower()}'")
                    continue

            # col contains/like 'value'
            m = re.search(rf'{ref}\s+(?:contains?|includes?|has|like|matches?)\s+["\']?(\w+)["\']?', q)
            if m:
                conditions.append(f"LOWER({c}) LIKE '%{m.group(1).lower()}%'")
                continue

            # col starts with 'value'
            m = re.search(rf'{ref}\s+starts?\s+with\s+["\']?(\w+)["\']?', q)
            if m:
                conditions.append(f"LOWER({c}) LIKE '{m.group(1).lower()}%'")
                continue

            # col ends with 'value'
            m = re.search(rf'{ref}\s+ends?\s+with\s+["\']?(\w+)["\']?', q)
            if m:
                conditions.append(f"LOWER({c}) LIKE '%{m.group(1).lower()}'")
                continue

        # ── IN / NOT IN ───────────────────────────────────────────────────────
        m = re.search(r'(?<!\bnot\b\s)(?:in|from|within)\s+\(([^)]+)\)', q)
        if m:
            items = [f"'{i.strip().lower()}'" if not i.strip().replace('.','').isdigit()
                     else i.strip() for i in m.group(1).split(',')]
            target = self._best(ctx,'cat') or self._best(ctx,'num')
            if target:
                if not self._best(ctx,'num') or target == self._best(ctx,'cat'):
                    conditions.append(f"LOWER({target}) IN ({', '.join(items)})")
                else:
                    conditions.append(f"{target} IN ({', '.join(items)})")

        m = re.search(r'(?:not in|exclude|excluding|except)\s+\(([^)]+)\)', q)
        if m:
            items = [f"'{i.strip().lower()}'" if not i.strip().replace('.','').isdigit()
                     else i.strip() for i in m.group(1).split(',')]
            target = self._best(ctx,'cat') or self._best(ctx,'num')
            if target:
                if not self._best(ctx,'num') or target == self._best(ctx,'cat'):
                    conditions.append(f"LOWER({target}) NOT IN ({', '.join(items)})")
                else:
                    conditions.append(f"{target} NOT IN ({', '.join(items)})")

        # ── NULL checks ───────────────────────────────────────────────────────
        for c in cols:
            cref    = re.escape(c.lower())
            cref_sp = re.escape(c.lower().replace('_',' '))
            ref     = rf'(?:{cref}|{cref_sp})'
            if re.search(rf'{ref}\s+is\s+not\s+null', q):
                conditions.append(f"{c} IS NOT NULL")
            elif re.search(rf'{ref}\s+is\s+null', q):
                conditions.append(f"{c} IS NULL")

        # ── OR conditions for status/type/category ────────────────────────────
        m = re.search(r'(?:status|type|category|region|gender|method|mode|channel)'
                      r'\s+(?:is\s+)?["\']?(\w+)["\']?\s+or\s+["\']?(\w+)["\']?', q)
        if m and cat_cols:
            kw     = q[max(0, m.start()-5):m.start()+20]
            target = next((c for c in cat_cols if c.lower() in kw), cat_cols[0])
            v1     = m.group(1).lower()
            v2     = m.group(2).lower()
            conditions.append(f"LOWER({target}) IN ('{v1}', '{v2}')")

        # ── Implicit value conditions (payment method, gender, status) ────────
        conditions += self._implicit_value_conditions(q, cat_cols, col_types)

        # ── Deduplicate ───────────────────────────────────────────────────────
        seen, unique = set(), []
        for c in conditions:
            key = c.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(c)
        return unique

    def _implicit_value_conditions(self, q, cat_cols, col_types):
        conditions = []

        # Only use columns that are genuinely text/categorical —
        # exclude numeric types and any column ending in _id or named id
        def is_text_col(c):
            dtype = col_types.get(c, 'TEXT')
            if dtype in NUMERIC_TYPES:
                return False
            if c.lower() == 'id' or c.lower().endswith('_id'):
                return False
            return True

        text_cols = [c for c in cat_cols if is_text_col(c)]

        # ── Payment method ────────────────────────────────────────────────────
        pm_col = next((c for c in text_cols if any(k in c.lower() for k in
                       ['method','mode','type','channel','payment','source','medium'])), None)
        if pm_col:
            for pm in sorted(PAYMENT_METHODS, key=len, reverse=True):
                if pm in q:
                    conditions.append(f"LOWER({pm_col}) = '{pm.lower()}'")
                    break

        # ── Gender ────────────────────────────────────────────────────────────
        gender_col = next((c for c in text_cols
                           if 'gender' in c.lower() or 'sex' in c.lower()), None)
        if gender_col:
            for g in GENDERS:
                if re.search(rf'\b{g}\b', q):
                    conditions.append(f"LOWER({gender_col}) = '{g.lower()}'")
                    break

        # ── Status ────────────────────────────────────────────────────────────
        status_col = next((c for c in text_cols
                           if 'status' in c.lower() or 'state' in c.lower()), None)
        if status_col:
            for sv in sorted(STATUS_VALUES, key=len, reverse=True):
                if re.search(rf'\b{re.escape(sv)}\b', q):
                    conditions.append(f"LOWER({status_col}) = '{sv.lower()}'")
                    break

        # ── Preposition-based value detection ─────────────────────────────────
        # e.g. "done through credit card", "paid via UPI", "using wallet"
        prep_pattern = (r'(?:done through|paid through|made through|paid via|paid with|'
                        r'paid by|paid using|via|using|through|with method|with type)\s+'
                        r'([a-zA-Z][a-zA-Z0-9 \-]{1,30}?)(?:\s+and|\s+or|$|[,.])')
        for m in re.finditer(prep_pattern, q):
            val = m.group(1).strip()
            if val and len(val) > 1:
                col = next((c for c in text_cols if any(k in c.lower() for k in
                            ['method','mode','type','channel','payment','source'])), None)
                if col and not any(val.lower() in cond.lower() for cond in conditions):
                    conditions.append(f"LOWER({col}) = '{val.lower()}'")

        return conditions

    # ── HAVING ────────────────────────────────────────────────────────────────
    def _extract_having(self, q, agg_alias):
        patterns = [
            (r'having\s+(?:more than|greater than|above|over)\s+(\d+(?:\.\d+)?)', '>'),
            (r'having\s+(?:less than|below|under)\s+(\d+(?:\.\d+)?)',             '<'),
            (r'having\s+(?:at least)\s+(\d+(?:\.\d+)?)',                          '>='),
            (r'having\s+(?:at most|no more than)\s+(\d+(?:\.\d+)?)',              '<='),
            (r'having\s+(?:equal to|exactly)\s+(\d+(?:\.\d+)?)',                  '='),
            (r'with\s+(?:more than|over)\s+(\d+(?:\.\d+)?)\s+\w+',               '>'),
        ]
        for pattern, op in patterns:
            m = re.search(pattern, q)
            if m:
                return f" HAVING {agg_alias} {op} {m.group(1)}"
        return ""

    # ── ORDER BY ──────────────────────────────────────────────────────────────
    def _extract_order(self, q, cols, default_col=None, default_dir='DESC'):
        direction = default_dir
        if any(w in q for w in ['ascending','asc','lowest first','smallest first','oldest first']):
            direction = 'ASC'
        if any(w in q for w in ['descending','desc','highest first','largest first','newest first']):
            direction = 'DESC'
        m = re.search(r'order(?:ed)?\s+by\s+(\w+)', q)
        if m:
            candidate = m.group(1)
            matched   = next((c for c in cols if c.lower() == candidate), None)
            if matched:
                default_col = matched
        return f" ORDER BY {default_col} {direction}" if default_col else ""

    # ── LIMIT / OFFSET ────────────────────────────────────────────────────────
    def _extract_limit(self, q, default=100):
        m = re.search(r'(?:top|first|limit|show\s+me|get|fetch)\s+(\d+)', q)
        return int(m.group(1)) if m else default

    def _extract_offset(self, q):
        m = re.search(r'(?:skip|offset|starting from|page\s+(\d+))', q)
        if not m:
            return 0
        if 'page' in m.group(0):
            page = int(m.group(1))
            return (page - 1) * self._extract_limit(q)
        m2 = re.search(r'(?:skip|offset)\s+(\d+)', q)
        return int(m2.group(1)) if m2 else 0

    # ── Window functions ──────────────────────────────────────────────────────
    def _detect_window_function(self, q, num_col, cat_col=None, date_col=None):
        partition = f"PARTITION BY {cat_col}" if cat_col else ""
        if re.search(r'\b(?:rank|ranked|ranking)\b', q):
            order_col = num_col or date_col
            direction = 'ASC' if any(w in q for w in ['lowest','smallest','earliest']) else 'DESC'
            fn        = 'DENSE_RANK()' if 'dense' in q or 'consecutive' in q else 'RANK()'
            return f"{fn} OVER ({partition} ORDER BY {order_col} {direction}) AS rank"
        if re.search(r'\brow[_ ]?number\b', q):
            over = f"OVER ({partition} ORDER BY {num_col or date_col})"
            return f"ROW_NUMBER() {over} AS row_num"
        if re.search(r'\b(?:running total|cumulative|cumsum)\b', q):
            over = (f"OVER ({partition} ORDER BY {date_col or num_col} "
                    f"ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)")
            return f"SUM({num_col}) {over} AS running_total"
        if re.search(r'\b(?:lag|previous|prior)\b', q):
            n = 1
            m = re.search(r'lag\s*\(\s*(\d+)\s*\)', q)
            if m: n = int(m.group(1))
            return f"LAG({num_col}, {n}) OVER ({partition} ORDER BY {date_col or num_col}) AS prev_{num_col}"
        if re.search(r'\b(?:lead|next|following)\b', q):
            n = 1
            m = re.search(r'lead\s*\(\s*(\d+)\s*\)', q)
            if m: n = int(m.group(1))
            return f"LEAD({num_col}, {n}) OVER ({partition} ORDER BY {date_col or num_col}) AS next_{num_col}"
        if re.search(r'\bntile\b', q):
            n = 4
            m = re.search(r'ntile\s*\(\s*(\d+)\s*\)', q)
            if m: n = int(m.group(1))
            return f"NTILE({n}) OVER (ORDER BY {num_col} DESC) AS bucket"
        if re.search(r'\bpercentile\b', q):
            return f"PERCENT_RANK() OVER (ORDER BY {num_col}) AS percentile"
        return None

    # ── Main single-table generator ───────────────────────────────────────────
    def _generate(self, ctx):
        q, table = ctx['q'], ctx['table']
        cols, num_cols, cat_cols, date_cols = (ctx['cols'], ctx['num_cols'],
                                               ctx['cat_cols'], ctx['date_cols'])
        if not cols:
            return f"SELECT * FROM {table} LIMIT 100"

        where_conds = self._extract_where(ctx)
        lim    = self._extract_limit(q)
        offset = self._extract_offset(q)
        bn, bc, bd = self._best(ctx,'num'), self._best(ctx,'cat'), self._best(ctx,'date')
        grp  = any(w in q for w in ['by','per','each','group','breakdown','for each','distribution'])
        tgrp = any(w in q for w in ['monthly','yearly','by year','by month','by week',
                                    'by quarter','trend','over time'])

        def wc(extra=None):
            conds = list(where_conds) + (extra or [])
            return f" WHERE {' AND '.join(conds)}" if conds else ""

        def lc():
            s = f" LIMIT {lim}"
            if offset: s += f" OFFSET {offset}"
            return s

        # ── Window functions ──────────────────────────────────────────────────
        wf = self._detect_window_function(q, bn, bc, bd)
        if wf:
            return f"SELECT *, {wf} FROM {table}{wc()} ORDER BY {bn or bd}{lc()}"

        # ── DISTINCT ──────────────────────────────────────────────────────────
        if any(w in q for w in ['distinct','unique','different','all possible']):
            t = bc or (ctx['mentioned'][0] if ctx['mentioned'] else cols[0])
            return f"SELECT DISTINCT {t} FROM {table}{wc()} ORDER BY {t}"

        # ── COUNT ─────────────────────────────────────────────────────────────
        if any(w in q for w in ['how many','count','total number','number of']):
            having = self._extract_having(q,'count')
            if grp and bc:
                order = self._extract_order(q, cols, 'count')
                return f"SELECT {bc}, COUNT(*) AS count FROM {table}{wc()} GROUP BY {bc}{having}{order}"
            return f"SELECT COUNT(*) AS total_count FROM {table}{wc()}"

        # ── SUM ───────────────────────────────────────────────────────────────
        if any(w in q for w in ['total','sum']):
            having = self._extract_having(q, f'total_{bn}') if bn else ''
            if bn and bc and grp:
                order = self._extract_order(q, cols, f'total_{bn}')
                return (f"SELECT {bc}, SUM({bn}) AS total_{bn} FROM {table}"
                        f"{wc()} GROUP BY {bc}{having}{order}")
            if bn and bd and tgrp:
                return (f"SELECT {bd} AS period, SUM({bn}) AS total_{bn} FROM {table}"
                        f"{wc()} GROUP BY {bd} ORDER BY {bd}")
            if bn:
                return f"SELECT SUM({bn}) AS total_{bn} FROM {table}{wc()}"

        # ── AVG ───────────────────────────────────────────────────────────────
        if any(w in q for w in ['average','avg','mean']):
            having = self._extract_having(q, f'avg_{bn}') if bn else ''
            if bn and bc and grp:
                order = self._extract_order(q, cols, f'avg_{bn}')
                return (f"SELECT {bc}, ROUND(AVG({bn}), 2) AS avg_{bn} FROM {table}"
                        f"{wc()} GROUP BY {bc}{having}{order}")
            if bn:
                return f"SELECT ROUND(AVG({bn}), 2) AS avg_{bn} FROM {table}{wc()}"

        # ── MIN + MAX ─────────────────────────────────────────────────────────
        if 'min' in q and 'max' in q and bn:
            return f"SELECT MIN({bn}) AS min_{bn}, MAX({bn}) AS max_{bn} FROM {table}{wc()}"

        # ── MAX ───────────────────────────────────────────────────────────────
        if any(w in q for w in ['maximum','highest','max','largest','top','best','most']):
            if bn:
                n     = lim if any(w in q for w in ['top','best','most']) else 1
                order = self._extract_order(q, cols, bn, 'DESC')
                return f"SELECT * FROM {table}{wc()}{order} LIMIT {n}"

        # ── MIN ───────────────────────────────────────────────────────────────
        if any(w in q for w in ['minimum','lowest','min','smallest','least','bottom']):
            if bn:
                order = self._extract_order(q, cols, bn, 'ASC')
                return f"SELECT * FROM {table}{wc()}{order}{lc()}"

        # ── RANK ──────────────────────────────────────────────────────────────
        if any(w in q for w in ['rank','ranked','ranking']):
            if bn:
                return (f"SELECT *, RANK() OVER (ORDER BY {bn} DESC) AS rank"
                        f" FROM {table}{wc()} ORDER BY rank{lc()}")

        # ── PERCENTAGE ───────────────────────────────────────────────────────
        if any(w in q for w in ['percent','percentage','share','ratio','proportion']):
            if bn and bc:
                return (f"SELECT {bc}, SUM({bn}) AS total_{bn},"
                        f" ROUND(100.0 * SUM({bn}) / SUM(SUM({bn})) OVER (), 2) AS percentage"
                        f" FROM {table}{wc()} GROUP BY {bc} ORDER BY total_{bn} DESC")

        # ── TIME GROUP ────────────────────────────────────────────────────────
        if tgrp and date_cols and bn:
            grp_expr = date_cols[0]
            if   'month'   in q: grp_expr = f"DATE_FORMAT({date_cols[0]}, '%Y-%m')"
            elif 'year'    in q: grp_expr = f"YEAR({date_cols[0]})"
            elif 'week'    in q: grp_expr = f"WEEK({date_cols[0]})"
            elif 'quarter' in q: grp_expr = f"QUARTER({date_cols[0]})"
            return (f"SELECT {grp_expr} AS period, SUM({bn}) AS total_{bn}"
                    f" FROM {table}{wc()} GROUP BY {grp_expr} ORDER BY {grp_expr}")

        # ── GROUP BY ──────────────────────────────────────────────────────────
        if grp:
            having = self._extract_having(q, f'total_{bn}') if bn else ''
            if bc and bn:
                order = self._extract_order(q, cols, f'total_{bn}')
                return (f"SELECT {bc}, COUNT(*) AS count, SUM({bn}) AS total_{bn}"
                        f" FROM {table}{wc()} GROUP BY {bc}{having}{order}")
            if bc:
                having = self._extract_having(q,'count')
                return (f"SELECT {bc}, COUNT(*) AS count FROM {table}"
                        f"{wc()} GROUP BY {bc}{having} ORDER BY count DESC")

        # ── WHERE only ────────────────────────────────────────────────────────
        if where_conds:
            # Only use mentioned columns that are NOT already used as WHERE filters
            where_col_names = set()
            for cond in where_conds:
                m = re.match(r'LOWER\((\w+)\)|(\w+)\s+(?:=|!=|<|>|LIKE|IN|IS|BETWEEN)', cond, re.IGNORECASE)
                if m:
                    where_col_names.add((m.group(1) or m.group(2)).lower())

            # Select mentioned cols that aren't the filter columns, or fallback to *
            select_cols = [c for c in ctx['mentioned'] if c.lower() not in where_col_names]
            if not select_cols:
                select_cols = [c for c in cols if c.lower() not in where_col_names] or ['*']
            sc    = ', '.join(select_cols) if len(select_cols) <= 6 else '*'
            order = self._extract_order(q, cols, bn)
            return f"SELECT {sc} FROM {table} WHERE {' AND '.join(where_conds)}{order}{lc()}"

        # ── Mentioned columns ─────────────────────────────────────────────────
        if ctx['mentioned']:
            sc    = ', '.join(ctx['mentioned']) if len(ctx['mentioned']) <= 6 else '*'
            order = self._extract_order(q, cols)
            return f"SELECT {sc} FROM {table}{order}{lc()}"

        # ── Fallback ──────────────────────────────────────────────────────────
        return f"SELECT * FROM {table}{lc()}"

    # ── Multi-table ────────────────────────────────────────────────────────────
    def _multi_table(self, question, tables, db_service):
        q = question.lower().strip()

        join_type = 'JOIN'
        if re.search(r'\bleft\s+(?:outer\s+)?join\b|all.*from.*left\b', q):   join_type = 'LEFT JOIN'
        elif re.search(r'\bright\s+(?:outer\s+)?join\b', q):                   join_type = 'RIGHT JOIN'
        elif re.search(r'\bfull\s+(?:outer\s+)?join\b', q):                    join_type = 'FULL OUTER JOIN'
        elif re.search(r'\bcross\s+join\b|every combination\b', q):            join_type = 'CROSS JOIN'

        aliases = {t: f"t{i+1}" for i, t in enumerate(tables)}
        table_cols, table_col_types = {}, {}
        for t in tables:
            try:
                df = db_service.conn.execute(f"DESCRIBE {t}").fetchdf()
                table_cols[t]     = list(df['column_name'])
                table_col_types[t] = dict(zip(df['column_name'], df['column_type']))
            except Exception:
                table_cols[t]     = []
                table_col_types[t] = {}

        join_candidates = []
        for i in range(len(tables)):
            for j in range(i+1, len(tables)):
                common = db_service.get_common_columns(tables[i], tables[j])
                if common:
                    join_candidates.append((tables[i], tables[j], common[0]))

        def build_join_clause():
            if join_type == 'CROSS JOIN' or not join_candidates:
                base = f"FROM {tables[0]} AS {aliases[tables[0]]}"
                for t in tables[1:]:
                    base += f"\nCROSS JOIN {t} AS {aliases[t]}"
                return base
            t1, t2, col = join_candidates[0]
            clause = (f"FROM {t1} AS {aliases[t1]}"
                      f"\n{join_type} {t2} AS {aliases[t2]}"
                      f" ON {aliases[t1]}.{col} = {aliases[t2]}.{col}")
            joined = {t1, t2}
            for ta, tb, c in join_candidates[1:]:
                if ta not in joined and tb in joined:
                    clause += f"\n{join_type} {ta} AS {aliases[ta]} ON {aliases[ta]}.{c} = {aliases[tb]}.{c}"
                    joined.add(ta)
                elif tb not in joined and ta in joined:
                    clause += f"\n{join_type} {tb} AS {aliases[tb]} ON {aliases[ta]}.{c} = {aliases[tb]}.{c}"
                    joined.add(tb)
            return clause

        join_clause = build_join_clause()
        all_num, all_cat, all_date = [], [], []
        for t, cols in table_cols.items():
            a      = aliases[t]
            ctypes = table_col_types[t]
            for c in cols:
                qc    = f"{a}.{c}"
                ctype = re.sub(r'\(.*\)', '', ctypes.get(c,'')).upper()
                if any(k in c.lower() for k in NUMERIC_KW)  or ctype in NUMERIC_TYPES:  all_num.append((qc,c,t))
                if any(k in c.lower() for k in CATEGORY_KW) or ctype in CATEGORY_TYPES: all_cat.append((qc,c,t))
                if any(k in c.lower() for k in DATE_KW)     or ctype in DATE_TYPES:      all_date.append((qc,c,t))

        def mentioned(col_list):
            return [(qc,c,t) for qc,c,t in col_list
                    if c.lower() in q or c.lower().replace('_',' ') in q]

        bn  = mentioned(all_num)[0]  if mentioned(all_num)  else (all_num[0]  if all_num  else None)
        bc  = mentioned(all_cat)[0]  if mentioned(all_cat)  else (all_cat[0]  if all_cat  else None)
        bd  = mentioned(all_date)[0] if mentioned(all_date) else (all_date[0] if all_date else None)
        lim = self._extract_limit(q)
        grp = any(w in q for w in ['by','per','each','group','breakdown'])

        if any(w in q for w in ['how many','count','total number']):
            if grp and bc:
                qc,c,t = bc
                return (f"SELECT {qc}, COUNT(*) AS count\n{join_clause}"
                        f"\nGROUP BY {qc}\nORDER BY count DESC")
            return f"SELECT COUNT(*) AS total_count\n{join_clause}"

        if any(w in q for w in ['total','sum']):
            if bn and bc and grp:
                nqc,nc,_ = bn; cqc,cc,_ = bc
                return (f"SELECT {cqc}, SUM({nqc}) AS total_{nc}\n{join_clause}"
                        f"\nGROUP BY {cqc}\nORDER BY total_{nc} DESC")
            if bn:
                nqc,nc,_ = bn
                return f"SELECT SUM({nqc}) AS total_{nc}\n{join_clause}"

        if any(w in q for w in ['average','avg','mean']):
            if bn and bc and grp:
                nqc,nc,_ = bn; cqc,cc,_ = bc
                return (f"SELECT {cqc}, ROUND(AVG({nqc}), 2) AS avg_{nc}\n{join_clause}"
                        f"\nGROUP BY {cqc}\nORDER BY avg_{nc} DESC")
            if bn:
                nqc,nc,_ = bn
                return f"SELECT ROUND(AVG({nqc}), 2) AS avg_{nc}\n{join_clause}"

        if any(w in q for w in ['maximum','highest','max','largest','top','best','most']):
            if bn:
                nqc,nc,_ = bn
                n = lim if any(w in q for w in ['top','best','most']) else 1
                return f"SELECT *\n{join_clause}\nORDER BY {nqc} DESC\nLIMIT {n}"

        if any(w in q for w in ['minimum','lowest','min','smallest','least','bottom']):
            if bn:
                nqc,nc,_ = bn
                return f"SELECT *\n{join_clause}\nORDER BY {nqc} ASC\nLIMIT {lim}"

        if any(w in q for w in ['percent','percentage','share','ratio']):
            if bn and bc:
                nqc,nc,_ = bn; cqc,cc,_ = bc
                return (f"SELECT {cqc}, SUM({nqc}) AS total_{nc},"
                        f" ROUND(100.0 * SUM({nqc}) / SUM(SUM({nqc})) OVER (), 2) AS percentage"
                        f"\n{join_clause}\nGROUP BY {cqc}\nORDER BY total_{nc} DESC")

        if grp:
            if bc and bn:
                cqc,cc,_ = bc; nqc,nc,_ = bn
                return (f"SELECT {cqc}, COUNT(*) AS count, SUM({nqc}) AS total_{nc}"
                        f"\n{join_clause}\nGROUP BY {cqc}\nORDER BY total_{nc} DESC")
            if bc:
                cqc,cc,_ = bc
                return (f"SELECT {cqc}, COUNT(*) AS count\n{join_clause}"
                        f"\nGROUP BY {cqc}\nORDER BY count DESC")

        return f"SELECT *\n{join_clause}\nLIMIT {lim}"
# ══════════════════════════════════════════════════════════════════════════════
# QueryMind Ultimate Generic Rule Engine Extension
# Preserves every method above and extends multi-table recovery.
# ══════════════════════════════════════════════════════════════════════════════

class EnhancedSQLGenerator(EnhancedSQLGenerator):
    """
    Generic schema-driven fallback extension.

    Design goals
    ------------
    * Preserve the original rule engine and its public API.
    * Never hard-code database/table/column names.
    * Work with arbitrary uploaded schemas inside QueryMind's DuckDB runtime.
    * Prefer verified, data-supported relationships over blind same-name joins.
    * Cover projection, filtering, aggregation, grouping, ordering, limits,
      NULL checks, ranges, IN lists and common join requests.
    * Fall back to the original implementation whenever confidence is low.
    """

    _NUMERIC_GROUP = {
        "TINYINT", "SMALLINT", "INTEGER", "INT", "BIGINT", "HUGEINT",
        "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT",
        "REAL", "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC"
    }
    _TEXT_GROUP = {
        "VARCHAR", "TEXT", "CHAR", "STRING", "NVARCHAR", "NCHAR", "ENUM"
    }
    _DATE_GROUP = {
        "DATE", "TIME", "TIMESTAMP", "TIMESTAMPTZ", "DATETIME", "INTERVAL"
    }
    _BOOL_GROUP = {"BOOLEAN", "BOOL"}

    def __init__(self):
        super().__init__()
        self._schema_cache = {}

    # ── Identifier / schema utilities ──────────────────────────────────────

    @staticmethod
    def _qi(name):
        """DuckDB-safe quoted identifier."""
        return '"' + str(name).replace('"', '""') + '"'

    @classmethod
    def _type_group(cls, dtype):
        t = re.sub(r"\(.*?\)", "", str(dtype or "")).upper().strip()
        if t in cls._NUMERIC_GROUP or any(x in t for x in ("INT", "DECIMAL", "NUMERIC", "DOUBLE", "FLOAT", "REAL")):
            return "NUMERIC"
        if t in cls._DATE_GROUP or any(x in t for x in ("DATE", "TIME")):
            return "DATETIME"
        if t in cls._BOOL_GROUP or "BOOL" in t:
            return "BOOLEAN"
        return "TEXT"

    def _describe_table_generic(self, table, db_service):
        """
        Return [{name,type,group}, ...] without assuming column names.
        """
        try:
            df = db_service.conn.execute(
                f"DESCRIBE {self._qi(table)}"
            ).fetchdf()
            rows = []
            for _, r in df.iterrows():
                name = str(r["column_name"])
                dtype = str(r["column_type"])
                rows.append({
                    "name": name,
                    "type": dtype,
                    "group": self._type_group(dtype),
                })
            return rows
        except Exception as exc:
            logger.warning("Generic DESCRIBE failed for %s: %s", table, exc)
            try:
                schema = db_service.get_schema(table)
                cols, types = self._parse_schema(schema)
                return [{
                    "name": c,
                    "type": types.get(c, "TEXT"),
                    "group": self._type_group(types.get(c, "TEXT")),
                } for c in cols]
            except Exception:
                return []

    @staticmethod
    def _name_relation_score(a, b):
        """
        Generic relationship-name score. No table-specific rules.
        """
        x = str(a).lower().strip()
        y = str(b).lower().strip()
        if x == y:
            return 1.00

        xn = re.sub(r"[^a-z0-9]", "", x)
        yn = re.sub(r"[^a-z0-9]", "", y)
        if xn == yn:
            return 0.97

        xb = re.sub(r"(?:_?id|_?key|_?code)$", "", x)
        yb = re.sub(r"(?:_?id|_?key|_?code)$", "", y)

        if x == "id" and y.endswith("_id"):
            return 0.94
        if y == "id" and x.endswith("_id"):
            return 0.94
        if xb and xb == yb and (
            x.endswith(("_id", "_key", "_code")) or
            y.endswith(("_id", "_key", "_code"))
        ):
            return 0.91
        return 0.0

    def _column_uniqueness(self, table, col, db_service):
        try:
            q = (
                f"SELECT COUNT(DISTINCT {self._qi(col)})::DOUBLE / "
                f"NULLIF(COUNT({self._qi(col)}),0) "
                f"FROM {self._qi(table)}"
            )
            val = db_service.conn.execute(q).fetchone()[0]
            return float(val or 0.0)
        except Exception:
            return 0.0

    def _value_overlap(self, ta, ca, tb, cb, db_service):
        """
        Bounded sample overlap keeps relationship discovery practical on
        arbitrary uploaded datasets.
        """
        try:
            q = f"""
            WITH a AS (
                SELECT DISTINCT CAST({self._qi(ca)} AS VARCHAR) AS v
                FROM {self._qi(ta)}
                WHERE {self._qi(ca)} IS NOT NULL
                LIMIT 200
            ),
            b AS (
                SELECT DISTINCT CAST({self._qi(cb)} AS VARCHAR) AS v
                FROM {self._qi(tb)}
                WHERE {self._qi(cb)} IS NOT NULL
                LIMIT 200
            ),
            counts AS (
                SELECT
                    (SELECT COUNT(*) FROM a) AS ac,
                    (SELECT COUNT(*) FROM b) AS bc,
                    (SELECT COUNT(*) FROM a INNER JOIN b USING(v)) AS ov
            )
            SELECT CASE
                WHEN LEAST(ac,bc)=0 THEN 0
                ELSE ov::DOUBLE / LEAST(ac,bc)
            END
            FROM counts
            """
            val = db_service.conn.execute(q).fetchone()[0]
            return float(val or 0.0)
        except Exception:
            return 0.0

    def _discover_relationships_generic(self, tables, db_service):
        """
        Discover one or more candidate JOIN edges by schema + sampled data.
        """
        desc = {t: self._describe_table_generic(t, db_service) for t in tables}
        edges = []

        for i in range(len(tables)):
            for j in range(i + 1, len(tables)):
                ta, tb = tables[i], tables[j]
                best = None

                for ca in desc.get(ta, []):
                    for cb in desc.get(tb, []):
                        ns = self._name_relation_score(ca["name"], cb["name"])
                        if ns <= 0:
                            continue
                        if ca["group"] != cb["group"]:
                            continue

                        overlap = self._value_overlap(
                            ta, ca["name"], tb, cb["name"], db_service
                        )
                        uq = max(
                            self._column_uniqueness(ta, ca["name"], db_service),
                            self._column_uniqueness(tb, cb["name"], db_service),
                        )
                        score = 0.50 * ns + 0.30 * overlap + 0.20 * uq

                        item = {
                            "left_table": ta,
                            "left_col": ca["name"],
                            "right_table": tb,
                            "right_col": cb["name"],
                            "score": score,
                            "overlap": overlap,
                        }
                        if best is None or item["score"] > best["score"]:
                            best = item

                if best and best["score"] >= 0.58:
                    edges.append(best)

        return edges

    def _join_tree_generic(self, tables, db_service):
        """
        Construct a connected join tree. Returns (aliases, from_join_sql, edges)
        or None when relationships are insufficient.
        """
        if not tables:
            return None

        aliases = {t: f"t{i+1}" for i, t in enumerate(tables)}
        if len(tables) == 1:
            return aliases, f"FROM {self._qi(tables[0])} AS {aliases[tables[0]]}", []

        edges = self._discover_relationships_generic(tables, db_service)
        root = tables[0]
        joined = {root}
        remaining = set(tables[1:])
        clauses = [f"FROM {self._qi(root)} AS {aliases[root]}"]
        used = []

        while remaining:
            choice = None
            for edge in sorted(edges, key=lambda e: e["score"], reverse=True):
                lt, rt = edge["left_table"], edge["right_table"]
                if lt in joined and rt in remaining:
                    choice = (edge, lt, rt, edge["left_col"], edge["right_col"])
                    break
                if rt in joined and lt in remaining:
                    choice = (edge, rt, lt, edge["right_col"], edge["left_col"])
                    break

            if not choice:
                return None

            edge, old_t, new_t, old_c, new_c = choice
            clauses.append(
                f"JOIN {self._qi(new_t)} AS {aliases[new_t]} "
                f"ON {aliases[old_t]}.{self._qi(old_c)} = "
                f"{aliases[new_t]}.{self._qi(new_c)}"
            )
            joined.add(new_t)
            remaining.remove(new_t)
            used.append(edge)

        return aliases, "\n".join(clauses), used

    # ── Generic question understanding ─────────────────────────────────────

    def _all_columns_catalog(self, tables, db_service):
        catalog = []
        for t in tables:
            for c in self._describe_table_generic(t, db_service):
                catalog.append((t, c["name"], c["group"], c["type"]))
        return catalog

    @staticmethod
    def _whole_word(text, token):
        return bool(re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(str(token).lower())}(?![A-Za-z0-9_])",
            text.lower()
        ))

    def _resolve_column_reference(self, phrase, catalog, preferred_table=None):
        """
        Resolve a natural-language column mention without hard-coded schemas.
        """
        p = str(phrase).lower().strip().replace(" ", "_")
        candidates = []
        for t, c, group, dtype in catalog:
            cn = c.lower()
            score = 0.0
            if p == cn:
                score = 1.0
            elif p.replace("_", "") == cn.replace("_", ""):
                score = 0.96
            elif p in cn or cn in p:
                score = 0.70
            if preferred_table and t.lower() == preferred_table.lower():
                score += 0.10
            if score:
                candidates.append((score, t, c, group, dtype))
        if not candidates:
            return None
        return max(candidates, key=lambda x: x[0])[1:]

    def _projection_generic(self, question, tables, aliases, db_service):
        q = question.lower()
        catalog = self._all_columns_catalog(tables, db_service)

        if any(p in q for p in (
            "all data", "all records", "all rows", "everything",
            "all columns", "complete data", "entire data",
            "records from both", "data from both",
            "records from all", "data from all",
        )):
            return [f"{aliases[t]}.*" for t in tables]

        picked = []
        seen = set()

        # Explicit table-qualified natural language wins for duplicate columns.
        for t in tables:
            for _, c, _, _ in [x for x in catalog if x[0] == t]:
                patterns = (
                    rf"\b{re.escape(t.lower())}\s*\.\s*{re.escape(c.lower())}\b",
                    rf"\b{re.escape(c.lower())}\b[^.;]{{0,80}}\bfrom\s+{re.escape(t.lower())}\b",
                    rf"\b{re.escape(t.lower())}\b[^.;]{{0,80}}\b{re.escape(c.lower())}\b",
                )
                if any(re.search(p, q) for p in patterns):
                    key = (t.lower(), c.lower())
                    if key not in seen:
                        picked.append(f"{aliases[t]}.{self._qi(c)}")
                        seen.add(key)

        # Globally unique column mentions.
        owners = {}
        for t, c, group, dtype in catalog:
            owners.setdefault(c.lower(), []).append((t, c))

        for c_lower, os in owners.items():
            if self._whole_word(q, c_lower):
                if len(os) == 1:
                    t, c = os[0]
                    key = (t.lower(), c.lower())
                    if key not in seen:
                        picked.append(f"{aliases[t]}.{self._qi(c)}")
                        seen.add(key)

        return picked

    def _numeric_conditions_generic(self, question, catalog, aliases):
        q = question.lower()
        conditions = []

        patterns = [
            (r"([a-zA-Z_][\w ]{0,40}?)\s+(?:greater than|more than|above|over)\s+(-?\d+(?:\.\d+)?)", ">"),
            (r"([a-zA-Z_][\w ]{0,40}?)\s+(?:less than|below|under)\s+(-?\d+(?:\.\d+)?)", "<"),
            (r"([a-zA-Z_][\w ]{0,40}?)\s+(?:at least|minimum of)\s+(-?\d+(?:\.\d+)?)", ">="),
            (r"([a-zA-Z_][\w ]{0,40}?)\s+(?:at most|no more than|maximum of)\s+(-?\d+(?:\.\d+)?)", "<="),
            (r"([a-zA-Z_][\w ]{0,40}?)\s+(?:equals?|equal to|is exactly)\s+(-?\d+(?:\.\d+)?)", "="),
            (r"([a-zA-Z_][\w ]{0,40}?)\s+(?:not equal to|is not)\s+(-?\d+(?:\.\d+)?)", "!="),
        ]

        for pat, op in patterns:
            for m in re.finditer(pat, q):
                words = m.group(1).strip().split()
                candidate = None
                for width in range(min(4, len(words)), 0, -1):
                    candidate = self._resolve_column_reference(
                        " ".join(words[-width:]), catalog
                    )
                    if candidate and candidate[2] == "NUMERIC":
                        break
                    candidate = None
                if candidate:
                    t, c, _, _ = candidate
                    conditions.append(
                        f"{aliases[t]}.{self._qi(c)} {op} {m.group(2)}"
                    )

        # BETWEEN <num> AND <num> near a numeric column.
        for t, c, group, _ in catalog:
            if group != "NUMERIC":
                continue
            cre = re.escape(c.lower().replace("_", r"[_ ]"))
            m = re.search(
                rf"{cre}.{{0,20}}\bbetween\s+(-?\d+(?:\.\d+)?)\s+and\s+(-?\d+(?:\.\d+)?)",
                q
            )
            if m:
                conditions.append(
                    f"{aliases[t]}.{self._qi(c)} BETWEEN {m.group(1)} AND {m.group(2)}"
                )

        return conditions

    def _text_conditions_generic(self, question, catalog, aliases):
        q = question.lower()
        conditions = []

        for t, c, group, _ in catalog:
            if group not in ("TEXT", "BOOLEAN"):
                continue

            cref = re.escape(c.lower().replace("_", " "))
            cref2 = re.escape(c.lower())

            eq = re.search(
                rf"(?:{cref}|{cref2})\s+(?:is|equals?|=|named|called)\s+"
                r"['\"]?([a-zA-Z0-9 _\-./@]+?)['\"]?"
                r"(?=\s+(?:and|or|order|group|limit|having|where)\b|$|[,.;])",
                q
            )
            if eq:
                val = eq.group(1).strip().replace("'", "''")
                if val:
                    conditions.append(
                        f"LOWER(CAST({aliases[t]}.{self._qi(c)} AS VARCHAR)) = "
                        f"'{val.lower()}'"
                    )
                    continue

            contains = re.search(
                rf"(?:{cref}|{cref2})\s+(?:contains?|includes?|like)\s+"
                r"['\"]?([a-zA-Z0-9 _\-./@]+?)['\"]?(?=$|[,.;])",
                q
            )
            if contains:
                val = contains.group(1).strip().replace("'", "''")
                conditions.append(
                    f"LOWER(CAST({aliases[t]}.{self._qi(c)} AS VARCHAR)) "
                    f"LIKE '%{val.lower()}%'"
                )

        return conditions

    def _null_conditions_generic(self, question, catalog, aliases):
        q = question.lower()
        out = []
        for t, c, _, _ in catalog:
            variants = (c.lower(), c.lower().replace("_", " "))
            for v in variants:
                if f"{v} is not null" in q or f"{v} not null" in q:
                    out.append(f"{aliases[t]}.{self._qi(c)} IS NOT NULL")
                    break
                if f"{v} is null" in q or f"{v} missing" in q:
                    out.append(f"{aliases[t]}.{self._qi(c)} IS NULL")
                    break
        return out

    def _group_column_generic(self, question, catalog, aliases):
        q = question.lower()
        m = re.search(
            r"(?:group(?:ed)?\s+by|by|per|for each|each)\s+"
            r"([a-zA-Z_][a-zA-Z0-9_ ]{0,60})",
            q
        )
        if not m:
            return None

        phrase = re.split(
            r"\b(?:where|having|order|limit|with|whose|that)\b",
            m.group(1)
        )[0].strip()
        words = phrase.split()

        for width in range(min(5, len(words)), 0, -1):
            ref = self._resolve_column_reference(
                " ".join(words[:width]), catalog
            )
            if ref:
                t, c, _, _ = ref
                return f"{aliases[t]}.{self._qi(c)}"
        return None

    def _metric_column_generic(self, question, catalog, aliases):
        q = question.lower()
        numerical = [x for x in catalog if x[2] == "NUMERIC"]
        mentioned = [
            x for x in numerical
            if self._whole_word(q, x[1]) or
               self._whole_word(q, x[1].replace("_", " "))
        ]
        pool = mentioned or numerical
        if not pool:
            return None
        t, c, _, _ = pool[0]
        return f"{aliases[t]}.{self._qi(c)}", c

    def _limit_generic(self, question, default=100):
        q = question.lower()
        m = re.search(
            r"\b(?:top|first|limit|fetch|show|get)\s+(\d{1,6})\b",
            q
        )
        n = int(m.group(1)) if m else int(default)
        return max(1, min(n, 10000))

    def _order_generic(self, question, catalog, aliases, fallback=None):
        q = question.lower()
        direction = None
        if any(x in q for x in (
            "descending", "highest first", "largest first",
            "newest first", "descending order"
        )):
            direction = "DESC"
        elif any(x in q for x in (
            "ascending", "lowest first", "smallest first",
            "oldest first", "ascending order"
        )):
            direction = "ASC"

        m = re.search(r"\b(?:order|sort)(?:ed)?\s+by\s+([a-zA-Z_][\w ]{0,50})", q)
        if m:
            phrase = re.split(r"\b(?:asc|desc|ascending|descending|limit)\b", m.group(1))[0]
            ref = self._resolve_column_reference(phrase.strip(), catalog)
            if ref:
                t, c, _, _ = ref
                return f"{aliases[t]}.{self._qi(c)} {direction or 'ASC'}"

        if fallback and direction:
            return f"{fallback} {direction}"
        return None

    def _build_advanced_multi(self, question, tables, db_service):
        tree = self._join_tree_generic(tables, db_service)
        if not tree:
            return None

        aliases, join_clause, _ = tree
        catalog = self._all_columns_catalog(tables, db_service)
        if not catalog:
            return None

        q = question.lower()
        projection = self._projection_generic(
            question, tables, aliases, db_service
        )
        numeric_conds = self._numeric_conditions_generic(
            question, catalog, aliases
        )
        text_conds = self._text_conditions_generic(
            question, catalog, aliases
        )
        null_conds = self._null_conditions_generic(
            question, catalog, aliases
        )
        conditions = []
        seen = set()
        for cond in numeric_conds + text_conds + null_conds:
            k = cond.lower()
            if k not in seen:
                conditions.append(cond)
                seen.add(k)

        group_col = self._group_column_generic(
            question, catalog, aliases
        )
        metric = self._metric_column_generic(
            question, catalog, aliases
        )

        agg = None
        agg_alias = None
        metric_ref = metric[0] if metric else None
        metric_name = metric[1] if metric else "value"

        if any(x in q for x in ("how many", "count", "number of", "total number")):
            agg = "COUNT(*)"
            agg_alias = "count"
        elif any(x in q for x in ("average", "avg", "mean")) and metric_ref:
            agg = f"ROUND(AVG({metric_ref}), 2)"
            agg_alias = f"avg_{metric_name}"
        elif re.search(r"\b(?:sum|total)\b", q) and metric_ref:
            agg = f"SUM({metric_ref})"
            agg_alias = f"total_{metric_name}"
        elif any(x in q for x in ("maximum", "max value")) and metric_ref:
            agg = f"MAX({metric_ref})"
            agg_alias = f"max_{metric_name}"
        elif any(x in q for x in ("minimum", "min value")) and metric_ref:
            agg = f"MIN({metric_ref})"
            agg_alias = f"min_{metric_name}"

        select_parts = []
        if agg:
            if group_col:
                select_parts.append(group_col)
            select_parts.append(f"{agg} AS {self._qi(agg_alias)}")
        elif projection:
            select_parts = projection
        else:
            select_parts = [f"{aliases[t]}.*" for t in tables]

        sql = "SELECT " + ", ".join(select_parts) + "\n" + join_clause

        if conditions:
            sql += "\nWHERE " + " AND ".join(conditions)

        if agg and group_col:
            sql += "\nGROUP BY " + group_col

        # HAVING for common grouped aggregate thresholds.
        if agg and group_col:
            hm = re.search(
                r"\b(?:having|with)\s+(?:more than|greater than|above)\s+"
                r"(-?\d+(?:\.\d+)?)",
                q
            )
            if hm:
                sql += f"\nHAVING {agg} > {hm.group(1)}"
            else:
                hm = re.search(
                    r"\b(?:having|with)\s+(?:less than|below|under)\s+"
                    r"(-?\d+(?:\.\d+)?)",
                    q
                )
                if hm:
                    sql += f"\nHAVING {agg} < {hm.group(1)}"

        order = self._order_generic(
            question, catalog, aliases,
            fallback=self._qi(agg_alias) if agg_alias else metric_ref
        )

        # Natural top/highest/lowest requests.
        if not order and metric_ref:
            if any(x in q for x in ("highest", "largest", "top", "most")):
                order = f"{metric_ref} DESC"
            elif any(x in q for x in ("lowest", "smallest", "bottom", "least")):
                order = f"{metric_ref} ASC"

        if order:
            sql += "\nORDER BY " + order

        # Aggregate-only scalar queries do not need a LIMIT.
        if not agg or group_col:
            sql += f"\nLIMIT {self._limit_generic(question)}"

        return sql

    @staticmethod
    def _explain_ok(sql, db_service):
        if not sql or db_service is None:
            return False
        try:
            db_service.conn.execute(f"EXPLAIN {sql}").fetchall()
            return True
        except Exception as exc:
            logger.warning("Advanced rule SQL rejected by DuckDB: %s", exc)
            return False

    # ── Public multi-table override ────────────────────────────────────────

    def generate_multi_sql(self, question: str, tables: list, db_service) -> str:
        """
        Advanced generic rule-based recovery first; original rule engine second.

        The LLM layer still decides when this fallback is reached. This method
        never replaces the model-first orchestration in flan_t5.py.
        """
        if not tables:
            return "SELECT 1 WHERE FALSE"

        if len(tables) == 1:
            schema = db_service.get_schema(tables[0])
            return self.generate_sql(question, schema, tables[0])

        try:
            sql = self._build_advanced_multi(
                question, tables, db_service
            )
            if sql and self._explain_ok(sql, db_service):
                logger.info("[EnhancedSQL Ultimate] advanced generic SQL accepted")
                return sql
        except Exception as exc:
            logger.warning(
                "[EnhancedSQL Ultimate] advanced path failed: %s", exc
            )

        # Preserve the complete legacy behavior as the final rule fallback.
        return super().generate_multi_sql(
            question, tables, db_service
        )
