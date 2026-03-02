#!/usr/bin/env python3
"""
svc-health-probe - Lightweight probe to check service health endpoints
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from typing import Dict, List, Optional, Any


DEFAULT_TIMEOUT = 5
DEFAULT_RETRIES = 3
DEFAULT_RETRY_DELAY = 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lightweight probe to check service health endpoints"
    )
    parser.add_argument(
        "endpoints",
        nargs="+",
        help="Health endpoint URLs to check"
    )
    parser.add_argument(
        "-t", "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT})"
    )
    parser.add_argument(
        "-r", "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"Number of retries on failure (default: {DEFAULT_RETRIES})"
    )
    parser.add_argument(
        "-d", "--retry-delay",
        type=int,
        default=DEFAULT_RETRY_DELAY,
        help=f"Delay between retries in seconds (default: {DEFAULT_RETRY_DELAY})"
    )
    parser.add_argument(
        "-H", "--header",
        action="append",
        dest="headers",
        help="Custom header (format: Header-Name: value)"
    )
    parser.add_argument(
        "-j", "--json",
        action="store_true",
        help="Output results as JSON"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed output"
    )
    parser.add_argument(
        "--post",
        action="append",
        dest="post_checks",
        help="Post-check command to run after health checks (can be specified multiple times)"
    )
    parser.add_argument(
        "--post-timeout",
        type=int,
        default=30,
        help="Timeout for post-check commands in seconds (default: 30)"
    )
    return parser.parse_args()


def parse_headers(header_list: Optional[List[str]]) -> Dict[str, str]:
    headers = {}
    if header_list:
        for h in header_list:
            if ":" in h:
                key, value = h.split(":", 1)
                headers[key.strip()] = value.strip()
    return headers


def check_endpoint(
    url: str,
    timeout: int,
    retries: int,
    retry_delay: int,
    headers: Dict[str, str],
    verbose: bool = False
) -> Dict[str, Any]:
    result = {
        "url": url,
        "status": "unknown",
        "status_code": None,
        "response_time_ms": None,
        "error": None,
        "attempts": 0
    }

    req = Request(url)
    req.add_header("User-Agent", "svc-health-probe/1.0")

    for key, value in headers.items():
        req.add_header(key, value)

    for attempt in range(1, retries + 1):
        result["attempts"] = attempt
        start_time = time.perf_counter()

        try:
            response = urlopen(req, timeout=timeout)
            elapsed = (time.perf_counter() - start_time) * 1000

            result["status_code"] = response.status
            result["response_time_ms"] = round(elapsed, 2)

            if 200 <= response.status < 300:
                result["status"] = "healthy"
            elif 300 <= response.status < 400:
                result["status"] = "redirect"
            elif 400 <= response.status < 500:
                result["status"] = "client_error"
            else:
                result["status"] = "server_error"

            if verbose:
                body = response.read(500)
                if body:
                    result["response_sample"] = body.decode("utf-8", errors="ignore")[:200]

            break

        except HTTPError as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            result["status_code"] = e.code
            result["response_time_ms"] = round(elapsed, 2)
            result["error"] = f"HTTP {e.code}: {e.reason}"

            if e.code >= 500:
                result["status"] = "server_error"
            else:
                result["status"] = "client_error"

        except URLError as e:
            result["error"] = str(e.reason)
            result["status"] = "unreachable"

        except Exception as e:
            result["error"] = str(e)
            result["status"] = "error"

        if attempt < retries:
            if verbose:
                print(f"  Retry {attempt}/{retries} for {url}...", file=sys.stderr)
            time.sleep(retry_delay)

    if result["status"] == "unknown" and result["error"]:
        result["status"] = "unreachable"

    return result


def run_post_check(
    command: str,
    timeout: int,
    verbose: bool = False
) -> Dict[str, Any]:
    result = {
        "command": command,
        "status": "unknown",
        "exit_code": None,
        "duration_ms": None,
        "error": None,
        "output": None
    }

    start_time = time.perf_counter()

    try:
        proc = subprocess.run(
            command,
            shell=True,
            timeout=timeout,
            capture_output=True,
            text=True
        )

        elapsed = (time.perf_counter() - start_time) * 1000
        result["exit_code"] = proc.returncode
        result["duration_ms"] = round(elapsed, 2)

        if proc.returncode == 0:
            result["status"] = "passed"
        else:
            result["status"] = "failed"

        if verbose or proc.returncode != 0:
            output_parts = []
            if proc.stdout:
                output_parts.append(proc.stdout.strip())
            if proc.stderr:
                output_parts.append(proc.stderr.strip())
            if output_parts:
                result["output"] = "\n".join(output_parts)

    except subprocess.TimeoutExpired:
        elapsed = (time.perf_counter() - start_time) * 1000
        result["duration_ms"] = round(elapsed, 2)
        result["status"] = "timeout"
        result["error"] = f"Command timed out after {timeout}s"

    except Exception as e:
        result["error"] = str(e)
        result["status"] = "error"

    return result


def format_text_result(result: Dict[str, Any]) -> str:
    status_icon = {
        "healthy": "✓",
        "redirect": "↻",
        "client_error": "✗",
        "server_error": "✗",
        "unreachable": "✗",
        "error": "✗",
        "unknown": "?",
        "passed": "✓",
        "failed": "✗",
        "timeout": "⏱"
    }.get(result["status"], "?")

    status_str = f"[{status_icon}] {result['status'].upper()}"
    time_str = ""

    if result.get("response_time_ms") is not None:
        time_str = f" ({result['response_time_ms']}ms)"
    elif result.get("duration_ms") is not None:
        time_str = f" ({result['duration_ms']}ms)"

    code_str = ""
    if result.get("status_code"):
        code_str = f" HTTP {result['status_code']}"
    elif result.get("exit_code") is not None:
        code_str = f" (exit {result['exit_code']})"

    target = result.get("url") or result.get("command", "")
    output = f"{status_str}{code_str}{time_str} - {target}"

    if result.get("error"):
        output += f"\n    Error: {result['error']}"

    if result.get("attempts") and result["attempts"] > 1:
        output += f"\n    Attempts: {result['attempts']}"

    if result.get("output"):
        output += f"\n    Output: {result['output']}"

    return output


def run_probes(args: argparse.Namespace) -> List[Dict[str, Any]]:
    headers = parse_headers(args.headers)
    results = []

    for url in args.endpoints:
        if args.verbose:
            print(f"Checking: {url}", file=sys.stderr)

        result = check_endpoint(
            url=url,
            timeout=args.timeout,
            retries=args.retries,
            retry_delay=args.retry_delay,
            headers=headers,
            verbose=args.verbose
        )
        results.append(result)

    return results


def run_post_checks(
    commands: List[str],
    timeout: int,
    verbose: bool = False
) -> List[Dict[str, Any]]:
    results = []

    for command in commands:
        if verbose:
            print(f"Running post-check: {command}", file=sys.stderr)

        result = run_post_check(
            command=command,
            timeout=timeout,
            verbose=verbose
        )
        results.append(result)

    return results


def main() -> int:
    args = parse_args()
    results = run_probes(args)

    post_results = []
    if args.post_checks:
        post_results = run_post_checks(
            commands=args.post_checks,
            timeout=args.post_timeout,
            verbose=args.verbose
        )

    all_results = results + post_results

    if args.json:
        output = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "total": len(results),
            "healthy": sum(1 for r in results if r["status"] == "healthy"),
            "results": results
        }
        if post_results:
            output["post_checks"] = {
                "total": len(post_results),
                "passed": sum(1 for r in post_results if r["status"] == "passed"),
                "results": post_results
            }
        print(json.dumps(output, indent=2))
    else:
        print(f"svc-health-probe - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 60)

        for result in results:
            print(format_text_result(result))

        if post_results:
            print()
            print("Post-checks:")
            for result in post_results:
                print(format_text_result(result))

        print("-" * 60)

        healthy_count = sum(1 for r in results if r["status"] == "healthy")
        total_count = len(results)

        if post_results:
            passed_count = sum(1 for r in post_results if r["status"] == "passed")
            post_total = len(post_results)
            print(f"All {total_count} endpoint(s) healthy, {passed_count}/{post_total} post-check(s) passed")
        else:
            if healthy_count == total_count:
                print(f"All {total_count} endpoint(s) healthy")
            else:
                print(f"{healthy_count}/{total_count} endpoint(s) healthy")

    unhealthy = [r for r in results if r["status"] not in ("healthy", "redirect")]
    failed_post = [r for r in post_results if r["status"] != "passed"]

    if unhealthy or failed_post:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
