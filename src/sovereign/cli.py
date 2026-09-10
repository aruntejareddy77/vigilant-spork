"""
src/sovereign/cli.py
Unified CLI entry point for the Sovereign AI Workbench.
"""
import json
from pathlib import Path
import sys
from typing import Optional
import click

from sovereign.audit.canonical import GENESIS_PREVIOUS_HASH
from sovereign.audit.mirror import AuditMirror
from sovereign.audit.verifier import verify_ledger


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Sovereign AI Workbench - Self-Hosted Air-Gapped Industrial Platform."""
    pass


@cli.group()
def audit():
    """Manage and verify cryptographic audit ledgers."""
    pass


@audit.command("verify")
@click.argument("ledger_path", default="audit_ledger.jsonl", type=click.Path(dir_okay=False))
def audit_verify(ledger_path: str):
    """
    Traverse and verify the cryptographic integrity of the audit ledger.
    Pinpoints tampered records or broken hash chains.
    """
    path = Path(ledger_path)
    if not path.exists():
        click.echo(f"[ERROR] Ledger file not found: {path}", err=True)
        sys.exit(1)

    result = verify_ledger(path)
    if result.is_valid:
        click.echo(
            f"[OK] Audit ledger integrity verified.\n"
            f"     Records checked : {result.records_checked}\n"
            f"     Tip hash        : {result.tip_hash}"
        )
        sys.exit(0)
    else:
        click.echo(
            f"[FAIL] Cryptographic audit chain TAMPER detected!\n"
            f"       Error Sequence : {result.error_seq}\n"
            f"       Diagnostic     : {result.error_message}",
            err=True,
        )
        sys.exit(1)


@audit.command("inspect")
@click.argument("ledger_path", default="audit_ledger.jsonl", type=click.Path(dir_okay=False))
def audit_inspect(ledger_path: str):
    """
    Display statistics, record counts, and session information for an audit ledger.
    """
    path = Path(ledger_path)
    if not path.exists():
        click.echo(f"[ERROR] Ledger file not found: {path}", err=True)
        sys.exit(1)

    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str:
                try:
                    records.append(json.loads(line_str))
                except json.JSONDecodeError:
                    pass

    total_records = len(records)
    if total_records == 0:
        click.echo(f"Ledger file: {path} (Empty, 0 records)")
        sys.exit(0)

    sessions = set(r.get("session_id") for r in records if "session_id" in r)
    first_time = records[0].get("timestamp_iso", "N/A")
    last_time = records[-1].get("timestamp_iso", "N/A")
    genesis_prev = records[0].get("previous_hash", GENESIS_PREVIOUS_HASH)
    tip_hash = records[-1].get("entry_hash", "N/A")

    click.echo("=== Sovereign Audit Ledger Inspection ===")
    click.echo(f"File Path        : {path.resolve()}")
    click.echo(f"Total Records    : {total_records}")
    click.echo(f"Unique Sessions  : {len(sessions)}")
    click.echo(f"First Timestamp  : {first_time}")
    click.echo(f"Last Timestamp   : {last_time}")
    click.echo(f"Genesis PrevHash : {genesis_prev}")
    click.echo(f"Tip Hash         : {tip_hash}")
    click.echo("=========================================")
    sys.exit(0)


@audit.command("export")
@click.option("--session-id", required=True, help="Session identifier to isolate and export.")
@click.option("--ledger-path", default="audit_ledger.jsonl", type=click.Path(dir_okay=False), help="Path to JSONL ledger.")
@click.option("--db-path", default=None, type=click.Path(dir_okay=False), help="Path to SQLite mirror (optional).")
@click.option("--output", default=None, type=click.Path(dir_okay=False), help="Output destination file.")
@click.option("--format", "fmt", type=click.Choice(["json", "jsonl"], case_sensitive=False), default="jsonl", help="Export format.")
def audit_export(session_id: str, ledger_path: str, db_path: Optional[str], output: Optional[str], fmt: str):
    """
    Extract a standalone audit slice for a specific session_id.
    """
    events_data = []

    # If db_path is provided and exists, use fast SQLite mirror
    if db_path and Path(db_path).exists():
        mirror = AuditMirror(db_path)
        slice_events = mirror.export_session_slice(session_id)
        events_data = [e.model_dump() for e in slice_events]
    else:
        # Fallback to streaming from JSONL
        l_path = Path(ledger_path)
        if not l_path.exists():
            click.echo(f"[ERROR] Ledger file not found: {l_path}", err=True)
            sys.exit(1)

        with open(l_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    try:
                        rec = json.loads(line_str)
                        if rec.get("session_id") == session_id:
                            events_data.append(rec)
                    except json.JSONDecodeError:
                        pass

    if fmt == "json":
        formatted_output = json.dumps(events_data, indent=2, ensure_ascii=False)
    else:
        formatted_output = "\n".join(json.dumps(r, ensure_ascii=False) for r in events_data)

    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(formatted_output + ("\n" if fmt == "jsonl" and formatted_output else ""))
        click.echo(f"[OK] Exported {len(events_data)} events for session '{session_id}' to {output}")
    else:
        click.echo(formatted_output)

    sys.exit(0)


if __name__ == "__main__":
    cli()
