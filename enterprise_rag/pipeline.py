from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from time import perf_counter

from enterprise_rag.audit import create_audit_entry, log_query
from enterprise_rag.config import PipelineConfig, load_config
from enterprise_rag.generator import generate_grounded_answer
from enterprise_rag.graph import PipelineGraph, PipelineState
from enterprise_rag.intent import classify_intent
from enterprise_rag.loaders import load_documents, load_users
from enterprise_rag.models import QueryTrace, RagAnswer
from enterprise_rag.reranker import rerank_hits
from enterprise_rag.retrieval import HybridRetriever
from enterprise_rag.router import is_out_of_scope_query, route_query
from enterprise_rag.security import filter_accessible_documents


class EnterpriseRagPipeline:
    def __init__(self, data_dir: Path, config: PipelineConfig | None = None) -> None:
        self.data_dir = data_dir
        self.config = config or load_config()
        self.users = load_users(data_dir)
        self.documents = load_documents(data_dir)
        self.documents_by_source = {
            source_type: [
                document
                for document in self.documents
                if document.source_type == source_type
            ]
            for source_type in {document.source_type for document in self.documents}
        }
        self.retriever = HybridRetriever(self.documents, self.config.retrieval)
        self._answer_cache: OrderedDict[tuple[str, str], tuple[RagAnswer, tuple]] = OrderedDict()
        self.graph = self._build_graph()

    def ask(self, user_id: str, query: str) -> RagAnswer:
        request_start = perf_counter()
        user = self.users[user_id]
        cache_key = (user_id, _normalize_query(query))
        
        if self.config.cache.enabled:
            cached_answer = self._answer_cache.get(cache_key)
            if cached_answer is not None:
                answer, cached_accessible_documents = cached_answer
                self._answer_cache.move_to_end(cache_key)
                self._audit(
                    user_id,
                    query,
                    answer,
                    accessible_documents=cached_accessible_documents,
                    blocked_count=len(answer.trace.blocked_documents),
                )
                return answer

        initial_state = PipelineState(
            user_id=user_id,
            query=query,
        )
        
        final_state = self.graph.execute(initial_state)
        
        if final_state.answer is None:
             raise RuntimeError("Pipeline failed to generate an answer.")
             
        final_state.answer.trace.timings_ms["total"] = _elapsed_ms(request_start)
        answer = final_state.answer

        self._audit(user_id, query, answer, final_state.accessible_documents, len(final_state.blocked_documents))
        
        if self.config.cache.enabled:
            self._cache_answer(cache_key, answer, tuple(final_state.accessible_documents))

        return answer

    def _build_graph(self) -> PipelineGraph:
        graph = PipelineGraph()
        
        graph.add_node("classify_intent", self._node_classify_intent)
        graph.add_node("check_scope", self._node_check_scope)
        graph.add_node("route", self._node_route)
        graph.add_node("security", self._node_security)
        graph.add_node("retrieve", self._node_retrieve)
        graph.add_node("rerank", self._node_rerank)
        graph.add_node("generate", self._node_generate)
        
        graph.add_edge("classify_intent", "check_scope")
        
        graph.add_conditional_edge(
            "check_scope", 
            "route", 
            lambda state: not state.short_circuited
        )
        
        graph.add_edge("route", "security")
        graph.add_edge("security", "retrieve")
        
        graph.add_conditional_edge(
            "retrieve",
            "rerank",
            lambda state: self.config.reranker.enabled
        )
        graph.add_conditional_edge(
            "retrieve",
            "generate",
            lambda state: not self.config.reranker.enabled
        )
        
        graph.add_edge("rerank", "generate")
        
        graph.set_entry_point("classify_intent")
        return graph

    # --- Pipeline Nodes ---

    def _node_classify_intent(self, state: PipelineState) -> PipelineState:
        state.intent = classify_intent(state.query)
        return state

    def _node_check_scope(self, state: PipelineState) -> PipelineState:
        if is_out_of_scope_query(state.query):
            state.answer = RagAnswer(
                answer=(
                    "This assistant is scoped to enterprise knowledge retrieval. "
                    "Ask about documents, records, logs, access policies, compliance, "
                    "finance, HR, security, legal, or operations data."
                ),
                citations=(),
                confidence=0.0,
                trace=QueryTrace(
                    intent=state.intent,
                    routed_sources=(),
                    route_reason="Out-of-scope query short-circuited before retrieval.",
                    accessible_documents=0,
                    blocked_documents=(),
                    retrieval_notes=("short_circuit=out_of_scope",),
                    timings_ms={},
                ),
                answer_strategy="no_evidence",
            )
            state.short_circuited = True
        return state

    def _node_route(self, state: PipelineState) -> PipelineState:
        start = perf_counter()
        state.routed_sources, state.route_reason = route_query(state.query)
        state.timings_ms["route"] = _elapsed_ms(start)
        return state

    def _node_security(self, state: PipelineState) -> PipelineState:
        start = perf_counter()
        routed_documents = []
        for source_type in state.routed_sources:
            routed_documents.extend(self.documents_by_source.get(source_type, ()))
            
        user = self.users[state.user_id]
        acc, blocked, filter_applied = filter_accessible_documents(user, routed_documents, self.config.security)
        
        state.accessible_documents = acc
        state.blocked_documents = blocked
        state.sensitivity_filter_applied = filter_applied
        state.timings_ms["security"] = _elapsed_ms(start)
        return state

    def _node_retrieve(self, state: PipelineState) -> PipelineState:
        start = perf_counter()
        allowed_doc_ids = {document.doc_id for document in state.accessible_documents}
        hits, notes = self.retriever.search(
            state.query,
            state.routed_sources,
            allowed_doc_ids=allowed_doc_ids,
        )
        state.search_hits = hits
        state.retrieval_notes = notes
        state.timings_ms["retrieval"] = _elapsed_ms(start)
        return state

    def _node_rerank(self, state: PipelineState) -> PipelineState:
        start = perf_counter()
        state.search_hits = rerank_hits(state.query, state.search_hits, self.config.reranker)
        state.reranker_applied = True
        state.timings_ms["rerank"] = _elapsed_ms(start)
        return state

    def _node_generate(self, state: PipelineState) -> PipelineState:
        start = perf_counter()
        trace = QueryTrace(
            intent=state.intent,
            routed_sources=state.routed_sources,
            route_reason=state.route_reason,
            accessible_documents=len(state.accessible_documents),
            blocked_documents=state.blocked_documents,
            retrieval_notes=state.retrieval_notes,
            sensitivity_filter_applied=state.sensitivity_filter_applied,
            reranker_applied=state.reranker_applied,
            timings_ms=state.timings_ms,
        )
        answer = generate_grounded_answer(state.query, state.search_hits, trace)
        state.answer = answer
        state.timings_ms["generation"] = _elapsed_ms(start)
        return state

    # --- Helpers ---

    def _cache_answer(
        self,
        cache_key: tuple[str, str],
        answer: RagAnswer,
        accessible_documents: tuple,
    ) -> None:
        self._answer_cache[cache_key] = (answer, accessible_documents)
        self._answer_cache.move_to_end(cache_key)
        if len(self._answer_cache) > self.config.cache.max_size:
            self._answer_cache.popitem(last=False)

    def _audit(
        self,
        user_id: str,
        query: str,
        answer: RagAnswer,
        accessible_documents,
        blocked_count: int,
    ) -> None:
        sensitivity_levels = tuple(
            sorted({doc.sensitivity_level.value for doc in accessible_documents})
        )
        entry = create_audit_entry(
            user_id=user_id,
            query=query,
            routed_sources=tuple(s.value for s in answer.trace.routed_sources),
            accessible_count=len(accessible_documents),
            blocked_count=blocked_count,
            answer_confidence=answer.confidence,
            sensitivity_levels_accessed=sensitivity_levels,
        )
        log_query(self.data_dir, entry)

    def get_users(self) -> dict:
        """Return user metadata suitable for the web API."""
        return {
            uid: {
                "user_id": u.user_id,
                "display_name": u.display_name,
                "roles": list(u.roles),
            }
            for uid, u in self.users.items()
        }


def _normalize_query(query: str) -> str:
    return " ".join(query.lower().split())


def _elapsed_ms(start: float) -> float:
    return round((perf_counter() - start) * 1000, 3)
