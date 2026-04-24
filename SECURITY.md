# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.6.x   | Yes |
| < 0.6.0 | No |

## Reporting a Vulnerability

Since trace-eval is a local-first CLI that reads user trace files, the main security considerations are:

1. **Trace file handling** — trace-eval reads local files only. It does not upload, transmit, or share trace data over the network.
2. **No network calls** — The scoring and remediation path makes zero network requests.
3. **No credential handling** — trace-eval does not store or process API keys, tokens, or credentials.

If you discover a security issue, please report it via [GitHub Security Advisory](https://github.com/kin0kaze23/trace-eval/security/advisories/new).
