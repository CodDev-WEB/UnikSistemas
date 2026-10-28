#!/usr/bin/env python3
"""Read-only readiness checks for an isolated UnikSistemas staging environment."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SERVICES = {
    "db",
    "api",
    "frontend",
    "clamav",
    "document-scan-worker",
    "notification-worker",
}
REVISION_RE = re.compile(r"^([A-Za-z0-9_]+)(?:\s+\(head\))?$")
MAX_STORED_HEALTH_AGE = timedelta(minutes=10)

CLAMAV_CHECK = r"""
import json
from datetime import UTC, datetime, timedelta
from app.antivirus import get_clamav_info, signature_status
from app.config import get_settings
from app.db import SessionLocal
from app.models import AntivirusHealth

settings = get_settings()
info = get_clamav_info(
    settings.antivirus_host,
    settings.antivirus_port,
    settings.antivirus_timeout_seconds,
)
now = datetime.now(UTC)
status, error = signature_status(
    info.database_date,
    now,
    settings.antivirus_signature_max_age_hours,
)
with SessionLocal() as db:
    health = db.get(AntivirusHealth, "clamav")
    checked_at = health.checked_at if health is not None else None
    if checked_at is not None and checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=UTC)
    health_age = now - checked_at if checked_at is not None else None
    stored_health_ok = (
        health is not None
        and health.status == "healthy"
        and health_age is not None
        and timedelta(0) <= health_age <= timedelta(minutes=10)
    )
result = {
    "probe_status": status,
    "signature_database_version": info.database_version,
    "signature_database_date": info.database_date.isoformat(),
    "stored_health_status": health.status if health is not None else "missing",
    "stored_health_age_seconds": int(health_age.total_seconds()) if health_age is not None else None,
    "error": error,
}
print(json.dumps(result, ensure_ascii=False))
raise SystemExit(0 if status == "healthy" and stored_health_ok else 1)
"""


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    details: str


def run_command(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    """Run a command without a shell and capture output for a safe summary."""
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def command_check(name: str, args: list[str], timeout: int = 30) -> tuple[Check, str]:
    try:
        result = run_command(args, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Check(name, "FAIL", f"Não foi possível executar o comando ({type(exc).__name__})."), ""

    output = result.stdout.strip()
    if result.returncode == 0:
        detail = output.splitlines()[-1][:400] if output else "Comando concluído."
        return Check(name, "PASS", detail), output

    # Avoid copying arbitrary command output or environment data into the report.
    error = result.stderr.strip().splitlines()
    detail = error[-1][:300] if error else f"Comando encerrou com código {result.returncode}."
    return Check(name, "FAIL", detail), output


def parse_revision_ids(output: str) -> set[str]:
    revisions: set[str] = set()
    for line in output.splitlines():
        match = REVISION_RE.fullmatch(line.strip())
        if match:
            revisions.add(match.group(1))
    return revisions


def public_url_issues(value: str) -> list[str]:
    parsed = urlsplit(value)
    issues: list[str] = []
    if parsed.scheme.lower() != "https":
        issues.append("a URL pública precisa usar HTTPS")
    if not parsed.netloc:
        issues.append("a URL pública precisa conter um host")
    if parsed.username or parsed.password:
        issues.append("não inclua usuário ou senha na URL")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        issues.append("informe somente a origem pública, sem caminho, query ou fragmento")
    return issues


def missing_security_headers(headers) -> list[str]:
    normalized = {key.lower(): value.strip() for key, value in headers.items()}
    missing: list[str] = []
    hsts = normalized.get("strict-transport-security", "")
    match = re.search(r"(?:^|;)\s*max-age\s*=\s*(\d+)", hsts, re.IGNORECASE)
    if match is None or int(match.group(1)) < 1:
        missing.append("Strict-Transport-Security com max-age positivo")
    if normalized.get("x-content-type-options", "").lower() != "nosniff":
        missing.append("X-Content-Type-Options: nosniff")
    if normalized.get("x-frame-options", "").upper() not in {"DENY", "SAMEORIGIN"}:
        missing.append("X-Frame-Options: DENY ou SAMEORIGIN")
    if not normalized.get("referrer-policy"):
        missing.append("Referrer-Policy")
    return missing


def fetch_http(url: str, timeout: int) -> tuple[int, bytes, object, str]:
    with urlopen(url, timeout=timeout) as response:
        return response.status, response.read(4096), response.headers, response.geturl()


def check_json_endpoint(
    name: str,
    url: str,
    expected: dict[str, str],
    timeout: int,
) -> Check:
    try:
        status, payload, _headers, final_url = fetch_http(url, timeout)
        if status != 200:
            return Check(name, "FAIL", f"HTTP {status}.")
        body = json.loads(payload.decode("utf-8"))
        mismatches = [key for key, value in expected.items() if body.get(key) != value]
        if mismatches:
            return Check(name, "FAIL", "Resposta de saúde não corresponde ao esperado.")
        if urlsplit(final_url).scheme != urlsplit(url).scheme:
            return Check(name, "FAIL", "O endpoint redirecionou para outro esquema.")
        return Check(name, "PASS", "Resposta de saúde válida.")
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        return Check(name, "FAIL", f"Falha na verificação HTTP ({type(exc).__name__}).")


def check_plain_endpoint(name: str, url: str, timeout: int) -> Check:
    try:
        status, _payload, _headers, final_url = fetch_http(url, timeout)
        if status != 200:
            return Check(name, "FAIL", f"HTTP {status}.")
        if urlsplit(final_url).scheme != urlsplit(url).scheme:
            return Check(name, "FAIL", "O endpoint redirecionou para outro esquema.")
        return Check(name, "PASS", "Endpoint respondeu HTTP 200.")
    except (URLError, TimeoutError, OSError) as exc:
        return Check(name, "FAIL", f"Falha na verificação HTTP ({type(exc).__name__}).")


def check_public_edge(public_url: str, timeout: int) -> list[Check]:
    problems = public_url_issues(public_url)
    if problems:
        return [Check("Borda HTTPS", "FAIL", "; ".join(problems))]

    parsed = urlsplit(public_url)
    health_url = urlunsplit(("https", parsed.netloc, "/health", "", ""))
    try:
        status, _payload, headers, final_url = fetch_http(health_url, timeout)
        if status != 200 or urlsplit(final_url).scheme != "https":
            return [Check("Borda HTTPS", "FAIL", "A URL pública não respondeu com sucesso via HTTPS.")]
        missing = missing_security_headers(headers)
        if missing:
            return [Check("Cabeçalhos de segurança públicos", "FAIL", "Ausentes ou inválidos: " + ", ".join(missing))]
        checks = [
            Check("Borda HTTPS", "PASS", "Endpoint público respondeu via HTTPS."),
            Check("Cabeçalhos de segurança públicos", "PASS", "HSTS e cabeçalhos de proteção verificados."),
        ]
    except (URLError, TimeoutError, OSError) as exc:
        return [Check("Borda HTTPS", "FAIL", f"Falha na verificação da borda ({type(exc).__name__}).")]

    http_url = urlunsplit(("http", parsed.netloc, "/health", "", ""))
    try:
        _status, _payload, _headers, final_http_url = fetch_http(http_url, timeout)
        if urlsplit(final_http_url).scheme != "https":
            checks.append(Check("Redirecionamento HTTP para HTTPS", "FAIL", "O acesso HTTP não terminou em HTTPS."))
        else:
            checks.append(Check("Redirecionamento HTTP para HTTPS", "PASS", "HTTP redireciona para HTTPS."))
    except (URLError, TimeoutError, OSError) as exc:
        checks.append(Check("Redirecionamento HTTP para HTTPS", "FAIL", f"Falha ao verificar HTTP ({type(exc).__name__})."))
    return checks


def run_preflight(args: argparse.Namespace) -> list[Check]:
    checks: list[Check] = []

    check, _ = command_check(
        "Configuração Docker Compose",
        ["docker", "compose", "config", "--quiet"],
    )
    checks.append(check)

    check, running_text = command_check(
        "Serviços Docker em execução",
        ["docker", "compose", "ps", "--services", "--filter", "status=running"],
    )
    checks.append(check)
    if check.status == "PASS":
        running = set(running_text.splitlines())
        missing = sorted(REQUIRED_SERVICES - running)
        if missing:
            checks.append(Check("Serviços obrigatórios", "FAIL", "Não estão em execução: " + ", ".join(missing)))
        else:
            checks.append(Check("Serviços obrigatórios", "PASS", "Todos os serviços esperados estão em execução."))

    checks.append(
        check_json_endpoint(
            "API: liveness",
            args.api_url.rstrip("/") + "/health/live",
            {"status": "ok"},
            args.timeout,
        )
    )
    checks.append(
        check_json_endpoint(
            "API: readiness e banco",
            args.api_url.rstrip("/") + "/health/ready",
            {"status": "ready", "database": "ok"},
            args.timeout,
        )
    )
    checks.append(
        check_plain_endpoint(
            "Frontend: endpoint de saúde",
            args.web_url.rstrip("/") + "/health",
            args.timeout,
        )
    )

    check, current_output = command_check(
        "Revisão atual do banco",
        ["docker", "compose", "exec", "-T", "api", "alembic", "current"],
    )
    checks.append(check)
    check, heads_output = command_check(
        "Revisões de migração disponíveis",
        ["docker", "compose", "exec", "-T", "api", "alembic", "heads"],
    )
    checks.append(check)
    current_revisions = parse_revision_ids(current_output)
    head_revisions = parse_revision_ids(heads_output)
    if current_revisions and current_revisions == head_revisions:
        checks.append(Check("Banco atualizado até head", "PASS", "A revisão aplicada corresponde à revisão mais recente."))
    else:
        checks.append(Check("Banco atualizado até head", "FAIL", "A revisão aplicada não corresponde às revisões disponíveis."))

    check, clamav_output = command_check(
        "ClamAV e assinaturas",
        [
            "docker", "compose", "exec", "-T",
            "document-scan-worker", "python", "-c", CLAMAV_CHECK,
        ],
        timeout=max(args.timeout, 20),
    )
    if check.status == "PASS":
        try:
            info = json.loads(clamav_output.splitlines()[-1])
            details = (
                f"Scanner healthy; DB de assinaturas {info['signature_database_version']}; "
                f"estado persistido atualizado há {info['stored_health_age_seconds']}s."
            )
            check = Check(check.name, "PASS", details)
        except (KeyError, IndexError, json.JSONDecodeError):
            check = Check(check.name, "FAIL", "O scanner respondeu, mas o relatório de saúde não pôde ser interpretado.")
    checks.append(check)

    if args.public_url:
        checks.extend(check_public_edge(args.public_url, args.timeout))
    elif args.require_public_url:
        checks.append(Check("Borda HTTPS pública", "FAIL", "Informe --public-url https://... para validar TLS, HSTS e proxy."))
    else:
        checks.append(Check("Borda HTTPS pública", "SKIP", "Não verificada; informe --public-url para validar a borda externa."))

    return checks


def render_report(checks: list[Check], generated_at: datetime | None = None) -> str:
    when = (generated_at or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds")
    lines = [
        "# Relatório de prontidão — UnikSistemas",
        "",
        f"- Gerado em UTC: {when}",
        "- Escopo: verificações de leitura; não executa restauração, envio de e-mail ou exclusão de documentos.",
        "",
        "| Resultado | Verificação | Detalhes |",
        "|---|---|---|",
    ]
    for check in checks:
        details = check.details.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {check.status} | {check.name} | {details} |")
    lines.extend(
        [
            "",
            "## Interpretação",
            "",
            "- FAIL precisa ser corrigido e a verificação repetida.",
            "- SKIP indica uma etapa que não foi verificada; a borda externa deve ser validada antes da liberação.",
            "- Este relatório não substitui um ensaio destrutivo de restauração em homologação, um teste de entrega SMTP autorizado nem a validação manual de isolamento multi-tenant e do proxy confiável.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Executa verificações de leitura para homologação do UnikSistemas."
    )
    parser.add_argument("--api-url", default="http://127.0.0.1:8000", help="Origem da API.")
    parser.add_argument("--web-url", default="http://127.0.0.1:3000", help="Origem do frontend.")
    parser.add_argument("--public-url", help="Origem HTTPS pública do ambiente de homologação.")
    parser.add_argument("--require-public-url", action="store_true", help="Falha se a borda pública não for verificada.")
    parser.add_argument("--timeout", type=int, default=8, help="Timeout HTTP em segundos (padrão: 8).")
    parser.add_argument("--report", type=Path, help="Grava o relatório Markdown neste caminho.")
    args = parser.parse_args()

    if args.timeout < 1 or args.timeout > 60:
        parser.error("--timeout deve ficar entre 1 e 60 segundos.")

    checks = run_preflight(args)
    report = render_report(checks)
    print(report, end="")
    if args.report:
        try:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(report, encoding="utf-8")
            print(f"\nRelatório salvo em: {args.report}")
        except OSError as exc:
            print(f"\nNão foi possível salvar o relatório ({type(exc).__name__}).", file=sys.stderr)
            return 1

    return 1 if any(check.status == "FAIL" for check in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
