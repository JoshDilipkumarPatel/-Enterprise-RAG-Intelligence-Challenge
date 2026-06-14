from __future__ import annotations

import argparse
import sys
from pathlib import Path

from enterprise_rag.pipeline import EnterpriseRagPipeline


def main() -> None:
    # Ensure emoji output works on Windows terminals
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    parser = argparse.ArgumentParser(description="Secure Enterprise RAG demo")
    parser.add_argument("--user", help="User id, for example alice or bob")
    parser.add_argument("--query", help="Natural-language enterprise question")
    parser.add_argument("--data-dir", default="data", help="Path to synthetic data directory")
    parser.add_argument("--serve", action="store_true", help="Launch the web dashboard")
    parser.add_argument("--port", type=int, default=8080, help="Port for the web dashboard")
    args = parser.parse_args()

    pipeline = EnterpriseRagPipeline(Path(args.data_dir))

    if args.serve:
        from enterprise_rag.web.server import start_server
        start_server(pipeline, port=args.port)
        return

    if not args.user or not args.query:
        parser.error("--user and --query are required in CLI mode (or use --serve)")

    answer = pipeline.ask(args.user, args.query)

    print("\nANSWER")
    print(answer.answer)
    print("\nSTRATEGY")
    print(answer.answer_strategy)
    print("\nCITATIONS")
    if answer.citations:
        for citation in answer.citations:
            print(f"- {citation}")
    else:
        print("- none")
    print(f"\nCONFIDENCE\n{answer.confidence:.2f}")
    print("\nTRACE")
    print(f"- intent: {answer.trace.intent.value if answer.trace.intent else 'none'}")
    print(f"- routed_sources: {', '.join(source.value for source in answer.trace.routed_sources)}")
    print(f"- route_reason: {answer.trace.route_reason}")
    print(f"- accessible_documents: {answer.trace.accessible_documents}")
    print(f"- blocked_documents: {len(answer.trace.blocked_documents)}")
    if answer.trace.sensitivity_filter_applied:
        print("- sensitivity_filter: APPLIED")
    if answer.trace.reranker_applied:
        print("- reranker: APPLIED")
    if answer.trace.timings_ms:
        for name, value in answer.trace.timings_ms.items():
            print(f"- timing_{name}: {value:.3f} ms")
    for note in answer.trace.retrieval_notes:
        print(f"- {note}")


if __name__ == "__main__":
    main()
