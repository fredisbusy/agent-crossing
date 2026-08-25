# Test review

- Unit coverage verifies diagnostics redaction and embedding-dimension validation.
- PostgreSQL integration coverage verifies create/read/save, normalized projections, optimistic conflicts, and restoration of the previously active session.
- Existing backend and frontend suites remain required regression gates.
- Manual live acceptance covers new session, current save, saved-session load, backend restart, and frontend proxy reachability.
- Browser automation and process-kill fault injection remain follow-up coverage gaps.

