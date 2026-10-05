"""JADEN: Empirical performance benchmark and environment profiler.

Measures actual throughput, latency distributions, and memory allocations
across a representative 500-address corpus spanning all Japanese addressing regimes:
- Corpus 1: Clean Standard Gaiku-hoshiki (200 distinct addresses)
- Corpus 2: Complex Conventional Kyoto, Hokkaido & Cadastral Chiban (150 distinct addresses)
- Corpus 3: Dirty Real-World Inputs with Omissions, Dashes & Unit/Floor tags (150 distinct addresses)
Total Unique Addresses in Benchmark: 500
"""

import os
import sys
import time
import platform
import statistics
import json
import tracemalloc
from typing import List, Dict, Any

# Ensure UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from jaden.engine import AddressNormalizer
from jaden.data.loader import get_registry


def build_representative_corpus() -> Dict[str, List[str]]:
    """Builds an empirically diverse corpus of 500 distinct Japanese addresses."""
    reg = get_registry()
    all_munis = list(reg._municipalities_by_code.values())

    # -------------------------------------------------------------------------
    # Corpus 1: Clean Standard Gaiku-hoshiki (200 distinct addresses)
    # -------------------------------------------------------------------------
    clean_addrs: List[str] = []
    # Sample 200 distinct municipalities across all 47 prefectures
    step = max(1, len(all_munis) // 200)
    for i in range(200):
        m = all_munis[(i * step) % len(all_munis)]
        chome = (i % 8) + 1
        ban = (i * 3 % 25) + 1
        go = (i * 7 % 15) + 1
        clean_addrs.append(f"{m.prefecture_name}{m.name}本町{chome}丁目{ban}番{go}号")

    # -------------------------------------------------------------------------
    # Corpus 2: Complex Conventional (150 distinct addresses)
    # 50 Kyoto intersections + 50 Hokkaido Jo-Chome + 50 Cadastral Chiban
    # -------------------------------------------------------------------------
    complex_addrs: List[str] = []

    # 2a. Kyoto Intersections (50 distinct)
    kyoto_streets_ns = ["寺町通", "烏丸通", "河原町通", "新町通", "室町通", "東洞院通", "西洞院通", "堀川通", "大宮通", "千本通"]
    kyoto_streets_ew = ["御池通", "四条通", "三条通", "五条通", "丸太町通", "下立売通", "上立売通", "六角通", "錦小路通", "七条通"]
    kyoto_dirs = ["上る", "下る", "東入", "西入", "下ル"]
    for i in range(50):
        s1 = kyoto_streets_ns[i % len(kyoto_streets_ns)]
        s2 = kyoto_streets_ew[(i * 3) % len(kyoto_streets_ew)]
        d = kyoto_dirs[(i * 2) % len(kyoto_dirs)]
        lot = 100 + i * 7
        complex_addrs.append(f"京都府京都市中京区{s1}{s2}{d}町{lot}番地")

    # 2b. Hokkaido Jo-Chome Grid (50 distinct)
    for i in range(50):
        ns = "北" if i % 2 == 0 else "南"
        ew = "西" if (i // 2) % 2 == 0 else "東"
        jo = (i % 15) + 1
        chome = ((i * 3) % 20) + 1
        lot = (i * 5 % 30) + 1
        complex_addrs.append(f"北海道札幌市中央区{ns}{jo}条{ew}{chome}丁目{lot}番地")

    # 2c. Cadastral Lot / Oaza / Koaza (50 distinct)
    cadastral_locs = [
        ("長野県", "長野市", "南長野", "幅下"),
        ("青森県", "八戸市", "鮫町", "日出町"),
        ("福島県", "福島市", "松川町", "浅川"),
        ("岩手県", "盛岡市", "玉山区", "薮川"),
        ("新潟県", "新潟市西蒲区", "巻", "甲"),
    ]
    for i in range(50):
        pref, city, oaza, koaza = cadastral_locs[i % len(cadastral_locs)]
        banchi = 200 + i * 11
        edaban = (i % 7) + 1
        complex_addrs.append(f"{pref}{city}大字{oaza}字{koaza}{banchi}番地の{edaban}")

    # -------------------------------------------------------------------------
    # Corpus 3: Dirty Real-World (150 distinct addresses)
    # Omitted prefectures, wave dashes, compound buildings, floors, bare units
    # -------------------------------------------------------------------------
    dirty_addrs: List[str] = []
    bldgs = ["タワー", "ヒルズ", "レジデンス", "メゾン", "セントラルビル", "国際センタービル"]
    floors = ["3階", "50F", "地下1階", "B2F", "12F", "8階"]
    for i in range(150):
        m = all_munis[(i * 13) % len(all_munis)]
        bldg_name = f"第{i % 5 + 1}{bldgs[i % len(bldgs)]}"
        fl = floors[i % len(floors)]
        unit = 100 + (i * 3 % 800)

        # Mix formatting styles: dashes, omitted prefecture, full-width numbers
        if i % 3 == 0:
            # Full-width wave dash notation with building and floor
            dirty_addrs.append(f"{m.name}本町{i % 5 + 1}―{i % 20 + 1}～{i % 10 + 1} {bldg_name} {fl}")
        elif i % 3 == 1:
            # Omitted prefecture with bare room unit
            dirty_addrs.append(f"{m.name}中央{i % 9 + 1}-{(i * 2) % 25 + 1} {bldg_name} {unit}")
        else:
            # Concatenated building and basement floor
            dirty_addrs.append(f"{m.prefecture_name}{m.name}大通{i % 7 + 1}-{(i * 3) % 15 + 1}-{i % 8 + 1}{bldg_name}{fl}{unit}号室")

    assert len(clean_addrs) == 200
    assert len(complex_addrs) == 150
    assert len(dirty_addrs) == 150

    return {
        "Clean Standard (Gaiku-hoshiki: 200 unique)": clean_addrs,
        "Complex Conventional (Kyoto/Hokkaido/Cadastral: 150 unique)": complex_addrs,
        "Dirty Real-World (Omitted/Dashes/Buildings: 150 unique)": dirty_addrs,
    }


def run_benchmark(eval_passes_per_corpus: int = 10) -> Dict[str, Any]:
    """Runs a rigorous empirical benchmark over the 500-address corpus."""
    tracemalloc.start()
    t_init_start = time.perf_counter()
    normalizer = AddressNormalizer()
    init_time_sec = time.perf_counter() - t_init_start

    # Measure baseline memory footprint of registry & tries
    mem_current, mem_peak_init = tracemalloc.get_traced_memory()
    registry_footprint_mb = mem_peak_init / (1024 * 1024)

    corpora = build_representative_corpus()
    total_unique_addresses = sum(len(addrs) for addrs in corpora.values())

    # Measure peak heap allocation during active normalization pass
    for addrs in corpora.values():
        for addr in addrs[:50]:
            normalizer.normalize(addr)
    mem_final, mem_peak_total = tracemalloc.get_traced_memory()
    peak_heap_mb = mem_peak_total / (1024 * 1024)
    tracemalloc.stop()

    results: Dict[str, Any] = {
        "environment": {
            "os": f"{platform.system()} {platform.release()} ({platform.version()})",
            "processor": platform.processor() or "x86_64",
            "cpu_cores": os.cpu_count(),
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "memory_profile": {
            "registry_heap_allocation_mb": round(registry_footprint_mb, 2),
            "registry_initialization_seconds": round(init_time_sec, 4),
        },
        "corpus_statistics": {
            "total_unique_addresses": total_unique_addresses,
            "evaluation_passes": eval_passes_per_corpus,
        },
        "corpora": {},
    }

    print("=" * 75)
    print("JADEN EMPIRICAL BENCHMARK SUITE — REPRESENTATIVE CORPUS (500 UNIQUE)")
    print("=" * 75)
    print(f"OS:               {results['environment']['os']}")
    print(f"Python:           {results['environment']['python_version']} ({results['environment']['python_implementation']})")
    print(f"CPU Cores:        {results['environment']['cpu_cores']}")
    print(f"Registry Memory:  {registry_footprint_mb:.2f} MB heap (1,918 municipalities + 47 prefectures)")
    print(f"Evaluation Scale: {total_unique_addresses} unique addresses x {eval_passes_per_corpus} passes = {total_unique_addresses * eval_passes_per_corpus:,} operations")
    print("-" * 75)

    total_addresses_evaluated = 0
    total_benchmark_time_sec = 0.0

    for corpus_name, addresses in corpora.items():
        latencies_us: List[float] = []

        t_start = time.perf_counter()
        for _ in range(eval_passes_per_corpus):
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
            "unique_addresses": len(addresses),
            "evaluations": total_eval,
            "elapsed_seconds": round(elapsed_sec, 4),
            "throughput_addresses_per_sec": round(throughput, 1),
            "latency_microseconds": {
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
        print(f"  Latency:     P50: {p50:.2f} μs | P90: {p90:.2f} μs | P99: {p99:.2f} μs (Mean: {mean_lat:.2f} μs)")

    overall_throughput = total_addresses_evaluated / total_benchmark_time_sec
    results["overall_throughput_addresses_per_sec"] = round(overall_throughput, 1)
    results["memory_profile"]["peak_heap_allocation_mb"] = round(peak_heap_mb, 2)

    print("\n" + "=" * 75)
    print(f"AGGREGATE THROUGHPUT:  {overall_throughput:,.1f} addresses/sec")
    print(f"PEAK MEMORY PROFILE:   {peak_heap_mb:.2f} MB")
    print("=" * 75)

    # Save benchmark result artifact (relative path)
    out_rel = os.path.join("benchmarks", "benchmark_results.json")
    out_abs = os.path.join(os.path.dirname(__file__), "benchmark_results.json")
    with open(out_abs, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Saved verified benchmark telemetry to {out_rel}")

    return results


if __name__ == "__main__":
    run_benchmark(eval_passes_per_corpus=10)
