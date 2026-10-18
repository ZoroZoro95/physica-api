"""Generate a reviewable scene through local API calls, never generated code."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
from urllib.parse import urlparse
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from dotenv import load_dotenv
from groq import Groq
from core.playground.agent import run_agent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--question', required=True)
    parser.add_argument('--env-file', type=Path, help='Explicit .env file; never written to reports')
    parser.add_argument('--model', help='Groq model ID; otherwise PLAYGROUND_MODEL')
    parser.add_argument('--api-url', default='http://127.0.0.1:8001')
    args = parser.parse_args()
    if args.env_file:
        if not args.env_file.is_file():
            parser.error('Environment file does not exist')
        load_dotenv(args.env_file)
    model = args.model or os.getenv('PLAYGROUND_MODEL')
    if not model or not os.getenv('GROQ_API_KEY'):
        parser.error('Set GROQ_API_KEY and PLAYGROUND_MODEL, or pass --model. No fallback to unrelated provider keys.')
    url = urlparse(args.api_url)
    if (url.scheme != 'http' or url.hostname not in ('localhost', '127.0.0.1', '::1')
            or url.username or url.password or url.path not in ('', '/') or url.query or url.fragment):
        parser.error('This prototype only connects to a loopback HTTP playground API')
    client = Groq(api_key=os.environ['GROQ_API_KEY'], timeout=30, max_retries=0)

    def complete(messages, tools):
        response = client.chat.completions.create(model=model, messages=messages, tools=tools,
            tool_choice='auto', parallel_tool_calls=False, temperature=0, max_completion_tokens=3000)
        message = response.choices[0].message
        return {'content': message.content,
                'tool_calls': [c.model_dump() for c in message.tool_calls or []]}

    with httpx.Client(base_url=args.api_url.rstrip('/'), timeout=15, follow_redirects=False, trust_env=False) as api:
        report = run_agent(args.question, complete, api)
    report['model'] = model
    destination = Path(__file__).resolve().parents[1] / 'questions/debug_reports/playground-agent'
    destination /= datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8]
    destination.mkdir(parents=True, mode=0o700)
    (destination/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    if report['scene']:
        (destination/'scene.json').write_text(json.dumps(report['scene'], indent=2, allow_nan=False)+'\n')
    print(f"{report['status']}: {report['reason']}\nReport: {destination}")
    return 0 if report['status'] in ('review', 'needs_clarification', 'unsupported') else 1


if __name__ == '__main__':
    raise SystemExit(main())
