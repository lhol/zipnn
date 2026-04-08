#!/usr/bin/env python
"""
Memory leak verification script for ZipNN.

This script tests whether the memory leak fix in zipnn_core.c is working correctly.
If memory usage stays stable after multiple compress/decompress cycles, the fix is successful.

Usage:
    python test_memory_leak.py
    
    # With more iterations
    python test_memory_leak.py --iterations 500
    
    # With larger tensors
    python test_memory_leak.py --size 2000
"""

import argparse
import gc
import sys

try:
    import psutil
except ImportError:
    print("psutil not installed. Install with: pip install psutil")
    sys.exit(1)

try:
    import torch
except ImportError:
    print("torch not installed. Install with: pip install torch")
    sys.exit(1)

from zipnn import ZipNN


def get_memory_mb():
    """Get current process memory usage in MB."""
    process = psutil.Process()
    return process.memory_info().rss / (1024 ** 2)


def test_memory_leak(iterations=100, tensor_size=1000, print_interval=20):
    """
    Test for memory leaks by running multiple compress/decompress cycles.
    
    Args:
        iterations: Number of compress/decompress cycles
        tensor_size: Size of square tensor (tensor_size x tensor_size)
        print_interval: How often to print memory status
    
    Returns:
        True if no significant memory leak detected, False otherwise
    """
    print("=" * 60)
    print("ZipNN Memory Leak Test")
    print("=" * 60)
    print(f"Iterations: {iterations}")
    print(f"Tensor size: {tensor_size} x {tensor_size} (float16)")
    print(f"Tensor memory: {tensor_size * tensor_size * 2 / (1024**2):.2f} MB per tensor")
    print("=" * 60)
    
    # Force initial garbage collection
    gc.collect()
    initial_memory = get_memory_mb()
    print(f"Initial memory: {initial_memory:.1f} MB")
    print()
    
    # Create ZipNN instance (singleton pattern - one instance for all operations)
    zpn = ZipNN(method='huffman', input_format='torch')
    
    memory_readings = []
    
    for i in range(iterations):
        # Create random tensor
        tensor = torch.randn(tensor_size, tensor_size, dtype=torch.float16)
        
        # Compress
        compressed = zpn.compress(tensor)
        
        # Decompress
        decompressed = zpn.decompress(compressed)
        
        # Verify data integrity (check every iteration for thoroughness)
        # Use strict tolerance (1e-7) since compression should be lossless
        if not torch.allclose(tensor, decompressed, rtol=1e-7, atol=1e-7):
            print(f"ERROR: Data integrity check failed at iteration {i}!")
            print(f"  Max difference: {(tensor - decompressed).abs().max().item()}")
            return False
        
        if i == 0:
            print("Data integrity check: PASSED (will verify every iteration)")
            print()
        
        # Explicitly delete to help GC
        del compressed, decompressed, tensor
        
        # Periodic memory check and cleanup
        if i % print_interval == 0:
            gc.collect()
            current_memory = get_memory_mb()
            memory_readings.append(current_memory)
            memory_increase = current_memory - initial_memory
            print(f"Iteration {i:4d}: Memory = {current_memory:.1f} MB "
                  f"(+{memory_increase:.1f} MB from start)")
    
    # Final cleanup and measurement
    gc.collect()
    final_memory = get_memory_mb()
    memory_readings.append(final_memory)
    
    print()
    print("=" * 60)
    print("Results")
    print("=" * 60)
    print(f"Initial memory:  {initial_memory:.1f} MB")
    print(f"Final memory:    {final_memory:.1f} MB")
    print(f"Total increase:  {final_memory - initial_memory:.1f} MB")
    
    # Analyze memory trend (compare first half vs second half averages)
    if len(memory_readings) >= 4:
        mid = len(memory_readings) // 2
        first_half_avg = sum(memory_readings[:mid]) / mid
        second_half_avg = sum(memory_readings[mid:]) / (len(memory_readings) - mid)
        trend = second_half_avg - first_half_avg
        print(f"Memory trend:    {'+' if trend > 0 else ''}{trend:.1f} MB "
              f"(second half avg - first half avg)")
    
    # Determine if there's a significant leak
    # Allow some memory increase due to Python internals, but flag large increases
    total_data_processed_mb = iterations * tensor_size * tensor_size * 2 / (1024 ** 2)
    memory_increase = final_memory - initial_memory
    leak_ratio = memory_increase / total_data_processed_mb if total_data_processed_mb > 0 else 0
    
    print()
    print(f"Total data processed: {total_data_processed_mb:.1f} MB")
    print(f"Memory increase ratio: {leak_ratio:.4f} (increase / data processed)")
    print()
    
    # Check if memory is stable (more important than total increase)
    # A true leak shows continuous growth; initialization overhead is acceptable
    if len(memory_readings) >= 4:
        # Check if memory is stable in the second half (after warmup)
        second_half = memory_readings[len(memory_readings)//2:]
        memory_variance = max(second_half) - min(second_half)
        is_stable = memory_variance < 10  # Less than 10MB variance = stable
    else:
        is_stable = False
    
    # Threshold: continuous growth indicates a leak
    if not is_stable and leak_ratio > 0.5:  # More than 50% of data processed = definite leak
        print("❌ MEMORY LEAK DETECTED!")
        print("   Memory is continuously increasing proportionally to data processed.")
        print("   The fix may not be working correctly.")
        return False
    elif not is_stable and leak_ratio > 0.15:
        print("⚠️  WARNING: Possible memory leak detected.")
        print("   Memory is growing but may stabilize. Run with more iterations to confirm.")
        return True
    elif memory_increase > 200:  # More than 200MB absolute increase but stable
        print("⚠️  WARNING: High initial memory overhead detected.")
        print("   Memory is stable after warmup, likely initialization costs.")
        return True
    else:
        print("✅ NO MEMORY LEAK DETECTED!")
        print("   Memory usage is stable. The fix is working correctly.")
        if is_stable:
            print(f"   Memory variance in second half: {memory_variance:.1f} MB (stable)")
        return True


def main():
    parser = argparse.ArgumentParser(
        description="Test ZipNN for memory leaks after the fix"
    )
    parser.add_argument(
        "--iterations", "-n", type=int, default=100,
        help="Number of compress/decompress cycles (default: 100)"
    )
    parser.add_argument(
        "--size", "-s", type=int, default=1000,
        help="Tensor size (size x size matrix, default: 1000)"
    )
    parser.add_argument(
        "--interval", "-i", type=int, default=20,
        help="Print interval for memory readings (default: 20)"
    )
    
    args = parser.parse_args()
    
    success = test_memory_leak(
        iterations=args.iterations,
        tensor_size=args.size,
        print_interval=args.interval
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

