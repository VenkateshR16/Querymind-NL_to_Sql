"""
EasyOCR engine for image-to-text query extraction.
Works on Python 3.14+ — no system installation needed.
Handles: bullets, numbering, highlights, UI chrome, digit splits,
         low contrast, background noise, answer labels, watermarks,
         multi-line queries, mixed fonts, screenshotted documents.
"""
import io
import re
import logging
import warnings

logger = logging.getLogger(__name__)

# Suppress EasyOCR/torch pin_memory warning (no GPU)
warnings.filterwarnings("ignore", message=".*pin_memory.*")

# ── UI / document noise words ─────────────────────────────────────────────────
NOISE_WORDS = {
    # Toolbar / menu
    'file', 'edit', 'view', 'help', 'format', 'tools', 'insert',
    'home', 'page', 'layout', 'references', 'mailings', 'review',
    # Heading styles
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'heading', 'subheading', 'title', 'subtitle',
    # Formatting buttons
    'bold', 'italic', 'underline', 'strikethrough', 'superscript',
    'subscript', 'font', 'size', 'color', 'highlight', 'align',
    # File types
    'png', 'jpg', 'jpeg', 'gif', 'svg', 'bmp', 'webp', 'pdf',
    'docx', 'xlsx', 'pptx', 'txt', 'csv', 'tsv', 'json',
    # Dialog buttons
    'ok', 'cancel', 'close', 'save', 'open', 'new', 'print',
    'apply', 'confirm', 'yes', 'no', 'submit', 'reset',
    # Actions
    'upload', 'drag', 'drop', 'browse', 'click', 'tap',
    'copy', 'paste', 'cut', 'undo', 'redo', 'select', 'all',
    # UI elements
    'menu', 'toolbar', 'sidebar', 'tab', 'panel', 'ribbon',
    'window', 'dialog', 'popup', 'modal', 'tooltip', 'button',
    'checkbox', 'radio', 'dropdown', 'scroll', 'resize',
    # App-specific
    'venky', 'querymind', 'analytics', 'intelligent',
    'dataset', 'datasets', 'schema', 'history', 'settings',
    'navigation', 'interface', 'voice', 'sql', 'http', 'localhost',
    # Document labels
    'answer', 'question', 'solution', 'output', 'result', 'results',
    'note', 'notes', 'example', 'examples', 'task', 'tasks',
    'exercise', 'problem', 'assignment', 'homework', 'lab',
    'instructions', 'description', 'objective', 'summary',
    'introduction', 'conclusion', 'reference', 'appendix',
    'figure', 'table', 'chart', 'graph', 'diagram', 'image',
    # Watermarks / headers / footers
    'confidential', 'draft', 'sample', 'preview', 'watermark',
    'copyright', 'reserved', 'rights', 'powered', 'version',
    'page', 'of', 'footer', 'header',
    # Numbers as words that appear as labels
    'one', 'two', 'three', 'four', 'five', 'six', 'seven',
    'eight', 'nine', 'ten',
}

# ── Query intent keywords (boosts scoring) ────────────────────────────────────
QUERY_KEYWORDS = [
    # Request verbs
    'want', 'show', 'get', 'find', 'list', 'give', 'display',
    'fetch', 'retrieve', 'return', 'select', 'print', 'tell',
    'calculate', 'compute', 'determine', 'identify',
    # Aggregations
    'total', 'sum', 'count', 'average', 'avg', 'mean',
    'max', 'maximum', 'min', 'minimum', 'highest', 'lowest',
    'top', 'bottom', 'best', 'worst', 'largest', 'smallest',
    # Filters
    'more', 'less', 'greater', 'between', 'where', 'having',
    'above', 'below', 'equal', 'equals', 'than', 'atleast',
    'atmost', 'exactly', 'not', 'except', 'excluding',
    'contains', 'starts', 'ends', 'like', 'null', 'empty',
    # Grouping / sorting
    'group', 'by', 'per', 'each', 'rank', 'ranked', 'order',
    'sort', 'ascending', 'descending', 'asc', 'desc',
    # Columns (common)
    'sales', 'revenue', 'price', 'amount', 'cost', 'salary',
    'profit', 'loss', 'income', 'expense', 'balance', 'tax',
    'name', 'region', 'city', 'country', 'category', 'product',
    'type', 'status', 'gender', 'department', 'brand', 'age',
    'score', 'rating', 'quantity', 'stock', 'date', 'year',
    'month', 'day', 'time', 'period', 'week', 'quarter',
    # Question words
    'how', 'many', 'much', 'which', 'what', 'who', 'when', 'where',
    # Time
    'monthly', 'yearly', 'weekly', 'daily', 'trend', 'over',
    # Misc
    'unique', 'distinct', 'all', 'with', 'without', 'users',
    'customers', 'employees', 'records', 'rows', 'entries',
    'whose', 'that', 'are', 'have', 'has', 'been',
]


class OCREngine:
    def __init__(self):
        self.available = False
        self.reader    = None
        self._init_ocr()

    # ── Initialization ────────────────────────────────────────────────────────

    def _init_ocr(self):
        try:
            import easyocr
            logger.info("⏳ Loading EasyOCR model (first time ~100MB download)...")
            self.reader    = easyocr.Reader(['en'], gpu=False, verbose=False)
            self.available = True
            logger.info("✅ EasyOCR ready")
        except Exception as e:
            logger.warning(f"⚠️  EasyOCR not available: {e}")

    # ── Image Preprocessing ───────────────────────────────────────────────────

    def _preprocess_image(self, image_bytes: bytes) -> bytes:
        """
        Prepare image for maximum OCR accuracy.
        Pipeline:
          1. Crop 8% margins  → removes toolbars, sidebars
          2. Upscale 2.5x     → prevents digit clipping (30→3 fix)
          3. Grayscale        → removes color distractions
          4. CLAHE-style      → local contrast normalization
          5. Contrast + Sharp → enhance text edges
          6. Binarize         → pure black/white (no blurry edges)
          7. Median filter    → remove salt-and-pepper noise
          8. Deskew           → fix slight rotation
        """
        try:
            from PIL import Image, ImageFilter, ImageEnhance, ImageOps
            img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            w, h = img.size

            # Step 1: Crop margins
            mx = int(w * 0.08)
            my = int(h * 0.08)
            img = img.crop((mx, my, w - mx, h - my))

            # Step 2: Upscale 2.5x (critical for small/thin digits)
            img = img.resize(
                (int(img.width * 2.5), int(img.height * 2.5)),
                Image.LANCZOS
            )

            # Step 3: Grayscale
            img = img.convert('L')

            # Step 4: Auto-equalize histogram (CLAHE-like)
            img = ImageOps.equalize(img)

            # Step 5: Contrast + Sharpness
            img = ImageEnhance.Contrast(img).enhance(2.5)
            img = ImageEnhance.Sharpness(img).enhance(3.0)

            # Step 6: Binarize with Otsu-like adaptive threshold
            # Try multiple thresholds and pick the one with most
            # balanced black/white pixel ratio (text vs background)
            best_img   = img
            best_score = float('inf')
            for thresh in range(100, 200, 15):
                candidate = img.point(lambda p: 255 if p > thresh else 0)
                pixels    = list(candidate.getdata())
                black     = pixels.count(0)
                white     = pixels.count(255)
                total     = len(pixels)
                # Good threshold: text is 5-40% of image
                ratio = black / total
                score = abs(ratio - 0.15)   # target ~15% black (text)
                if score < best_score:
                    best_score = score
                    best_img   = candidate
            img = best_img

            # Step 7: Denoise
            img = img.filter(ImageFilter.MedianFilter(size=3))

            # Step 8: Deskew (correct slight tilt)
            img = self._deskew(img)

            buf = io.BytesIO()
            img.save(buf, format='PNG')
            return buf.getvalue()

        except Exception as e:
            logger.warning(f"Preprocessing failed ({e}), using original")
            return image_bytes

    def _deskew(self, img):
        """Correct slight image rotation using projection profile."""
        try:
            import numpy as np
            data = np.array(img)
            # Invert so text = 1, background = 0
            binary = (data < 128).astype(np.uint8)
            best_angle = 0
            best_score = -1
            for angle in [a * 0.5 for a in range(-10, 11)]:
                from PIL import Image as PILImage
                rotated = PILImage.fromarray(binary * 255).rotate(
                    angle, expand=False, fillcolor=0
                )
                rot_data = np.array(rotated)
                # Score = variance of row sums (sharp rows = correct angle)
                row_sums = rot_data.sum(axis=1)
                score    = float(np.var(row_sums))
                if score > best_score:
                    best_score = score
                    best_angle = angle
            if abs(best_angle) > 0.4:
                img = img.rotate(best_angle, expand=False, fillcolor=255)
        except Exception:
            pass  # deskew is optional
        return img

    # ── Text Cleaning Helpers ─────────────────────────────────────────────────

    def _strip_prefix(self, text: str) -> str:
        """
        Remove leading bullets, numbering, symbols, labels.
        Handles: •, ◆, ▪, -, *, 1., 1), (1), Q1., Q:, Answer:, Note:
        """
        # Unicode bullets and symbols
        text = re.sub(r'^[\s\u2022\u25C6\u25AA\u2023\u2043\u204C'
                      r'\u25CF\u25CB\u2713\u2714\*\-\+\>\~]+', '', text)
        # Numbered list: "1.", "1)", "(1)", "1:"
        text = re.sub(r'^\(?\d+[\.\)\:]\s*', '', text)
        # Lettered list: "a.", "A)", "(a)"
        text = re.sub(r'^\(?[a-zA-Z][\.\)\:]\s*', '', text)
        # Label prefixes: "Q:", "Q1:", "Ans:", "Answer:", "Note:", "Task 1:"
        text = re.sub(
            r'^(?:Q|Que|Question|Ans|Answer|Note|Task|Ex|Example|Problem)'
            r'[\s\d]*[\:\.\)]\s*',
            '', text, flags=re.IGNORECASE
        )
        return text.strip()

    def _is_noise_only(self, text: str) -> bool:
        """True if text contains only noise/UI words."""
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        if not words:
            return True
        return all(w in NOISE_WORDS for w in words)

    def _is_valid_line(self, text: str) -> bool:
        """Basic validity checks before scoring."""
        # Must have at least one real word (3+ chars or a number)
        has_word   = bool(re.search(r'\b[a-zA-Z]{3,}\b', text))
        has_number = bool(re.search(r'\d+', text))
        return has_word or has_number

    # ── Scoring ───────────────────────────────────────────────────────────────

    def _score_line(self, text: str, conf: float) -> float:
        """
        Score a text line by its likelihood of being a natural-language query.
        Higher = more likely to be the user's query.
        """
        tl           = text.lower()
        words        = re.findall(r'\b\w+\b', tl)
        word_count   = len(words)
        noise_count  = sum(1 for w in words if w in NOISE_WORDS)
        keyword_hits = sum(1 for kw in QUERY_KEYWORDS if kw in tl)
        has_number   = bool(re.search(r'\d+', text))
        is_sentence  = word_count >= 4

        # Reject pure noise
        if word_count > 0 and noise_count == word_count:
            return -1.0

        # Penalty if more than half words are noise
        noise_ratio = noise_count / word_count if word_count else 0
        noise_pen   = noise_ratio * 40.0

        return (
            len(text)               * 0.8   +   # longer = better
            keyword_hits            * 30.0  +   # query keywords
            has_number              * 12.0  +   # contains a number
            conf                    * 20.0  +   # OCR confidence
            word_count              * 4.0   +   # more words = sentence
            (15.0 if is_sentence else 0.0)  -   # sentence bonus
            noise_pen                           # noise penalty
        )

    # ── OCR Result Processing ─────────────────────────────────────────────────

    def _clean_ocr_results(self, results: list) -> str:
        """
        From all OCR detections, pick the best natural-language query line.
        Falls back to combining top candidates if best is too short.
        """
        if not results:
            return ""

        scored = []
        for (bbox, text, conf) in results:
            text = text.strip()
            if not text or conf < 0.22:
                continue

            # Strip bullets, numbering, labels
            clean = self._strip_prefix(text)
            if not clean:
                continue

            # Skip very short strays
            if len(clean) <= 2 and not re.search(r'\d{3,}', clean):
                continue

            # Skip pure noise
            if self._is_noise_only(clean):
                logger.info(f"   ❌ noise: '{clean}'")
                continue

            # Skip invalid lines
            if not self._is_valid_line(clean):
                continue

            score = self._score_line(clean, conf)
            logger.info(f"   📊 '{clean}' → score={round(score,1)} conf={round(conf,2)}")

            if score >= 0:
                scored.append((score, clean, conf))

        if not scored:
            return ""

        scored.sort(key=lambda x: x[0], reverse=True)
        best_text = scored[0][1]
        logger.info(f"🏆 Best: '{best_text}'")

        # If best is very short, try combining top lines
        if len(best_text) < 15 and len(scored) > 1:
            seen  = set()
            parts = []
            for _, t, _ in scored[:5]:
                for w in re.findall(r'\b\w+\b', t.lower()):
                    if w not in NOISE_WORDS and w not in seen:
                        seen.add(w)
                        parts.append(w)
            combined = ' '.join(parts)
            if len(combined) > len(best_text):
                best_text = combined
                logger.info(f"🔗 Combined: '{best_text}'")

        return best_text.strip()

    # ── Post-processing ───────────────────────────────────────────────────────

    def _post_process_text(self, text: str) -> str:
        """
        Fix digit splits, misread chars, punctuation, and spacing.
        """
        if not text:
            return text

        # ── Fix digits split by spaces: "3 0" → "30", "1 0 0 0" → "1000" ───
        for _ in range(6):
            text = re.sub(r'(\d)\s+(\d)', r'\1\2', text)

        # ── Remove thousands comma: "2,000" → "2000" ─────────────────────────
        text = re.sub(r'(\d),(\d{3})\b', r'\1\2', text)

        # ── Fix letter↔digit confusions (context-aware) ───────────────────────
        text = re.sub(r'(?<=\d)O(?=\d)',  '0', text)
        text = re.sub(r'(?<=\d)o(?=\d)',  '0', text)
        text = re.sub(r'(?<=\d)l(?=\d)',  '1', text)
        text = re.sub(r'(?<=\d)I(?=\d)',  '1', text)
        text = re.sub(r'(?<=\d)S(?=\d)',  '5', text)
        text = re.sub(r'(?<=\d)s(?=\d)',  '5', text)
        text = re.sub(r'(?<=\d)B(?=\d)',  '8', text)
        text = re.sub(r'(?<=\d)G(?=\d)',  '6', text)
        text = re.sub(r'(?<=\d)Z(?=\d)',  '2', text)
        text = re.sub(r'(?<=\d)z(?=\d)',  '2', text)
        text = re.sub(r'(?<=\d)q(?=\d)',  '9', text)
        text = re.sub(r'(?<=\d)g(?=\d)',  '9', text)

        # ── Fix standalone misread digits at end of numbers ───────────────────
        # e.g. "5O" → "50", "3O" → "30"
        text = re.sub(r'(\d)O\b', r'\g<1>0', text)
        text = re.sub(r'(\d)o\b', r'\g<1>0', text)

        # ── Normalize quotes and punctuation ──────────────────────────────────
        text = re.sub(r'["""]',  '"',  text)
        text = re.sub(r"[''']",  "'",  text)
        text = re.sub(r'\|',     'I',  text)
        text = re.sub(r'`',      "'",  text)

        # ── Remove stray isolated special chars ───────────────────────────────
        text = re.sub(r'(?<!\w)[^a-zA-Z0-9\s><=!%,.()\'"]{1,2}(?!\w)', '', text)

        # ── Collapse multiple spaces ───────────────────────────────────────────
        text = ' '.join(text.split())

        return text.strip()

    # ── Multi-strategy OCR ────────────────────────────────────────────────────

    def _run_ocr_multi_strategy(self, image_bytes: bytes) -> list:
        """
        Run OCR on multiple versions of the image and merge results.
        Strategies: preprocessed, original, inverted, high-contrast crop.
        Deduplicates by normalized text.
        """
        all_results = []
        seen_texts  = set()

        def add_results(results):
            for (bbox, text, conf) in results:
                key = re.sub(r'\s+', '', text.lower().strip())
                if key and key not in seen_texts:
                    seen_texts.add(key)
                    all_results.append((bbox, text, conf))

        # Strategy 1: Preprocessed (primary)
        try:
            processed = self._preprocess_image(image_bytes)
            r1 = self.reader.readtext(processed)
            logger.info(f"🔍 Strategy 1 (preprocessed): {[(t,round(c,2)) for _,t,c in r1]}")
            add_results(r1)
        except Exception as e:
            logger.warning(f"Strategy 1 failed: {e}")

        # Strategy 2: Original image as-is
        try:
            r2 = self.reader.readtext(image_bytes)
            logger.info(f"🔍 Strategy 2 (original): {[(t,round(c,2)) for _,t,c in r2]}")
            add_results(r2)
        except Exception as e:
            logger.warning(f"Strategy 2 failed: {e}")

        # Strategy 3: Inverted colors (white text on dark bg)
        try:
            from PIL import Image, ImageOps
            img = Image.open(io.BytesIO(image_bytes)).convert('L')
            inv = ImageOps.invert(img)
            buf = io.BytesIO()
            inv.save(buf, format='PNG')
            r3  = self.reader.readtext(buf.getvalue())
            logger.info(f"🔍 Strategy 3 (inverted): {[(t,round(c,2)) for _,t,c in r3]}")
            add_results(r3)
        except Exception as e:
            logger.warning(f"Strategy 3 failed: {e}")

        # Strategy 4: Center crop (focus on main content area)
        try:
            from PIL import Image
            img  = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            w, h = img.size
            cx, cy = int(w * 0.15), int(h * 0.15)
            cropped = img.crop((cx, cy, w - cx, h - cy))
            buf = io.BytesIO()
            cropped.save(buf, format='PNG')
            r4  = self.reader.readtext(buf.getvalue())
            logger.info(f"🔍 Strategy 4 (center crop): {[(t,round(c,2)) for _,t,c in r4]}")
            add_results(r4)
        except Exception as e:
            logger.warning(f"Strategy 4 failed: {e}")

        return all_results

    # ── Public API ────────────────────────────────────────────────────────────

    def extract_text(self, image_bytes: bytes) -> dict:
        """
        Main method: extract clean natural-language query from image.
        Returns dict with 'success', 'text', 'char_count' or 'error'.
        """
        if not self.available:
            return {
                "success": False,
                "text":    "",
                "error":   "OCR not available. Run: pip install easyocr pillow"
            }
        try:
            # Multi-strategy OCR
            all_results = self._run_ocr_multi_strategy(image_bytes)

            # Pick best line
            text = self._clean_ocr_results(all_results)

            # Fix digit splits and misreads
            text = self._post_process_text(text)

            if not text:
                return {
                    "success": False,
                    "text":    "",
                    "error":   "No query text detected. Try a clearer or closer image."
                }

            logger.info(f"✅ Final OCR text: '{text}'")
            return {
                "success":    True,
                "text":       text,
                "char_count": len(text)
            }

        except Exception as e:
            logger.error(f"OCR extract_text error: {e}")
            return {"success": False, "text": "", "error": str(e)}

    def extract_text_with_data(self, image_bytes: bytes) -> dict:
        """
        Extended: returns text + per-word confidence + bounding boxes.
        Useful for debugging OCR quality.
        """
        if not self.available:
            return {"success": False, "data": [], "error": "OCR not available"}
        try:
            all_results = self._run_ocr_multi_strategy(image_bytes)

            words = [
                {
                    "text":       text,
                    "confidence": round(conf * 100, 2),
                    "bbox":       bbox
                }
                for (bbox, text, conf) in all_results
                if conf > 0.22
                and text.strip().lower() not in NOISE_WORDS
                and len(text.strip()) > 2
            ]

            full_text = self._post_process_text(
                self._clean_ocr_results(all_results)
            )

            return {
                "success":    True,
                "text":       full_text,
                "words":      words,
                "char_count": len(full_text)
            }

        except Exception as e:
            logger.error(f"OCR extract_text_with_data error: {e}")
            return {"success": False, "data": [], "error": str(e)}


# Singleton — import and use: from ocr import ocr
ocr = OCREngine()