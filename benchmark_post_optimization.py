"""Complete before-and-after verification benchmark for Gemma 4 performance boost."""

import json
import statistics
import time
import psutil
import requests
from jarvis.config import config
from jarvis.conversation.manager import ConversationManager
from jarvis.llm.ollama_client import OllamaClient


def get_system_stats():
    vm = psutil.virtual_memory()
    return {
        "ram_used_gb": round((vm.total - vm.available) / (1024 ** 3), 2),
        "ram_percent": vm.percent,
        "cpu_percent": psutil.cpu_percent(interval=0.1),
    }


def get_loaded_models():
    try:
        r = requests.get(f"{config.ollama.base_url}/api/ps", timeout=3)
        return r.json().get("models", [])
    except Exception as exc:
        return []


def run_post_optimization_benchmark():
    print("=" * 65)
    print("JARVIS GEMMA 4 POST-OPTIMIZATION PERFORMANCE BENCHMARK")
    print("=" * 65)

    client = OllamaClient()

    # 1. Connection check latency (with persistent session & cached state)
    t0 = time.perf_counter()
    connected = client.check_connection()
    conn_ms = (time.perf_counter() - t0) * 1000
    print(f"Ollama check_connection(): {conn_ms:.2f} ms (Connected: {connected})")

    # 2. Check loaded state
    loaded = get_loaded_models()
    print(f"Loaded models in memory: {len(loaded)}")
    for m in loaded:
        print(f"  • Model: {m.get('name')} | VRAM: {round(m.get('size_vram',0)/(1024**2), 1)} MB | Expires: {m.get('expires_at')}")

    # 3. Five Warm Requests with identical prompts to baseline
    prompts = [
        "What time is it?",
        "Give me three tips for computer maintenance.",
        "What is the capital of France and its famous landmark?",
        "Explain briefly what Python is.",
        "Summarize how memory management works in computers.",
    ]

    print("\n--- 5 Warm Requests Benchmark ---")
    results = []

    for i, p in enumerate(prompts, 1):
        time.sleep(0.3)
        tokens_received = []
        ttft = None
        t_req_start = time.perf_counter()

        def on_token(t: str):
            nonlocal ttft
            if ttft is None:
                ttft = (time.perf_counter() - t_req_start) * 1000
            tokens_received.append(t)

        reply = client.chat_stream(
            messages=[{"role": "user", "content": p}],
            on_token=on_token,
        )
        total_time_ms = (time.perf_counter() - t_req_start) * 1000
        metrics = client.last_metrics

        res = {
            "prompt": p,
            "ttft_ms": round(ttft, 2) if ttft else None,
            "total_ms": round(total_time_ms, 2),
            "eval_count": metrics.get("eval_count", 0),
            "eval_duration_ms": metrics.get("eval_duration_ms", 0),
            "tokens_per_sec": metrics.get("tokens_per_sec", 0.0),
            "load_duration_ms": metrics.get("load_duration_ms", 0.0),
            "reply_preview": reply[:60].replace("\n", " "),
        }
        results.append(res)
        print(f"Warm #{i}: TTFT={res['ttft_ms']}ms | Total={res['total_ms']}ms | Tokens={res['eval_count']} @ {res['tokens_per_sec']} tok/s | Load={res['load_duration_ms']}ms | '{res['reply_preview']}...'")

    # 4. Full ConversationManager end-to-end test (including tool call)
    print("\n--- End-to-End ConversationManager Test (Tool Execution) ---")
    mgr = ConversationManager()
    stats_before = get_system_stats()
    print(f"System resources before: {stats_before}")

    t_tool_0 = time.perf_counter()
    tool_reply = mgr.process_user_input("What time is it right now?")
    t_tool_ms = (time.perf_counter() - t_tool_0) * 1000
    print(f"Tool turn total latency: {t_tool_ms:.2f} ms")
    print(f"Tool reply: \"{tool_reply.strip()}\"")

    t_chat_0 = time.perf_counter()
    chat_reply = mgr.process_user_input("Give me a short one sentence quote about technology.")
    t_chat_ms = (time.perf_counter() - t_chat_0) * 1000
    print(f"Direct conversational turn total latency: {t_chat_ms:.2f} ms")
    print(f"Direct reply: \"{chat_reply.strip()}\"")

    stats_after = get_system_stats()
    print(f"System resources after: {stats_after}")

    # 5. Summary Statistics
    ttfts = [r["ttft_ms"] for r in results if r["ttft_ms"]]
    totals = [r["total_ms"] for r in results]
    tps = [r["tokens_per_sec"] for r in results if r["tokens_per_sec"]]

    print("\n" + "=" * 65)
    print("POST-OPTIMIZATION SUMMARY (5 Warm Requests):")
    print(f"  • Median TTFT (Time to First Token): {statistics.median(ttfts):.2f} ms")
    print(f"  • Median Total Latency:             {statistics.median(totals):.2f} ms")
    print(f"  • Median Generation Speed:          {statistics.median(tps):.2f} tok/s")
    print("=" * 65)

    client.close()


if __name__ == "__main__":
    run_post_optimization_benchmark()
