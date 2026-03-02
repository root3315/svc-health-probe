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
- `--post` - Post-check command to run after health checks (can be specified multiple times)
- `--post-timeout` - Timeout for post-check commands in seconds (default: 30)

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

With post-checks:
```bash
python svc_health_probe.py --post "echo 'Health check complete'" http://localhost:8080/health
```

Multiple post-checks:
```bash
python svc_health_probe.py \
  --post "curl -s http://localhost:8080/metrics" \
  --post "echo 'All checks done'" \
  http://localhost:8080/health
```

Post-check with custom timeout:
```bash
python svc_health_probe.py \
  --post-timeout 60 \
  --post "./scripts/validate-deployment.sh" \
  http://localhost:8080/health
```

## Output

Text mode looks like:
```
svc-health-probe - 2026-03-03 14:30:00
------------------------------------------------------------
[✓] HEALTHY HTTP 200 (12.5ms) - http://localhost:8080/health
[✗] SERVER_ERROR HTTP 503 (8.2ms) - http://api.local/status
    Error: HTTP 503: Service Unavailable

Post-checks:
[✓] PASSED (exit 0) (45.2ms) - echo 'Health check complete'
------------------------------------------------------------
All 1 endpoint(s) healthy, 1/1 post-check(s) passed
```

Exit code is 0 if all endpoints are healthy and all post-checks pass, 1 otherwise.

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
- Post-checks run after all health endpoint checks complete
- Post-checks are shell commands, so you can run scripts, curl, echo, etc.
