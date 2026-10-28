"""Benchmark script for measuring baseline Ollama / Gemma 4 inference performance."""

import json
import time
import requests
import psutil
from jarvis.config import config
from jarvis.conversation.manager import ConversationManager
from jarvis.llm.ollama_client import OllamaClient


def get_process_stats():
    """Get CPU percent and RAM usage."""
    vm = psutil.virtual_memory()
    return {
        "ram_used_gb": round((vm.total - vm.available) / (1024 ** 3), 2),
        "ram_percent": vm.percent,
        "cpu_percent": psutil.cpu_percent(interval=0.1),
    }


def check_ollama_ps():
    """Query currently loaded models in Ollama."""
    try:
        resp = requests.get("http://localhost:11434/api/ps", timeout=3)
        return resp.json().get("models", [])
    except Exception as exc:
        return [{"error": str(exc)}]


def raw_ollama_profile(prompt: str, keep_alive=None, options=None):
    """Direct profiling of /api/chat with streaming to capture TTFT and Ollama metrics."""
    endpoint = f"{config.ollama.base_url}/api/chat"
    payload = {
        "model": config.ollama.model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
    }
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive
    if options is not None:
        payload["options"] = options

    t0 = time.perf_counter()
    ttft = None
    chunks_received = 0
    final_stats = {}
    content_chunks = []

    with requests.post(endpoint, json=payload, stream=True, timeout=60) as resp:
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            chunk = json.loads(line)
            token = chunk.get("message", {}).get("content", "")
            if token:
                if ttft is None:
                    ttft = time.perf_counter() - t0
                content_chunks.append(token)
                chunks_received += 1

            if chunk.get("done", False):
                final_stats = {
                    "total_duration_ms": round(chunk.get("total_duration", 0) / 1e6, 2),
                    "load_duration_ms": round(chunk.get("load_duration", 0) / 1e6, 2),
                    "prompt_eval_count": chunk.get("prompt_eval_count", 0),
                    "prompt_eval_duration_ms": round(chunk.get("prompt_eval_duration", 0) / 1e6, 2),
                    "eval_count": chunk.get("eval_count", 0),
                    "eval_duration_ms": round(chunk.get("eval_duration", 0) / 1e6, 2),
                }

    total_time = time.perf_counter() - t0
    final_stats["client_total_time_ms"] = round(total_time * 1000, 2)
    final_stats["ttft_ms"] = round(ttft * 1000, 2) if ttft else None
    if final_stats.get("eval_duration_ms", 0) > 0 and final_stats.get("eval_count", 0) > 0:
        final_stats["tokens_per_sec"] = round(
            final_stats["eval_count"] / (final_stats["eval_duration_ms"] / 1000.0), 2
        )
    else:
        final_stats["tokens_per_sec"] = 0.0

    return final_stats, "".join(content_chunks)


def run_baseline_benchmarks():
    print("=" * 60)
    print("JARVIS GEMMA 4 BASELINE PROFILING")
    print("=" * 60)

    # 1. Connection check latency
    t_conn_start = time.perf_counter()
    client = OllamaClient()
    connected = client.check_connection()
    conn_time = (time.perf_counter() - t_conn_start) * 1000
    print(f"Ollama check_connection(): {conn_time:.2f} ms (Connected: {connected})")

    # 2. Check loaded state
    loaded_before = check_ollama_ps()
    print(f"Loaded models before benchmark: {loaded_before}")

    # 3. Cold request benchmark
    print("\n--- 1. Cold Request (Model loading from disk) ---")
    stats_cold, resp_cold = raw_ollama_profile("Hello JARVIS, are you online?")
    print(json.dumps(stats_cold, indent=2))
    print(f"Response preview: {resp_cold[:80]}...")
    print("Loaded models after cold request:", check_ollama_ps())

    # 4. Five Warm requests benchmark
    prompts = [
        "What time is it?",
        "Give me three tips for computer maintenance.",
        "What is the capital of France and its famous landmark?",
        "Explain briefly what Python is.",
        "Summarize how memory management works in computers.",
    ]

    print("\n--- 2. Five Warm Requests ---")
    warm_results = []
    for i, p in enumerate(prompts, 1):
        time.sleep(0.5)  # brief gap
        stats, text = raw_ollama_profile(p)
        stats["prompt"] = p
        warm_results.append(stats)
        print(f"Warm #{i} ['{p[:30]}...']: "
              f"TTFT={stats['ttft_ms']}ms, "
              f"Total={stats['client_total_time_ms']}ms, "
              f"Tokens={stats['eval_count']}, "
              f"Speed={stats['tokens_per_sec']} tok/s, "
              f"Load={stats['load_duration_ms']}ms")

    # 5. Full ConversationManager workflow benchmark (including ensure_model_available overhead)
    print("\n--- 3. Existing ConversationManager.process_user_input Benchmark ---")
    mgr = ConversationManager()
    stats_before = get_process_stats()
    print(f"System resources before: {stats_before}")

    t_mgr_0 = time.perf_counter()
    reply = mgr.process_user_input("Give me a short one sentence quote about technology.")
    t_mgr_elapsed = (time.perf_counter() - t_mgr_0) * 1000
    print(f"ConversationManager process_user_input total time: {t_mgr_elapsed:.2f} ms")
    print(f"Reply: {reply}")
    stats_after = get_process_stats()
    print(f"System resources after: {stats_after}")

    # Print summary statistics
    ttfts = [r["ttft_ms"] for r in warm_results if r["ttft_ms"]]
    totals = [r["client_total_time_ms"] for r in warm_results]
    tps = [r["tokens_per_sec"] for r in warm_results if r["tokens_per_sec"]]

    import statistics
    print("\n" + "=" * 60)
    print("BASELINE SUMMARY STATISTICS (5 Warm Requests):")
    print(f"  • Median TTFT (Time to First Token): {statistics.median(ttfts):.2f} ms")
    print(f"  • Median Total Latency:             {statistics.median(totals):.2f} ms")
    print(f"  • Median Generation Speed:          {statistics.median(tps):.2f} tok/s")
    print("=" * 60)


if __name__ == "__main__":
    run_baseline_benchmarks()
