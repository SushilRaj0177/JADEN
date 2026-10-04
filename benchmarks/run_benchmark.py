"""JADEN: Empirical performance benchmark and environment profiler.

Measures actual throughput and latency distributions across 3 distinct address
complexity corpora without synthetic bias.
"""

import os
import sys
import time
import platform
import statistics
import json
from typing import List, Dict, Any

# Ensure UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from jaden.engine import AddressNormalizer


CORPUS_CLEAN_STANDARD = [
    "東京都千代田区霞が関2丁目1番2号",
    "東京都港区六本木6丁目10番1号",
    "神奈川県横浜市中区日本大通1番地",
    "大阪府大阪市中央区大手前2丁目1番",
    "愛知県名古屋市中区三の丸3丁目1番2号",
    "福岡県福岡市博多区東公園7番7号",
    "宮城県仙台市青葉区本町3丁目8番1号",
    "広島県広島市中区基町10番52号",
]

CORPUS_COMPLEX_CONVENTIONAL = [
    "京都府京都市中京区寺町通御池上る上本能寺前町488番地",
    "京都府京都市下京区烏丸通七条下ル東塩小路町721番地1",
    "京都府京都市東山区四条通大和大路東入祇園町北側",
    "北海道札幌市中央区北1条西2丁目1番地",
    "北海道札幌市中央区南3条東4丁目1番",
    "長野県長野市大字南長野字幅下692番地の2",
    "茨城県東茨城郡大洗町磯浜町6881番地",
    "石川県金沢市鞍月1丁目1番地",
]

CORPUS_DIRTY_REALWORLD = [
    "港区芝公園4-2-8 東京タワー",
    "新宿区西新宿2-8-1東京都庁 第一本庁舎",
    "横浜市中区海岸通1-1",
    "東京都千代田区霞が関１―２～３ー４",
    "港区六本木6-10-1六本木ヒルズ森タワー50F",
    "大阪市北区梅田3-1-1 JR大阪駅",
    "名古屋市中村区名駅1-1-4 JRセントラルタワーズ",
    "さいたま市大宮区錦町630",
]


def run_benchmark(iterations: int = 5000) -> Dict[str, Any]:
    normalizer = AddressNormalizer()

    # 1. Warm-up phase
    for addr in CORPUS_CLEAN_STANDARD + CORPUS_COMPLEX_CONVENTIONAL + CORPUS_DIRTY_REALWORLD:
        normalizer.normalize(addr)

    corpora = {
        "Clean Standard (Gaiku-hoshiki)": CORPUS_CLEAN_STANDARD,
        "Complex Conventional (Kyoto/Hokkaido/Chiban)": CORPUS_COMPLEX_CONVENTIONAL,
        "Dirty Real-World (Omitted/Dashes/Concatenated)": CORPUS_DIRTY_REALWORLD,
    }

    results: Dict[str, Any] = {
        "environment": {
            "os": f"{platform.system()} {platform.release()} ({platform.version()})",
            "processor": platform.processor() or "x86_64",
            "cpu_cores": os.cpu_count(),
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "corpora": {},
    }

    total_addresses_evaluated = 0
    total_benchmark_time_sec = 0.0

    print("=" * 70)
    print("JADEN EMPIRICAL BENCHMARK SUITE")
    print("=" * 70)
    print(f"OS: {results['environment']['os']}")
    print(f"Python: {results['environment']['python_version']} ({results['environment']['python_implementation']})")
    print(f"CPU Cores: {results['environment']['cpu_cores']}")
    print("-" * 70)

    for corpus_name, addresses in corpora.items():
        latencies_us: List[float] = []
        n_addr = len(addresses)
        reps = iterations // n_addr

        t_start = time.perf_counter()
        for _ in range(reps):
            for addr in addresses:
                t0 = time.perf_counter_ns()
                normalizer.normalize(addr)
                t1 = time.perf_counter_ns()
                latencies_us.append((t1 - t0) / 1000.0)
        t_end = time.perf_counter()

        elapsed_sec = t_end - t_start
        total_eval = len(latencies_us)
        throughput = total_eval / elapsed_sec

        total_addresses_evaluated += total_eval
        total_benchmark_time_sec += elapsed_sec

        latencies_sorted = sorted(latencies_us)
        p50 = statistics.median(latencies_sorted)
        p90 = latencies_sorted[int(total_eval * 0.90)]
        p99 = latencies_sorted[int(total_eval * 0.99)]
        mean_lat = statistics.mean(latencies_sorted)
        min_lat = min(latencies_sorted)
        max_lat = max(latencies_sorted)

        results["corpora"][corpus_name] = {
            "count": total_eval,
            "elapsed_seconds": round(elapsed_sec, 4),
            "throughput_ops_sec": round(throughput, 1),
            "latency_us": {
                "mean": round(mean_lat, 2),
                "p50_median": round(p50, 2),
                "p90": round(p90, 2),
                "p99": round(p99, 2),
                "min": round(min_lat, 2),
                "max": round(max_lat, 2),
            }
        }

        print(f"\nCorpus: {corpus_name}")
        print(f"  Operations:  {total_eval:,} evaluations in {elapsed_sec:.3f}s")
        print(f"  Throughput:  {throughput:,.1f} addresses/sec")
        print(f"  Latency P50: {p50:.2f} μs | P90: {p90:.2f} μs | P99: {p99:.2f} μs (Mean: {mean_lat:.2f} μs)")

    overall_throughput = total_addresses_evaluated / total_benchmark_time_sec
    results["overall_throughput_ops_sec"] = round(overall_throughput, 1)

    print("\n" + "=" * 70)
    print(f"AGGREGATE THROUGHPUT: {overall_throughput:,.1f} addresses/sec")
    print("=" * 70)

    # Save benchmark result artifact
    out_path = os.path.join(os.path.dirname(__file__), "benchmark_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Saved complete benchmark telemetry to {out_path}")

    return results


if __name__ == "__main__":
    run_benchmark(iterations=10000)
