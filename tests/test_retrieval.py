import unittest
from pathlib import Path

from enterprise_rag.loaders import load_documents
from enterprise_rag.models import SourceType
from enterprise_rag.retrieval import HybridRetriever
from enterprise_rag.text_utils import chunk_text, first_matching_sentence


class ChunkTextTest(unittest.TestCase):
    def test_short_text_returns_single_chunk(self) -> None:
        text = "This is a short text."
        chunks = chunk_text(text, chunk_size=200)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], text)

    def test_long_text_splits_into_overlapping_chunks(self) -> None:
        words = ["word"] * 500
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=200, overlap=40)
        self.assertGreater(len(chunks), 1)
        # Each chunk except the last should be about chunk_size words
        first_chunk_words = chunks[0].split()
        self.assertEqual(len(first_chunk_words), 200)

    def test_overlap_creates_shared_content(self) -> None:
        words = [f"w{i}" for i in range(300)]
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=200, overlap=50)
        # The second chunk should start with content from the end of the first
        first_end_words = set(chunks[0].split()[-50:])
        second_start_words = set(chunks[1].split()[:50])
        self.assertEqual(first_end_words, second_start_words)

    def test_snippet_prefers_highest_overlap_sentence(self) -> None:
        text = (
            "Payment was delayed. "
            "The updated vendor payment workflow requires dual approval."
        )
        snippet = first_matching_sentence(
            text,
            {"vendor", "payment", "workflow", "approval"},
        )

        self.assertIn("vendor payment workflow", snippet)


class HybridRetrieverTest(unittest.TestCase):
    def setUp(self) -> None:
        data_dir = Path("data")
        self.all_docs = load_documents(data_dir)

    def test_search_returns_results_for_matching_query(self) -> None:
        retriever = HybridRetriever(self.all_docs)
        hits, notes = retriever.search("vendor payment approval", tuple(SourceType))
        self.assertGreater(len(hits), 0)
        self.assertTrue(any("vendor_payment" in h.document.doc_id for h in hits))

    def test_search_returns_empty_for_gibberish(self) -> None:
        retriever = HybridRetriever(self.all_docs)
        hits, _ = retriever.search("xyzzy zorch flurble", tuple(SourceType))
        self.assertEqual(len(hits), 0)

    def test_deduplication_across_chunks(self) -> None:
        retriever = HybridRetriever(self.all_docs)
        hits, _ = retriever.search("cloud migration status infrastructure", tuple(SourceType))
        doc_ids = [h.document.doc_id for h in hits]
        self.assertEqual(len(doc_ids), len(set(doc_ids)), "Duplicate doc_ids in results")

    def test_results_are_sorted_by_score(self) -> None:
        retriever = HybridRetriever(self.all_docs)
        hits, _ = retriever.search("security alert penetration", tuple(SourceType))
        scores = [h.score for h in hits]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_score_reasons_are_populated(self) -> None:
        retriever = HybridRetriever(self.all_docs)
        hits, _ = retriever.search("GDPR compliance assessment", tuple(SourceType))
        if hits:
            self.assertGreater(len(hits[0].reasons), 0)

    def test_hits_include_block_ids_for_citation_traceability(self) -> None:
        retriever = HybridRetriever(self.all_docs)
        hits, _ = retriever.search("vendor payment approval", tuple(SourceType))

        self.assertTrue(hits)
        self.assertTrue(hits[0].block_id.startswith("block-"))

    def test_search_applies_allowed_document_metadata_filter(self) -> None:
        retriever = HybridRetriever(self.all_docs)
        hits, notes = retriever.search(
            "impossible travel security alert",
            tuple(SourceType),
            allowed_doc_ids={"vendor_payment_workflow"},
        )

        self.assertEqual(hits, [])
        self.assertIn("metadata_filter_allowed_docs=1", notes)


if __name__ == "__main__":
    unittest.main()
