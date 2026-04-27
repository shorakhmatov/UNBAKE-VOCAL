"""Evaluation metrics for speech recognition."""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

import numpy as np
from jiwer import wer, cer

from recognizers import RecognitionResult, WordTimestamp
from config import MAX_CER_THRESHOLD, MAX_WER_THRESHOLD, MAX_TIMESTAMP_ERROR_MS


@dataclass
class TimestampAccuracy:
    """Timestamp accuracy metrics."""
    mean_absolute_error_ms: float
    max_error_ms: float
    within_threshold_pct: float  # Percentage of words within threshold
    alignment_score: float  # Overall alignment quality 0-1


@dataclass
class EvaluationMetrics:
    """Complete evaluation results."""
    # Text accuracy
    wer: float  # Word Error Rate
    cer: float  # Character Error Rate
    
    # Timestamp accuracy
    timestamp_accuracy: Optional[TimestampAccuracy] = None
    
    # Additional metrics
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    
    # Quality flags
    passed_cer: bool = False
    passed_wer: bool = False
    passed_timestamps: bool = False
    overall_passed: bool = False
    
    # Details
    missing_words: List[str] = field(default_factory=list)
    hallucinated_words: List[str] = field(default_factory=list)
    substitutions: List[Tuple[str, str]] = field(default_factory=list)


class TextNormalizer:
    """Normalize text for comparison."""
    
    @staticmethod
    def normalize(text: str) -> str:
        """Apply full normalization."""
        # Lowercase
        text = text.lower()
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove punctuation but keep alphanumeric and spaces
        text = re.sub(r'[^\w\s]', '', text)
        return text.strip()
    
    @staticmethod
    def normalize_keep_punctuation(text: str) -> str:
        """Normalize but keep punctuation for structure."""
        text = text.lower()
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


class RecognitionEvaluator:
    """Evaluate speech recognition results."""
    
    def __init__(self):
        self.normalizer = TextNormalizer()
    
    def evaluate(
        self,
        result: RecognitionResult,
        ground_truth_text: str,
        ground_truth_timestamps: Optional[List[Tuple[float, str]]] = None
    ) -> EvaluationMetrics:
        """
        Evaluate recognition result against ground truth.
        
        Args:
            result: Recognition result
            ground_truth_text: Expected text
            ground_truth_timestamps: Optional list of (timestamp, word) tuples
            
        Returns:
            EvaluationMetrics
        """
        # Normalize texts
        pred_text_norm = self.normalizer.normalize(result.text)
        true_text_norm = self.normalizer.normalize(ground_truth_text)
        
        # Calculate WER and CER
        metrics_wer = wer(true_text_norm, pred_text_norm)
        metrics_cer = cer(true_text_norm, pred_text_norm)
        
        # Analyze differences
        missing, hallucinated, substitutions = self._analyze_differences(
            true_text_norm, pred_text_norm
        )
        
        # Calculate precision/recall
        true_words = set(true_text_norm.split())
        pred_words = set(pred_text_norm.split())
        
        if len(pred_words) > 0:
            precision = len(true_words & pred_words) / len(pred_words)
        else:
            precision = 0.0
        
        if len(true_words) > 0:
            recall = len(true_words & pred_words) / len(true_words)
        else:
            recall = 0.0
        
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        # Evaluate timestamps if ground truth provided
        timestamp_acc = None
        if ground_truth_timestamps:
            timestamp_acc = self._evaluate_timestamps(
                result.words, ground_truth_timestamps
            )
        
        # Determine pass/fail
        passed_cer = metrics_cer <= MAX_CER_THRESHOLD
        passed_wer = metrics_wer <= MAX_WER_THRESHOLD
        passed_timestamps = (
            timestamp_acc is None or 
            timestamp_acc.within_threshold_pct >= 0.8  # 80% words within threshold
        )
        
        overall_passed = passed_cer and passed_wer and passed_timestamps
        
        return EvaluationMetrics(
            wer=metrics_wer,
            cer=metrics_cer,
            timestamp_accuracy=timestamp_acc,
            precision=precision,
            recall=recall,
            f1_score=f1,
            passed_cer=passed_cer,
            passed_wer=passed_wer,
            passed_timestamps=passed_timestamps,
            overall_passed=overall_passed,
            missing_words=missing,
            hallucinated_words=hallucinated,
            substitutions=substitutions
        )
    
    def _analyze_differences(
        self, 
        true_text: str, 
        pred_text: str
    ) -> Tuple[List[str], List[str], List[Tuple[str, str]]]:
        """
        Analyze differences between true and predicted text.
        
        Returns:
            Tuple of (missing_words, hallucinated_words, substitutions)
        """
        true_words = true_text.split()
        pred_words = pred_text.split()
        
        # Simple diff - can be improved with proper sequence alignment
        from difflib import SequenceMatcher
        
        matcher = SequenceMatcher(None, true_words, pred_words)
        
        missing = []
        hallucinated = []
        substitutions = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'delete':
                missing.extend(true_words[i1:i2])
            elif tag == 'insert':
                hallucinated.extend(pred_words[j1:j2])
            elif tag == 'replace':
                # Potential substitution
                for tw, pw in zip(true_words[i1:i2], pred_words[j1:j2]):
                    substitutions.append((tw, pw))
        
        return missing, hallucinated, substitutions
    
    def _evaluate_timestamps(
        self,
        pred_words: List[WordTimestamp],
        ground_truth: List[Tuple[float, str]]
    ) -> TimestampAccuracy:
        """
        Evaluate timestamp accuracy.
        
        Args:
            pred_words: Predicted words with timestamps
            ground_truth: List of (timestamp, word) tuples
            
        Returns:
            TimestampAccuracy metrics
        """
        if not pred_words or not ground_truth:
            return TimestampAccuracy(0, 0, 0, 0)
        
        # Match predicted words to ground truth
        errors = []
        matched = 0
        
        gt_idx = 0
        pred_idx = 0
        
        while gt_idx < len(ground_truth) and pred_idx < len(pred_words):
            gt_time, gt_word = ground_truth[gt_idx]
            pred_word = pred_words[pred_idx]
            
            # Simple matching by word similarity
            gt_word_norm = self.normalizer.normalize(gt_word)
            pred_word_norm = self.normalizer.normalize(pred_word.word)
            
            if gt_word_norm == pred_word_norm or self._word_similarity(gt_word_norm, pred_word_norm) > 0.8:
                error_ms = abs(pred_word.start - gt_time) * 1000
                errors.append(error_ms)
                matched += 1
                gt_idx += 1
                pred_idx += 1
            else:
                # Skip to find match
                pred_idx += 1
        
        if not errors:
            return TimestampAccuracy(0, 0, 0, 0)
        
        mean_error = np.mean(errors)
        max_error = np.max(errors)
        within_threshold = sum(1 for e in errors if e <= MAX_TIMESTAMP_ERROR_MS)
        within_pct = within_threshold / len(errors) if errors else 0
        
        # Alignment score based on mean error
        alignment_score = max(0, 1 - (mean_error / 1000))  # 0 at 1s error, 1 at 0 error
        
        return TimestampAccuracy(
            mean_absolute_error_ms=mean_error,
            max_error_ms=max_error,
            within_threshold_pct=within_pct,
            alignment_score=alignment_score
        )
    
    def _word_similarity(self, w1: str, w2: str) -> float:
        """Calculate word similarity using Levenshtein ratio."""
        try:
            from Levenshtein import ratio
            return ratio(w1, w2)
        except ImportError:
            # Fallback to simple ratio
            if len(w1) == 0 and len(w2) == 0:
                return 1.0
            if len(w1) == 0 or len(w2) == 0:
                return 0.0
            
            matches = sum(c1 == c2 for c1, c2 in zip(w1, w2))
            return 2 * matches / (len(w1) + len(w2))


class BatchEvaluator:
    """Evaluate multiple recognition results."""
    
    def __init__(self):
        self.evaluator = RecognitionEvaluator()
        self.results = []
    
    def add_result(self, metrics: EvaluationMetrics, file_name: str, model_name: str):
        """Add evaluation result."""
        self.results.append({
            "file": file_name,
            "model": model_name,
            "metrics": metrics
        })
    
    def get_summary(self) -> Dict:
        """Get summary statistics."""
        if not self.results:
            return {}
        
        wers = [r["metrics"].wer for r in self.results]
        cers = [r["metrics"].cer for r in self.results]
        passed = [r["metrics"].overall_passed for r in self.results]
        
        summary = {
            "total_files": len(self.results),
            "mean_wer": np.mean(wers),
            "median_wer": np.median(wers),
            "std_wer": np.std(wers),
            "mean_cer": np.mean(cers),
            "median_cer": np.median(cers),
            "std_cer": np.std(cers),
            "pass_rate": sum(passed) / len(passed) if passed else 0,
            "models_used": list(set(r["model"] for r in self.results))
        }
        
        # Group by model
        by_model = defaultdict(list)
        for r in self.results:
            by_model[r["model"]].append(r["metrics"])
        
        summary["by_model"] = {}
        for model, metrics_list in by_model.items():
            summary["by_model"][model] = {
                "mean_wer": np.mean([m.wer for m in metrics_list]),
                "mean_cer": np.mean([m.cer for m in metrics_list]),
                "pass_rate": sum(m.overall_passed for m in metrics_list) / len(metrics_list)
            }
        
        return summary
    
    def export_results(self, output_path: str):
        """Export results to JSON."""
        import json
        
        data = {
            "summary": self.get_summary(),
            "results": [
                {
                    "file": r["file"],
                    "model": r["model"],
                    "wer": r["metrics"].wer,
                    "cer": r["metrics"].cer,
                    "precision": r["metrics"].precision,
                    "recall": r["metrics"].recall,
                    "f1": r["metrics"].f1_score,
                    "passed": r["metrics"].overall_passed,
                    "missing_words": r["metrics"].missing_words[:10],  # Limit
                    "hallucinated_words": r["metrics"].hallucinated_words[:10]
                }
                for r in self.results
            ]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Results exported to {output_path}")
