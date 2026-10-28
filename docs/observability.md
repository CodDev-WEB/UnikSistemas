# Observabilidade externa — UnikSistemas

## Endpoint Prometheus

A API oferece `GET /metrics` com métricas operacionais agregadas, sem rótulos por escritório, cliente, usuário ou documento. O endpoint fica **desativado por padrão** e responde HTTP 404 enquanto `METRICS_TOKEN` não estiver configurado.

Gere um segredo aleatório no servidor, por exemplo:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Configure o resultado como `METRICS_TOKEN` no ambiente da API. Não coloque o segredo no repositório, em URL, em dashboards ou nos logs. O token deve ter pelo menos 32 caracteres. Reinicie a API após alterar o ambiente.

O coletor de métricas deve consultar o endpoint por uma rede privada ou por uma regra de firewall/proxy que permita somente o coletor autorizado:

```bash
curl --fail --silent --show-error \
  -H "Authorization: Bearer $METRICS_TOKEN" \
  http://127.0.0.1:8000/metrics
```

Sem o token correto, a API responde HTTP 401; com o endpoint desativado, responde 404. As respostas autenticadas incluem `Cache-Control: no-store`. O endpoint não é um substituto para `/health/live` ou `/health/ready` e não instala nem administra Prometheus, Grafana ou um serviço de alertas.

## Métricas publicadas

| Métrica | Interpretação |
|---|---|
| `unik_antivirus_health_status{status=...}` | Estado do ClamAV em formato one-hot: `healthy`, `unavailable`, `signatures_stale` ou `unknown`. Exatamente um estado vale 1. |
| `unik_antivirus_signature_database_age_seconds` | Idade estimada da data do banco de assinaturas carregado. Consulte também a métrica `unik_antivirus_signature_database_known`. |
| `unik_antivirus_last_success_timestamp_seconds` | Timestamp Unix da última verificação bem-sucedida; 0 significa que não há registro. |
| `unik_antivirus_last_check_timestamp_seconds` | Timestamp Unix da última verificação do ClamAV; 0 significa desconhecido. |
| `unik_antivirus_last_cleanup_timestamp_seconds` | Timestamp Unix do último ciclo registrado de limpeza da quarentena; 0 significa desconhecido. |
| `unik_documents_scan_status_count{status=...}` | Quantidade de documentos por estado de análise antimalware: pendente, em análise, limpo, infectado ou erro. |
| `unik_documents_infected_payloads_waiting_retention_count` | Quantidade de payloads infectados ainda aguardando a limpeza por retenção. |
| `unik_documents_stale_scans_count` | Análises que continuam como `scanning` apesar de não haver tentativa registrada nos últimos cinco minutos. |
| `unik_notification_email_status_count{status=...}` | Quantidade de notificações na fila SMTP por estado: pendente, enviada ou falha. |

Os valores são agregados para a instalação inteira e têm conjuntos de rótulos limitados. Não são expostos nomes, e-mails, documentos, chaves de storage, IDs de escritórios ou texto de erros. Métricas de timestamp com valor 0 não comprovam atividade; trate-as como ausência de evidência.

## Ideias de alertas para o coletor

Ajuste nomes e intervalos à política operacional do ambiente. Exemplos para Prometheus:

```promql
sum(unik_antivirus_health_status{status="healthy"}) == 0
```

```promql
unik_documents_scan_status_count{status="error"} > 0
```

```promql
unik_documents_stale_scans_count > 0
```

```promql
time() - unik_antivirus_last_check_timestamp_seconds > 600
```

Antes de criar alertas de página, valide o comportamento com dados fictícios em homologação e defina quem recebe, o tempo de resposta esperado e como encerrar cada incidente. Arquivos infectados aguardando o prazo de retenção não significam, isoladamente, falha: acompanhe-os segundo a política documentada e alerte principalmente quando a limpeza falhar ou acumular atraso.

## Operação e segurança

- Não configure o token na URL nem em um cabeçalho enviado pelo browser do usuário.
- Restrinja o acesso ao endpoint no proxy de borda e na rede; um token não torna recomendável deixá-lo publicamente acessível.
- Armazene o token em um gerenciador de segredos, permita rotação e não o inclua em relatórios.
- Configure o Prometheus/Grafana ou outro coletor externo separadamente. A API expõe métricas, mas não persiste séries temporais e não envia alertas externos por conta própria.
- Compare as métricas com os alertas internos da Central de Notificações e com logs de `document-scan-worker`, `notification-worker`, ClamAV, PostgreSQL e proxy.
- Valide `/health/live`, `/health/ready`, a restauração de backups, o SMTP e a configuração de TLS/HSTS de forma independente antes de homologar a produção.
