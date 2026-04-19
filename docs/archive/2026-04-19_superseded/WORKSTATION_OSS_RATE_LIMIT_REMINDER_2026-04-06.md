# Workstation OSS Rate Limit Reminder

## Current Planning Math

- Internal OSS processing should be planned against the hourly quota, not the burst rate
- Current sustained ceiling: `5M tokens/hour`
- Sustained equivalent: about `83,333 tokens/minute`
- If raised to `10M tokens/hour`, sustained throughput becomes about `166,667 tokens/minute`

## Why This Matters

- `150K TPM` is a burst number
- `5M TPH` is the real sustained limiter for long-running batch work
- A move from `5M/hour` to `10M/hour` roughly cuts total processing time in half

## Shared Naming Rule

- In shared docs, manifests, and runbooks, use the neutral label `Workstation` for the high-capacity local processing box
- Do not use hardware nicknames in shared repo content
