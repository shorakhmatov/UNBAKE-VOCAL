#!/usr/bin/env python3
"""
Evaluation script for Vocal Recognition API.
Tests STT models and reports WER/CER metrics.
"""

import json
import time
import argparse
from pathlib import Path
from typing import Dict

from src.config import TEST_DATA_DIR, RESULTS_DIR
from src.recognizers import get_recognizer
from src.evaluator import RecognitionEvaluator, BatchEvaluator


# Ground truth - add your test files here
TEST_GROUND_TRUTH: Dict[str, Dict] = {}


def check_gpu():
    """Check if GPU is available."""
    try:
        import torch
        if torch.cuda.is_available():
            print(f"✓ GPU available: {torch.cuda.get_device_name(0)}")
            print(f"  CUDA version: {torch.version.cuda}")
            print(f"  Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
            return True
        else:
            print("⚠ No GPU available, using CPU (will be slower)")
            return False
    except ImportError:
        print("⚠ PyTorch not installed")
        return False


def test_single_recognizer(
    recognizer_type: str,
    model_size: str,
    test_files: Dict[str, Dict],
    device: str = "auto"
) -> Dict:
    """
    Test a single recognizer on test files.
    
    Args:
        recognizer_type: Type of recognizer
        model_size: Model size
        test_files: Dictionary of test files with ground truth
        device: Device to use
        
    Returns:
        Dictionary with results
    """
    print(f"\n{'='*60}")
    print(f"Testing: {recognizer_type} ({model_size})")
    print(f"{'='*60}")
    
    # Initialize recognizer
    try:
        recognizer = get_recognizer(recognizer_type, model_size, device)
        print(f"Loading model...")
        recognizer.load_model()
        print(f"✓ Model loaded successfully")
    except Exception as e:
        print(f"✗ Failed to load model: {e}")
        return {"error": str(e)}
    
    # Initialize evaluator
    evaluator = RecognitionEvaluator()
    batch_eval = BatchEvaluator()
    
    # Process each test file
    results = []
    total_time = 0
    
    for file_key, ground_truth in test_files.items():
        print(f"\nProcessing: {file_key}")
        
        # Check if file exists
        audio_path = TEST_DATA_DIR / f"{file_key}.m4a"
        if not audio_path.exists():
            audio_path = TEST_DATA_DIR / f"{file_key}.wav"
        if not audio_path.exists():
            audio_path = TEST_DATA_DIR / f"{file_key}.mp3"
        
        if not audio_path.exists():
            print(f"  ⚠ File not found: {audio_path}")
            continue
        
        try:
            # Transcribe
            start = time.time()
            result = recognizer.transcribe(
                str(audio_path),
                language=ground_truth.get("language")
            )
            elapsed = time.time() - start
            total_time += elapsed
            
            print(f"  Duration: {result.duration:.1f}s")
            print(f"  Processing time: {elapsed:.1f}s")
            print(f"  RTF: {elapsed / result.duration:.2f}x")
            print(f"  Detected language: {result.language}")
            print(f"  Words detected: {len(result.words)}")
            
            # Evaluate
            metrics = evaluator.evaluate(result, ground_truth["text"])
            batch_eval.add_result(metrics, file_key, recognizer.model_name)
            
            print(f"  WER: {metrics.wer:.2%}")
            print(f"  CER: {metrics.cer:.2%}")
            print(f"  F1: {metrics.f1_score:.2%}")
            print(f"  Status: {'✓ PASS' if metrics.overall_passed else '✗ FAIL'}")
            
            if metrics.hallucinated_words:
                print(f"  Hallucinations: {metrics.hallucinated_words[:3]}")
            
            results.append({
                "file": file_key,
                "result": result,
                "metrics": metrics
            })
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Get summary
    summary = batch_eval.get_summary()
    
    print(f"\n{'='*60}")
    print(f"Summary for {recognizer.model_name}")
    print(f"{'='*60}")
    print(f"Files processed: {summary.get('total_files', 0)}")
    print(f"Mean WER: {summary.get('mean_wer', 0):.2%}")
    print(f"Mean CER: {summary.get('mean_cer', 0):.2%}")
    print(f"Pass rate: {summary.get('pass_rate', 0):.1%}")
    print(f"Total time: {total_time:.1f}s")
    
    # Estimate cost
    total_duration = sum(r["result"].duration for r in results)
    rtf = total_time / total_duration if total_duration > 0 else 0
    
    # Rough cost estimation (GPU time)
    # AWS g4dn.xlarge ~ $0.526/hour = $0.000146/s
    gpu_cost_per_second = 0.000146
    est_cost_per_3min = rtf * 180 * gpu_cost_per_second
    
    print(f"\nCost Estimation:")
    print(f"  RTF (Real-Time Factor): {rtf:.2f}x")
    print(f"  Est. cost per 3min track: ${est_cost_per_3min:.4f}")
    print(f"  Target: <$0.05, Result: {'✓ PASS' if est_cost_per_3min < 0.05 else '✗ FAIL'}")
    
    return {
        "recognizer": recognizer_type,
        "model": model_size,
        "summary": summary,
        "rtf": rtf,
        "est_cost_per_3min": est_cost_per_3min,
        "results": results
    }


def compare_recognizers(device: str = "auto"):
    """Compare different recognizers."""
    print("\n" + "="*70)
    print("RECOGNIZER COMPARISON")
    print("="*70)
    
    # Test configurations
    configs = [
        ("faster-whisper", "large-v3"),
        ("whisper-timestamped", "large-v3"),
        # ("whisperx", "large-v3"),  # Commented out - requires more setup
    ]
    
    all_results = []
    
    for recognizer_type, model_size in configs:
        try:
            result = test_single_recognizer(
                recognizer_type,
                model_size,
                TEST_GROUND_TRUTH,
                device
            )
            all_results.append(result)
        except Exception as e:
            print(f"\n✗ Failed to test {recognizer_type}: {e}")
    
    # Comparison summary
    print("\n" + "="*70)
    print("COMPARISON SUMMARY")
    print("="*70)
    print(f"{'Model':<25} {'WER':>8} {'CER':>8} {'Pass':>8} {'RTF':>8} {'Cost/3min':>12}")
    print("-" * 70)
    
    for r in all_results:
        if "error" in r:
            continue
        summary = r.get("summary", {})
        print(f"{r['model']:<25} "
              f"{summary.get('mean_wer', 0):>7.1%} "
              f"{summary.get('mean_cer', 0):>7.1%} "
              f"{summary.get('pass_rate', 0):>7.1%} "
              f"{r.get('rtf', 0):>7.2f}x "
              f"${r.get('est_cost_per_3min', 0):>10.4f}")
    
    # Save results
    output_file = RESULTS_DIR / "comparison_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        # Convert to serializable format
        serializable = []
        for r in all_results:
            if "error" in r:
                continue
            serializable.append({
                "recognizer": r["recognizer"],
                "model": r["model"],
                "summary": r["summary"],
                "rtf": r["rtf"],
                "est_cost_per_3min": r["est_cost_per_3min"]
            })
        json.dump(serializable, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    
    # Recommendation
    print("\n" + "="*70)
    print("RECOMMENDATION")
    print("="*70)
    
    valid_results = [r for r in all_results if "error" not in r]
    if valid_results:
        # Find best by combined score (accuracy * cost_efficiency)
        def score(r):
            acc = 1 - r["summary"].get("mean_wer", 1)
            cost_eff = min(1.0, 0.05 / max(r["est_cost_per_3min"], 0.001))
            return acc * cost_eff
        
        best = max(valid_results, key=score)
        print(f"Recommended: {best['recognizer']} ({best['model']})")
        print(f"  WER: {best['summary'].get('mean_wer', 0):.2%}")
        print(f"  Cost: ${best['est_cost_per_3min']:.4f} per 3min")
        print(f"  Reason: Best accuracy/cost ratio")


def main():
    parser = argparse.ArgumentParser(description="Evaluate Vocal Recognition Models")
    parser.add_argument(
        "--device",
        choices=["cuda", "cpu", "auto"],
        default="auto",
        help="Device to use for inference"
    )
    parser.add_argument(
        "--model",
        default="large-v3",
        help="Whisper model size"
    )
    parser.add_argument(
        "--recognizer",
        choices=["whisper", "faster-whisper", "whisper-timestamped", "whisperx"],
        default="faster-whisper",
        help="Recognizer type"
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run comparison of all recognizers"
    )
    
    args = parser.parse_args()
    
    # Check GPU
    has_gpu = check_gpu()
    if args.device == "cuda" and not has_gpu:
        print("Warning: CUDA requested but not available, falling back to CPU")
        args.device = "cpu"
    
    print(f"\nTest data directory: {TEST_DATA_DIR}")
    print(f"Results directory: {RESULTS_DIR}")
    
    # Create directories
    TEST_DATA_DIR.mkdir(exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)
    
    if args.compare:
        compare_recognizers(args.device)
    else:
        result = test_single_recognizer(
            args.recognizer,
            args.model,
            TEST_GROUND_TRUTH,
            args.device
        )
        
        # Save results
        output_file = RESULTS_DIR / f"{args.recognizer}_{args.model}_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
