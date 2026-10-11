# Clearance portal UX checkpoints — summary

Program: A3 (full brief) + B2 (pytest + manual checklists + Playwright).

| Round | Focus | Backend tests | Playwright | Status |
|------:|-------|---------------|------------|--------|
| R0 | E2E harness + CI | n/a | `r0-smoke` | Passed |
| R1 | Trust / clarity | existing system/coverage | `r1-trust` | Passed |
| R2 | Case workspace | `test_clearance_r2_r5` | `r2-case` | Passed |
| R3 | Papers + ZIP pack | same | `r3-papers` | Passed |
| R4 | Work queue / alerts | same | `r4-alerts` | Passed |
| R5 | Ask co-pilot | same | `r5-ask` | Passed |
| R6 | Admin / RBAC | `test_clearance_r6_r11` + security | `r6-admin` | Passed |
| R7 | Account / org / legal | `test_clearance_r6_r11` | covered via UI | Passed |
| R8 | Parties / lines / comments | same | covered via API | Passed |
| R9 | Exports / FTA compare | same | covered via API | Passed |
| R10 | Notifications / retention / AV | same | covered via API | Passed |
| R11 | Client share / search / corridors | same | `@happy` | Passed |

## Commands

```powershell
# Backend clearance suites
python -m pytest backend/tests/integration/test_clearance_r2_r5.py backend/tests/integration/test_clearance_r6_r11.py --no-cov

# Frontend e2e (auto-starts API + Vite)
cd frontend
npx playwright install chromium   # or set PW_CHANNEL=chrome on Windows
npm run test:e2e
npm run test:e2e:happy
```

Honesty lock unchanged: BD→IN chapter 61 operational; duties deterministic; LLM explain-only.
