# svc-health-probe

Lightweight probe to check service health endpoints. Built this because I kept needing to quickly verify if my services were up without pulling in heavy monitoring tools.

## Why

Sometimes you just need to hit a bunch of health endpoints and see what's up. This does that. No dashboards, no agents, just curl-like simplicity with better output.

## Usage

```bash
python svc_health_probe.py http://localhost:8080/health http://api.example.com/status
```

### Options

- `-t, --timeout` - Request timeout (default: 5s)
- `-r, --retries` - Retry count on failure (default: 3)
- `-d, --retry-delay` - Seconds between retries (default: 1)
- `-H, --header` - Custom headers, e.g. `-H "Authorization: Bearer xyz"`
- `-j, --json` - Output as JSON for scripting
- `-v, --verbose` - Show more details

### Examples

Basic check:
```bash
python svc_health_probe.py http://localhost:3000/health
```

With custom timeout and retries:
```bash
python svc_health_probe.py -t 10 -r 5 http://api.local/health
```

With auth header:
```bash
python svc_health_probe.py -H "X-API-Key: secret123" http://api.local/health
```

JSON output for CI/CD:
```bash
python svc_health_probe.py -j http://api.local/health | jq '.healthy'
```

## Output

Text mode looks like:
```
svc-health-probe - 2026-03-03 14:30:00
------------------------------------------------------------
[✓] HEALTHY HTTP 200 (12.5ms) - http://localhost:8080/health
[✗] SERVER_ERROR HTTP 503 (8.2ms) - http://api.local/status
    Error: HTTP 503: Service Unavailable
------------------------------------------------------------
1/2 endpoint(s) healthy
```

Exit code is 0 if all endpoints are healthy, 1 otherwise.

## Install

No dependencies beyond Python 3.6+ stdlib. Just clone and run.

If you want to install it globally:
```bash
pip install -e .
```

Or symlink it:
```bash
ln -s $(pwd)/svc_health_probe.py /usr/local/bin/svc-health
```

## Notes

- Handles redirects as "healthy" (status 3xx)
- 4xx and 5xx are considered unhealthy
- Network errors show as "unreachable"
- Retries only happen on actual failures, not slow responses
