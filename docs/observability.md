# Observabilidade externa — UnikSistemas

## Stack opcional Prometheus + Grafana

O repositório inclui um perfil Docker Compose de monitoramento, desativado por padrão, com versões de imagem fixadas para facilitar revisões reproduzíveis. O stack coleta somente métricas agregadas da API, mantém 15 dias de séries no volume Prometheus e provisiona um dashboard Grafana e regras de alerta.

Antes de iniciar, configure no arquivo `.env`:
- `METRICS_TOKEN`: segredo aleatório com pelo menos 32 caracteres, compartilhado entre a API e o coletor.
- `GRAFANA_ADMIN_PASSWORD`: senha de pelo menos 24 caracteres. O entrypoint do Grafana recusa iniciar com senha vazia ou curta.
- `GRAFANA_ADMIN_USER`: opcional; padrão `admin`.

Gere os segredos com `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Guarde-os em um gerenciador de segredos quando aplicável e não comite nem compartilhe `.env`.

Inicie explicitamente os serviços:

```bash
docker compose --profile monitoring up -d prometheus grafana
docker compose --profile monitoring logs -f prometheus grafana
```

URLs locais: Prometheus <http://127.0.0.1:9090> e Grafana <http://127.0.0.1:3001>. As portas são vinculadas apenas a `127.0.0.1`; não as exponha diretamente à internet nem encaminhe o endpoint `/metrics` em um proxy público. O stack adicional não inicia no comando Compose padrão.

O coletor recebe o token pelo ambiente, escreve-o com permissões restritas em um filesystem temporário e o usa como `credentials_file` no scrape. A proteção de filesystem e o escopo local reduzem a exposição, mas não substituem controles no host: quem puder inspecionar o Docker daemon ou o processo poderá acessar o ambiente do container. Use uma gestão de segredos adequada em ambientes compartilhados.

## Endpoint Prometheus

A API oferece `GET /metrics` com métricas operacionais agregadas, sem rótulos por escritório, cliente, usuário ou documento. O endpoint fica **desativado por padrão** e responde HTTP 404 enquanto `METRICS_TOKEN` não estiver configurado.

Sem token correto, a API responde HTTP 401; quando o endpoint está ativado, respostas autenticadas incluem `Cache-Control: no-store`. O endpoint não substitui `/health/live` ou `/health/ready`.

## Métricas publicadas

| Métrica | Interpretação |
|---|---|
| `unik_antivirus_health_status{status=...}` | Estado do ClamAV em formato one-hot: `healthy`, `unavailable`, `signatures_stale` ou `unknown`. Exatamente um estado vale 1. |
| `unik_antivirus_signature_database_age_seconds` | Idade estimada da data do banco de assinaturas carregado. Consulte também `unik_antivirus_signature_database_known`. |
| `unik_antivirus_last_success_timestamp_seconds` | Timestamp Unix da última verificação bem-sucedida; 0 significa que não há registro. |
| `unik_antivirus_last_check_timestamp_seconds` | Timestamp Unix da última verificação do ClamAV; 0 significa desconhecido. |
| `unik_antivirus_last_cleanup_timestamp_seconds` | Timestamp Unix do último ciclo de limpeza da quarentena; 0 significa desconhecido. |
| `unik_documents_scan_status_count{status=...}` | Quantidade de documentos por estado de análise: pendente, em análise, limpo, infectado ou erro. |
| `unik_documents_infected_payloads_waiting_retention_count` | Payloads infectados ainda aguardando limpeza por retenção. |
| `unik_documents_stale_scans_count` | Análises ainda marcadas como `scanning` sem tentativa recente. |
| `unik_notification_email_status_count{status=...}` | Quantidade de notificações na fila SMTP por estado. |

Os valores são agregados para a instalação inteira e têm conjuntos de rótulos limitados. Não são expostos nomes, e-mails, documentos, chaves de storage, IDs de escritórios ou texto de erros.

## Alertas provisionados

O arquivo `ops/prometheus/alerts.yml` inclui regras para:
- falha ao coletar `/metrics`;
- ClamAV sem estado saudável ou com verificação atrasada;
- documentos com análise em erro ou parada;
- falhas na fila de e-mail.

As regras ficam disponíveis na página **Alerts** do Prometheus. **Elas não entregam notificações externas sem um Alertmanager configurado.** Configure destinos autorizados, política de repetição/agrupamento e responsáveis antes de depender delas operacionalmente. Valide as condições em homologação usando dados fictícios.

## Dashboard Grafana

O dashboard provisionado `UnikSistemas — Operações` exibe estado do ClamAV, idade das assinaturas, erros e análises paradas, fila antimalware, fila SMTP e estado da coleta. O provisionamento vem de arquivos versionados; edições feitas apenas pela interface não são persistidas no repositório.

## Operação e segurança

- Não coloque o token na URL, em dashboards ou em logs.
- Não publique as portas 9090 ou 3001; mantenha-as no loopback ou atrás de uma camada privada autenticada.
- Não compartilhe o token nem a senha do Grafana; o acesso ao Docker daemon deve ser restrito.
- Os volumes `prometheus_data` e `grafana_data` persistem após reinício dos containers.
- A retenção Prometheus está configurada para 15 dias; ajuste-a com avaliação de armazenamento e política de retenção antes de ampliar.
- O stack não instala nem configura Alertmanager, SMTP ou um webhook de alertas. Nenhum destino externo é presumido.
