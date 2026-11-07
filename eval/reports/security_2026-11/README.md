# Security and grounding, 2026-11-07 to 2026-11-08

Attacks hidden in uploaded documents, direct prompt injection, citation checks, static analysis, dependencies, and whether the
product reaches the internet. Public benchmarks are scored with their own data and stated adaptations; the project's own question
sets are labelled as such and are not benchmark results. Model: Qwen3 8B on an RTX 4050 (6 GB), everything local.

## Attacks hidden in documents (BIPIA)

BIPIA's EmailQA test emails with one of its text attacks inserted at the start, middle or end. The email is ingested with the
product's chunker and BIPIA's question is asked about it through the product's own pipeline. Only the six attack types a rule can
judge are used (30 attack strings), because BIPIA scores the rest with a paid GPT-4 judge. 120 samples per run, judged against the
email before the attack was inserted. Harness: `eval/security/bipia_attack.py`.

| Run | Sample | Attacks followed | Answers from the model / quoted text |
|---|---|---|---|
| Before any change | seed 20261107 | 19.2% [12.5, 25.8] | 11 / 109 |
| Correct short answers kept | seed 20261107 | 11.7% [6.7, 17.5] | 73 / 47 |
| Document text marked as data, reply instructions kept out of quotes | seed 20261107 | 0.8% [0, 2.5] | 71 / 49 |
| **Same code, fresh sample** | **seed 20261108, no overlap** | **0.8% [0, 2.5]** | **67 / 53** |

- The defences were designed after reading the first sample's failures, so the third row is optimistic. The fresh sample, drawn
  from attacks the first one didn't use, is the clean figure.
- Most early failures weren't the model obeying: the quoted-text fallback copied the injected advert or scam line into the answer.
  The fix keeps the model's answer when it is grounded and strips lines that address "your reply" from quoted text.
- The one attack still followed asked for the answer in French, and got it.
- The share of quoted-text answers barely moved between the last three rows, so the drop isn't from refusing more.
- A first attempt was refused 103 times in 120 by the retrieval confidence gate and measured nothing; it is kept as
  `bipia_attempt_gate_refused.json`. The gate no longer applies to a document the user chose (D-012).

## Direct prompt injection

`deepset/prompt-injections` at revision `4f61ecb0`, 662 rows in English and German. Harness: `eval/security/injection.py`.

| Guard | Train recall | Test recall | Test false positives |
|---|---|---|---|
| Regex guard as it was | 2.5% [0.5, 4.9] | 0% | 0% |
| `protectai/deberta-v3-base-prompt-injection-v2` | 42.9% [36.0, 49.8] | 36.7% [25.0, 48.3] | 0% |
| Regex guard now | 2.0% [0.5, 3.9] | 0% | 0% |

On the project's own questions, which were written for it:

| Guard | Law questions blocked | Contract questions blocked | Legal lookalikes blocked |
|---|---|---|---|
| Regex guard as it was | 0 of 50 | 0 of 20 | 11 of 20 |
| Classifier | 0 of 50 | 1 of 20 | 2 of 20 |
| Regex guard now | 0 of 50 | 0 of 20 | 1 of 20 |

The input guard doesn't stop prompt injection and isn't meant to. A direct injection only reaches the attacker's own session: no
tools are reachable from an answer, nothing secret is in the prompt, and data is scoped by organisation. The guard now only stops
plain attempts at the model's instructions and oversized input, so it no longer blocks lawyers. The classifier wasn't deployed
(D-013). The test split was scored a second time after narrowing the regex; the change only removed patterns.

## Citation check

A cited article now has to match a retrieved chunk of the same law, by its article tag or by the keyword and number in its text.
Before, "Art. 99" passed if "99" appeared anywhere in the sources. Unit tests: `test_a_number_elsewhere_in_the_text_does_not_verify_an_article`
and `test_the_cited_law_must_match_the_retrieved_article` in `backend/tests/test_citation_verifier.py`.

## Answer check against the contract (ContractNLI)

After generation, an answer is kept if it is close to a retrieved chunk (bge-m3 cosine at least 0.55) or shares six content words
with the context; otherwise quoted text replaces it. ContractNLI (CC BY 4.0) tests whether that tells a supported claim from a
contradicted one. Each hypothesis stands in for an answer; thresholds are tuned on dev and test is scored once. Harness:
`eval/grounding/contractnli.py`, results in `../grounding_2026-11/`.

| Check, five retrieved spans as context | Supported passed | Contradicted passed | Not mentioned passed | Balanced accuracy | CPU ms |
|---|---|---|---|---|---|
| Current check | 100.0% | 99.1% | 98.9% | 0.505 [0.502, 0.509] | 92 |
| Same cosine, tuned threshold | 73.8% | 56.8% | 46.6% | 0.626 [0.606, 0.645] | 92 |
| mDeBERTa-v3-base NLI | 57.4% | 14.5% | 23.6% | 0.678 [0.659, 0.699] | 464 |
| MiniLMv2-L6 NLI | 43.0% | 13.2% | 23.5% | 0.608 [0.589, 0.627] | 37 |

- The current check is a relevance check. It catches empty, refused and off-topic answers, and passes almost any claim on the
  right topic, true or not.
- With the annotated evidence as context, mDeBERTa passed 3.2% of contradicted claims, but also only 52.3% of supported ones.
- An NLI gate would turn about half the correct answers into quoted text, so it wasn't adopted (D-014). The product does not
  claim its answers are verified against their sources; citations are checked, answers are not.
- ContractNLI is English; German is untested.

## Static analysis and dependencies

- **bandit:** before, 3 medium (SQL built from strings) and 8 low (`bandit.json`). The one SQL path taking caller-supplied
  strings, an unused `filters` parameter, was removed; the remaining three join fixed fragments with bound values and carry a
  reviewed `nosec`. Seven low findings were exceptions swallowed in silence, two of which let bulk upload and corpus ingestion
  report success without queuing any work; they now log. Left: one low notice for `subprocess`, which runs the project's own
  eval scripts with fixed arguments and no shell (`bandit_after.json`).
- **pip-audit:** before, `transformers` 4.49.0 (remote code execution through checkpoint loading and conversion scripts, ReDoS),
  `sentence-transformers` 3.4.1, `python-jose`/`ecdsa` (`pip_audit.json`); auditing the installed image also found `torch` 2.6.0
  (including bypasses of its safe unpickler) and `setuptools` 78.1.0. `python-jose` was replaced with PyJWT, and torch 2.14.1,
  transformers 5.22.2, sentence-transformers 6.2.0 and setuptools 84 installed. After: 0 known vulnerabilities in the 129
  installed packages (`pip_audit_after.json`). On fixed inputs the new versions give the same embeddings (cosine 1.0) and
  reranker scores within 2e-6, and every LegalBench-RAG quality figure is unchanged (`ml_upgrade_check.json`).
- **OWASP ZAP:** `zap-api-scan.py` 2.16.1 with the OpenAPI spec, passive rules only (`-S`), without logging in. Before: no failures,
  warnings for a missing `X-Content-Type-Options` header and missing cross-origin isolation headers. Every response now carries
  `nosniff`, `Cross-Origin-Resource-Policy: same-origin`, `Referrer-Policy: no-referrer` and `X-Frame-Options: DENY`. After: 114
  passed, no failures, one warning that the pinned ZAP version is not the newest (`zap_api_before.json`, `zap_api_after.json`).
- **Metrics:** `/metrics` answered anyone. In production it now needs `METRICS_TOKEN` as a bearer token and is hidden without one.

## No traffic leaves the machine

`eval/security/egress_capture.sh` starts the API or the worker inside a network namespace that tcpdump is already watching, so
startup is included, then makes it do real work.

| Service | Work | Packets | To public addresses | Names looked up |
|---|---|---|---|---|
| API | start, answer one law question with the model | 386 | 0 | `db`, `cache` |
| Worker | start, ingest one uploaded ContractNLI contract | 475 | 0 | `db`, `cache` |

The only connections were to Postgres, Redis and Ollama on a private address; every DNS query was answered. Models load from
disk with Hugging Face's offline flags set and remote code off. In production, settings refuse a cloud API key when the local
model is selected and a tracing endpoint on a public host. This shows no attempts in this configuration; it is not a firewall.

## Law suite after these changes

The project's own 110-question regression suite, on the final code with the law texts re-chunked: 106 passed
(`logical_final.json`; Phase 5: 105). The two remaining long-standing misses are bgb-003 and cross-003. Two more, gdpr-023 and
cross-005, passed in the run before; asked three times each, one cited its article in 1 of 3 tries, so the suite moves by a
couple of questions between runs. An earlier run of this phase, before the guard and chunking changes, passed 108
(`logical_defended.json`).

That earlier run also showed a broken answer, ") aw.", to a project attack prompt. It came from two bugs, both fixed: the law
chunker cut long paragraphs every 1,200 characters mid-word, leaving 14 fragment chunks such as "ormance made." plus
"table of contents" lines, and the quoted-text fallback mishandled source labels with their own parentheses. The law corpus was
re-ingested: 4,129 chunks, from 4,172.
