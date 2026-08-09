# Deployment Readiness

The bot progresses through three explicit stages. A stage is not approval to
advance automatically; it is evidence required before an operator considers
the next stage.

## Research only

- Reproducible backtests include costs, assumptions, data provenance, and an
  out-of-sample period.
- Stress runs cover data outages, stale candles, price gaps, and parameter
  sensitivity.
- No broker placement permissions are enabled.

## Paper and review-only

- MCP contract checks use only tool listing, portfolio/position readback, and
  `review_equity_order`; they never call placement.
- The daemon runs with one service-root lease. A stale lease requires an
  operator-confirmed recovery.
- Every submission attempt is journaled and reconciled before another attempt.

## Controlled live pilot

- An operator explicitly enables the existing live gates and authorizes the
  exact order.
- Use `mcp-place-once` first, with a small cap and a verified broker readback.
- Stop automation on data validation failure, an unreconciled order, a lease
  conflict, unknown MCP payload, or any risk-limit breach.

## Incident procedure

1. Stop the daemon process; do not start a second instance.
2. Run `daemon-state` and `daemon-reconcile --dry-run`.
3. Confirm the broker order state independently.
4. Use the explicit pending-state recovery command only after that confirmation.
5. Record the event and root cause in the decision journal before resuming.
