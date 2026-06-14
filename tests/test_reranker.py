import unittest

from enterprise_rag.config import RerankerConfig
from enterprise_rag.models import Document, SearchHit, SourceType
from enterprise_rag.reranker import rerank_hits


class RerankerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = RerankerConfig(
            enabled=True,
            position_weight=0.15,
            coverage_weight=0.20,
            diversity_bonus=0.50, # Set high to guarantee rank change
        )

    def test_reranker_adjusts_scores_based_on_coverage_and_position(self) -> None:
        doc1 = Document(doc_id="d1", title="T1", source_type=SourceType.DOCUMENT, text="", path="", allowed_roles=())
        doc2 = Document(doc_id="d2", title="T2", source_type=SourceType.DOCUMENT, text="", path="", allowed_roles=())
        
        hit1 = SearchHit(document=doc1, score=1.0, reasons=(), snippet="hello world", block_id="block-10")
        hit2 = SearchHit(document=doc2, score=1.0, reasons=(), snippet="hello universe", block_id="block-1")
        
        # hit2 should get a higher position score because block-1 < block-10.
        # Coverage is same (1/1 for 'hello').
        reranked = rerank_hits("hello", [hit1, hit2], self.config)
        
        self.assertEqual(reranked[0].document.doc_id, "d2")
        self.assertGreater(reranked[0].score, reranked[1].score)

    def test_diversity_bonus(self) -> None:
        # Create 3 docs from DOCUMENT source, 1 from CSV source
        doc1 = Document(doc_id="d1", title="T1", source_type=SourceType.DOCUMENT, text="", path="", allowed_roles=())
        doc2 = Document(doc_id="d2", title="T2", source_type=SourceType.DOCUMENT, text="", path="", allowed_roles=())
        doc3 = Document(doc_id="d3", title="T3", source_type=SourceType.DOCUMENT, text="", path="", allowed_roles=())
        doc4 = Document(doc_id="d4", title="T4", source_type=SourceType.CSV, text="", path="", allowed_roles=())
        
        hits = [
            SearchHit(document=doc1, score=2.0, reasons=(), snippet="query", block_id="block-1"),
            SearchHit(document=doc2, score=1.9, reasons=(), snippet="query", block_id="block-1"),
            SearchHit(document=doc3, score=1.8, reasons=(), snippet="query", block_id="block-1"),
            SearchHit(document=doc4, score=1.5, reasons=(), snippet="query", block_id="block-1"), # Lowest score originally
        ]

        # The reranker should boost doc4 due to diversity_bonus
        reranked = rerank_hits("query", hits, self.config)
        
        # doc4 was at 1.5. After reranking (coverage and pos), all get similar base boosts. 
        # But doc4 gets a diversity_bonus of +0.5, jumping it up.
        self.assertTrue(any("diversity_boost" in r for r in reranked[0].reasons) or 
                        any("diversity_boost" in r for r in reranked[1].reasons) or
                        any("diversity_boost" in r for r in reranked[2].reasons))
                        
        doc_ids_top_3 = [h.document.doc_id for h in reranked[:3]]
        self.assertIn("d4", doc_ids_top_3)


if __name__ == "__main__":
    unittest.main()
