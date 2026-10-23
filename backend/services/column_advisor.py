"""
Intelligent column recommendation engine.
Uses keyword matching + semantic similarity to suggest relevant columns.
"""
import re, logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# Intent keywords → column patterns
INTENT_MAP = {
    'time':     ['date','time','year','month','day','created','updated','timestamp','period'],
    'location': ['country','city','region','state','province','location','area','zip','postal'],
    'finance':  ['price','amount','revenue','sales','cost','profit','margin','value','fee','total'],
    'count':    ['count','qty','quantity','num','number','total','volume'],
    'identity': ['id','name','code','key','sku','uuid','ref','reference'],
    'category': ['type','category','status','class','group','segment','tag','label'],
    'person':   ['name','first_name','last_name','email','user','customer','employee','contact'],
}

class ColumnAdvisor:
    def __init__(self):
        self.embedder = None
        self._load_embedder()

    def _load_embedder(self):
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
            self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
            self.np = np
            logger.info("✅ Column advisor embedder loaded")
        except Exception as e:
            logger.warning(f"⚠️  Embedder not available: {e}. Using keyword matching.")

    def recommend(self, question: str, columns: List[Dict]) -> List[Dict]:
        """
        Returns columns sorted by relevance to the question.
        Each entry: {name, type, score, reason}
        """
        question_lower = question.lower()
        scored = []

        for col in columns:
            col_name = col['name'].lower()
            col_type = col.get('type', '').upper()
            score = 0
            reasons = []

            # Direct name match in question
            if col_name in question_lower or col_name.replace('_', ' ') in question_lower:
                score += 50
                reasons.append('mentioned in question')

            # Intent-based matching
            for intent, patterns in INTENT_MAP.items():
                if any(p in col_name for p in patterns):
                    if any(kw in question_lower for kw in self._intent_keywords(intent)):
                        score += 30
                        reasons.append(f'{intent} column')

            # Type-based matching for aggregations
            numeric_types = ['INTEGER','DOUBLE','FLOAT','BIGINT','DECIMAL','NUMERIC']
            if any(t in col_type for t in numeric_types):
                if any(w in question_lower for w in ['total','sum','average','avg','max','min','count']):
                    score += 20
                    reasons.append('numeric — good for aggregation')

            # Time columns get boosted for trend questions
            if any(p in col_name for p in ['date','time','year','month']):
                if any(w in question_lower for w in ['trend','over time','monthly','yearly','when','recent']):
                    score += 25
                    reasons.append('time column — good for trends')

            scored.append({
                "name": col['name'],
                "type": col.get('type',''),
                "score": score,
                "reason": ', '.join(reasons) if reasons else 'low relevance'
            })

        # Semantic boost if embedder available
        if self.embedder and scored:
            try:
                col_texts = [f"{c['name']} {c['type']}" for c in columns]
                q_emb = self.embedder.encode([question])
                c_embs = self.embedder.encode(col_texts)
                sims = self.np.dot(q_emb, c_embs.T)[0]
                for i, item in enumerate(scored):
                    item['score'] += float(sims[i]) * 30
            except Exception as e:
                logger.debug(f"Embedding error: {e}")

        scored.sort(key=lambda x: x['score'], reverse=True)
        return scored[:6]  # Top 6

    def _intent_keywords(self, intent: str) -> List[str]:
        kw_map = {
            'time':     ['when','date','time','year','month','period','trend','over'],
            'location': ['where','country','city','region','state','location','area'],
            'finance':  ['revenue','cost','price','amount','profit','sales','earn','spend','total','sum'],
            'count':    ['how many','count','number','quantity','volume','total'],
            'identity': ['which','who','what','id','name','code'],
            'category': ['type','category','status','group','segment','kind'],
            'person':   ['who','customer','user','employee','person','contact','name'],
        }
        return kw_map.get(intent, [])

column_advisor = ColumnAdvisor()
