# Enterprise feature removal, 2026-11-06

Checks for the removal of SSO, SCIM, WORM, legal hold, the clause library and deadlines. Same
machine and models as `../baseline_2026-11/`. The cache was flushed before the suites ran.

| Check | Result | Note |
|---|---|---|
| Law regression suite | 104 of 110 | Baseline 103. No new failures. `cross-005` now passes, which is most likely model variation |
| Law retrieval, contract hit rate | 77.3%, 85% | Same as baseline |
| Unit tests | 95 of 95 | Baseline 100. SAML and IdP group tests were removed with the feature |
| E2E | 48 of 48 | Baseline 49. The deadlines check was removed |
| Integration | 37 of 40 on the full run | The other 3 passed when re-run after the causes below, but the full set has not been re-run together |
| Endpoint audits | 34 of 34, 26 of 26 | See below |
| Playwright | 13 of 13 | 11 on the first run. See below |
| Migration | Passed | Upgrade then downgrade reproduces the 018 schema exactly. Row counts unchanged. A fresh database differs only by the HNSW index that law ingest creates |

## First-run failures

- **Corpus upload returned 500.** A bug from before this work: `/app/src/data` is root-owned and the
  app runs as `juris`. Fixed in `docker-entrypoint.sh`.
- **Two retrieval tests failed on the host** because `sentence_transformers` is not in the host venv.
  They passed in a container (`integration_retrieval_in_container.log`), including the cross-org
  isolation test.
- **Two export routes returned 404 in the endpoint audit.** The audit used a random matter id. The
  tracked June report shows the same two failures. Fixed in the script.
- **`graph_extract` returned 400 in one audit run**, right after the worker restarted. The audit waits
  up to 80 s for a document to process, and a worker still loading models can take longer. It passed
  on the next run, so this is a timing weakness in the script, not fixed here.
- **Two Playwright research chat tests timed out at 120 s.** Cold model load with an image build
  competing for disk took about 97 s to first token. They passed with the model warm
  (`playwright_chat_warm.log`). Not caused by the removal, and queued for Phase 5.
