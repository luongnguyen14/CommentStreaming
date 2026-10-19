# Model Trial Report (prototype)

Generated at **2026-10-19T11:43:52+07:00** by `src/app/model_trial.py`.

- Command: `bash scripts/run_model_trial.sh --test-sample 200`
- Model: **LogisticRegression** (saved 2026-10-15T00:05:05, Spark 3.5.9)
- Evaluation split: **test** — deterministic sample ordered by `crc32(comment_id)`
- Sample size: **200** comments

> This program is a **model trial / prototype**, not the complete application.
> It runs the same text-cleaning function and the same saved `PipelineModel`
> used by the streaming job. It does not use Kafka or the dashboard.

## 1. Metrics on the sample

| Metric | Value |
|---|---:|
| Accuracy | 0.7200 |
| Macro-F1 | 0.6317 |
| Weighted-F1 | 0.7380 |

## 2. Per-class metrics

| Label | Precision | Recall | F1 | Support | Share |
|---|---:|---:|---:|---:|---:|
| negative | 0.6230 | 0.7600 | 0.6847 | 50 | 25.00% |
| neutral | 0.3158 | 0.4615 | 0.3750 | 26 | 13.00% |
| positive | 0.9307 | 0.7581 | 0.8356 | 124 | 62.00% |

## 3. Confusion matrix (rows = true, columns = predicted)

| true \ predicted | negative | neutral | positive |
|---|---:|---:|---:|
| **negative** | 38 | 11 | 1 |
| **neutral** | 8 | 12 | 6 |
| **positive** | 15 | 15 | 94 |

## 4. Example predictions (first 8)

_Text is not included (`--keep-text` was not passed). Only aggregate results and label counts are stored._

| # | comment_id | True | Predicted | Confidence |
|---:|---|---|---|---:|
| 1 | rw0973879 | positive | positive | 49.8% |
| 2 | rw0981745 | neutral | neutral | 72.6% |
| 3 | rw0982704 | positive | neutral | 61.6% |
| 4 | rw1990828 | positive | positive | 94.7% |
| 5 | rw1999197 | negative | negative | 90.4% |
| 6 | rw2479709 | negative | negative | 98.8% |
| 7 | rw2484451 | neutral | neutral | 53.9% |
| 8 | rw2486899 | positive | positive | 85.5% |

## 5. Caveats — read before citing these numbers

1. **Labels are inferred from IMDb ratings** (1–4 negative, 5–6 neutral, 7–10 positive),
   not human sentiment annotations. The `neutral` class is noisy; its F1 is the weakest.
2. **The saved model was trained on the 20% deterministic subset** used in Task 7
   (129,701 training rows). `config.yaml` now defaults to 64% for future
   retraining, but the model used here was **not** retrained on 64%.
3. **The test split was already used once** for the final evaluation
   (`outputs/tables/test_eval_log.csv`). This run re-evaluates the frozen model on a
   deterministic sample; it was **not** used to select or tune the model.
4. **IMDb reviews are not live-stream comments.** The macro-F1 in this report must not
   be promised for real livestream data. See `outputs/modeling_summary.md` §5.
5. The sample has 200 rows, so sampling error applies; no confidence interval or
   statistical significance test was computed.

## 6. Reproduce

```bash
bash scripts/run_model_trial.sh --test-sample 200
```
