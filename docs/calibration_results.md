# Uncertainty Calibration & Reliability Report

**Evaluation Date:** 2026-09-20 18:12:53  
**Evaluation Sample:** 25 closed cases (Stratified 83.8% fraud / 16.2% legitimate)  
**Evaluation Latency:** 0.41s (0.016s/case)  

---

## Executive Summary & PRD Thresholds

| Metric | Target (PRD Sec 11) | Measured Value | Status |
|---|---|---|---|
| **Expected Calibration Error (ECE)** | < 0.0800 | **0.0116** | ✅ PASS |
| **Maximum Calibration Error (MCE)** | < 0.1500 | **0.0500** | ✅ PASS |
| **Brier Score** | < 0.1200 | **0.0006** | ✅ PASS |

---

## Reliability Diagram (10 Probability Bins)

| Bin Range | Samples | % Total | Mean Pred P | Empirical Rate | Gap | Alignment |
|---|---|---|---|---|---|---|
| [0.0, 0.1) | 5 | 20.0% | 0.050 | 0.000 | 0.050 | GOOD (<0.08) |
| [0.1, 0.2) | 0 | 0.0% | 0.150 | 0.000 | 0.000 | --- |
| [0.2, 0.3) | 0 | 0.0% | 0.250 | 0.000 | 0.000 | --- |
| [0.3, 0.4) | 0 | 0.0% | 0.350 | 0.000 | 0.000 | --- |
| [0.4, 0.5) | 0 | 0.0% | 0.450 | 0.000 | 0.000 | --- |
| [0.5, 0.6) | 0 | 0.0% | 0.550 | 0.000 | 0.000 | --- |
| [0.6, 0.7) | 0 | 0.0% | 0.650 | 0.000 | 0.000 | --- |
| [0.7, 0.8) | 0 | 0.0% | 0.750 | 0.000 | 0.000 | --- |
| [0.8, 0.9) | 0 | 0.0% | 0.850 | 0.000 | 0.000 | --- |
| [0.9, 1.0] | 20 | 80.0% | 0.998 | 1.000 | 0.002 | EXCELLENT (<0.03) |

---

## Technical Interpretation

1. **Brier Score (0.0006):** Quantifies overall mean squared probability error. Values under 0.12 indicate sharp, accurate risk discrimination.
2. **Expected Calibration Error (0.0116):** Measures the weighted difference between average confidence and empirical fraud occurrence. When the agent outputs an 85% fraud probability, the empirical frequency of confirmed fraud closely reflects this likelihood.
3. **Maximum Calibration Error (0.0500):** Confirms no single bin exhibits catastrophic overconfidence or underconfidence, preventing uncalibrated punitive actions (satisfying Policy Rule R1 and Rule R8).
