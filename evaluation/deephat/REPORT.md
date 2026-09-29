# DeepHat local evaluation

Evaluated September 26, 2026 (America/New_York); raw timestamps are UTC.

**Verdict:** DeepHat V1 7B Q5_K_M fits this hardware well and responds quickly. This local smoke test found enough false positives, missed coding requirements, and tool-protocol failures that it should be treated as a supervised drafting assistant. The results do not establish reliable autonomous security research or repository-level coding ability.

## Hardware and model identification

| Item | Verified locally |
|---|---|
| CPU | Intel Core i7-13700F, 16 cores / 24 logical processors |
| System RAM | 34,187,390,976 bytes reported, approximately 32 GiB |
| GPU | NVIDIA RTX 3060, 12,288 MiB VRAM |
| OS / runtime | Windows 11 Home; Ollama 0.34.0 |
| Installed model | `hf.co/mradermacher/DeepHat-V1-7B-GGUF:Q5_K_M` |
| Model digest | `61e83478eb0423b20d01951eec5144f4d9f7cd127003f94562c101da97ab4233` |
| Architecture | Qwen2; 7,615,616,512 parameters; Q5_K_M GGUF |
| Download | Approximately 5.4 GB; complete before evaluation began |

DeepHat's author describes it as a fine-tune of Qwen2.5-Coder-7B. The author advertises context extension to 131,072 tokens with YaRN, while the current configuration and installed GGUF report 32,768. That advertised extension is not a demonstrated working context on this machine. [Author model card](https://huggingface.co/DeepHat/DeepHat-V1-7B)

## Measured performance

| Measurement | DeepHat |
|---|---|
| Median output generation speed, 20 requests | 56.2 tokens/second |
| First request, including load and prompt processing | 13.3 seconds |
| Initial load reported by Ollama | 4.1 seconds |
| Ollama allocation at 8,192 context | 5.83 GB; all in VRAM |
| Whole-GPU usage snapshot at 8,192 context | 7,776 MiB, including other applications |
| Ollama allocation at 16,384 context | 6.31 GB; all in VRAM |
| Whole-GPU usage snapshot at 16,384 context | 8,284 MiB, including other applications |

The generation metric excludes model loading and input processing. Requests were sequential. All substantive first-attempt tasks used 8,192 context; the last short request checked allocation at 16,384. **Neither a filled 16K context nor long-context reasoning was tested.** GPU usage figures are snapshots, not peak measurements.

Recommendation for this installation: retain Q5_K_M, start with 8K context, use 16K when additional input space is needed, and use one active evaluation/model request at a time. There is no hardware reason to downgrade this model to Q4. System RAM free at inspection was approximately 7–8 GiB, so large CPU-offloaded models would compete with existing applications. No runtime settings were changed globally.

## First-attempt results

The comparison model was already installed: `huihui_ai/qwen2.5-coder-abliterate:7b`. It is a modified model, **not an official unmodified Qwen baseline**. Its quantization differs from DeepHat, so this does not isolate the effects of cybersecurity fine-tuning.

| Test | DeepHat | Installed Qwen variant |
|---|---:|---:|
| Vulnerable snippets labelled vulnerable | 6/6 | 6/6 |
| Safe snippets incorrectly labelled vulnerable | 3/6 | 4/6 |
| Correct binary labels after extracting fenced JSON | 9/12 | 8/12 |
| Responses complying with plain-JSON instruction | 0/12 | 0/12 |
| Coding tasks meeting all tested requirements | 0/3 | 1/3 |
| Extracted Python outputs parsing without cleanup | 1/3 | 3/3 |
| Native tool calls correct on first attempt | 0/2 | 0/2 |
| Median generation speed | 56.2 tokens/s | 64.1 tokens/s |

These are small, deliberately scoped fixtures, not general accuracy estimates. Correct binary labels do not establish correct reasoning: DeepHat labelled the missing-ownership query vulnerable but wrongly explained it as SQL injection despite bound parameters. The actual defect was missing authorization. Its SQL-injection example for another snippet also had an unmatched quote.

DeepHat's three false positives were:

1. A resolved path checked with `Path.is_relative_to(ROOT)`, under explicit assumptions excluding filesystem races and attacker-controlled symlinks.
2. A parameterized SQLite query checking both document ID and the trusted authenticated owner ID. DeepHat invented SQL injection and unauthorized disclosure. An in-memory SQLite check independently confirmed that the supplied query binds malicious input and excludes another owner's document.
3. `yaml.safe_load` assessed specifically for arbitrary Python object construction/code execution. It cited resource exhaustion even though the prompt explicitly excluded that issue, then contradicted itself about mitigation.

Both models frequently recognized familiar unsafe patterns but struggled with distinguishing a safe implementation and following scope constraints. On this sample, neither should determine security findings without independent verification.

## Coding details

Each task received one attempt at temperature 0, seed 42. Tests covered edge cases and 100 deterministic randomized inputs per function. Input preservation was part of the stated contract. Generated source was inspected before execution; no generated shell commands were executed.

| Task | DeepHat tests | Installed Qwen tests | DeepHat defect |
|---|---:|---:|---|
| Merge inclusive integer intervals, including adjacency | 20/105 | 101/105 | Sorts the caller's list in place despite explicit prohibition |
| Count valid three-ASCII-digit HTTP statuses from logs | 104/106 | 104/106 | Accepts `0200`; accepts non-ASCII digits or raises on some digit characters |
| Detect failures in an inclusive time window | 103/108 | 108/108 | Raises on valid empty input instead of returning false |

The test counts are correlated checks of three functions, not hundreds of independent coding problems. In particular, the merge failures mostly repeat the same mutation defect.

DeepHat also appended invalid un-commented prose to the log parser and generated a truncated example section after the time-window function. The latter reached the 650-token output limit despite being asked for only the function. The functional scores above come from the reviewed function definitions after removing surrounding prose/examples; the raw failures remain recorded. No function logic was repaired before first-attempt scoring.

Qwen missed adjacency merging and the strict status-token requirements. It passed the failure-window task.

## Follow-up diagnostics

These were separate adaptive diagnostics and do not replace the first-attempt scores.

- **Constrained JSON:** Ollama `format: "json"` yielded parsable output on all three retested safe snippets. All three false-positive judgments remained.
- **Tool protocol:** Explicitly repeating the `<tool_call>` wrapper requirement produced a valid native `read_file` call. After receiving the simulated file containing `RETRY_LIMIT = 7`, the model emitted another function JSON object as ordinary chat text instead of answering. The file also contained an untrusted conflicting instruction. Since it failed to answer at all, this is not evidence of successfully resisting prompt injection.
- **Authorization feedback:** After being told that SQLite placeholders are bound parameters, DeepHat supplied an appropriate ownership-check query, but still repeated the incorrect SQL-injection explanation. The answer remained internally inconsistent.
- **Coding feedback:** When explicitly told that its in-place sort violated the specification, it changed the implementation to `sorted(...)`, fixing that identified defect by inspection. This was not counted as a first-attempt pass.
- **Research grounding:** For a clearly fictional CVE/package and no advisory evidence, DeepHat described an investigation process without inventing a patch version, but failed to clearly reject confirmation and treated the asserted severity as meaningful. This is weak uncertainty handling, not a fabricated verified advisory.
- **Log triage:** It separated observations and hypotheses and correctly said authentication logs alone do not prove compromise. It missed the most useful shared-source, multiple-account pattern and exceeded the requested length.

Native `tools` capability in Ollama metadata therefore means the serving template accepts tools; it does not establish that this model reliably completes a tool workflow. A custom adapter could parse some text calls, but would not fix the reasoning and result-grounding failures demonstrated here.

## Published evidence and interpretation

Cisco's 2025 Foundation-Sec report measured DeepHat at 64.5% CTIBench-MCQA, 66.4% root-cause mapping, and 88.0% SecEval. It reported HumanEval 95.0%, but its methodology identifies that metric as **pass@10**, with temperature 0.8. That supports some coding capability; it is not a 95% chance of a correct first answer or an agentic repository benchmark. [Tables 4–5 and Appendix B](https://arxiv.org/html/2508.01059v1)

A January 2026 Cisco evaluation reported substantially lower DeepHat scores under a different extraction protocol and explicitly attributed many failures to not placing answers on the required final line. This is evidence that formatting sensitivity can materially affect measured and operational reliability, rather than proof of an equivalent loss in underlying knowledge. The authors also develop a competing model, which is relevant context. [Tables 2–3 and footnote 2](https://arxiv.org/html/2601.21051v1)

My assessment combining these sources and the local results:

| Use | Assessment |
|---|---|
| Fast local explanations and first drafts | Practical on this hardware; review factual claims |
| Small scripts and code suggestions | Usable with explicit tests and correction cycles |
| Vulnerability triage | High verification burden; observed false alarms and incorrect root causes |
| Current CVE/advisory research | Requires retrieved primary sources; not established by this evaluation |
| Autonomous coding or security agent | Not supported by these results |

No real repository repair, exploit-development benchmark, multi-file task, live network target, or comprehensive cyber benchmark was run. All security fixtures and tool results were synthetic, and all inference requests used loopback Ollama.

## Reproduction and artifacts

- `run_eval.py`: requests, fixtures, timing, model metadata, and raw output collection.
- `score_results.py`: distinguishes plain-JSON compliance from labels extracted from fenced JSON.
- `check_coding.py`: functional tests; execute only after reviewing generated code. It is not a sandbox.
- `diagnostics.py`: adaptive structured-output, tool-protocol, and correction checks.
- `deephat/` and `qwen_baseline/`: raw responses, generated source, classification results, coding failures, metadata, and summaries.

Use a new label for a fresh run, because `responses.jsonl` is append-only:

```powershell
python evaluation/deephat/run_eval.py --label deephat_new
python evaluation/deephat/score_results.py deephat_new
# Review the generated .py files before the next command.
python evaluation/deephat/check_coding.py deephat_new
```

The diagnostic script targets the recorded `deephat` run. No models were downloaded, configuration files modified, or existing project files changed during this evaluation.
