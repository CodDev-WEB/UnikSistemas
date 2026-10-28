# Prontidão de homologação — UnikSistemas

## Objetivo e limites

Use este roteiro num ambiente **isolado de homologação**, com contas, clientes e documentos fictícios. A verificação automática é somente leitura: valida Docker Compose, serviços em execução, endpoints de saúde, migrações aplicadas, estado persistido do ClamAV e atualidade das assinaturas. Ela não cria backup, para serviços, envia e-mails, altera configurações, restaura dados nem remove arquivos.

Um relatório verde não autoriza produção por si só. A restauração completa, o envio real de SMTP, o isolamento entre escritórios e a configuração do proxy precisam de evidência própria.

## 1. Pré-verificação automática

Na raiz do repositório, com o arquivo de ambiente de homologação e os serviços já iniciados:

~~~bash
python scripts/staging_readiness.py
~~~

Para guardar o resultado e incluir a borda pública:

~~~bash
python scripts/staging_readiness.py \
  --public-url https://staging.exemplo.com \
  --require-public-url \
  --report /tmp/unik-staging-readiness.md
~~~

Substitua a URL de exemplo pelo domínio real do ambiente. O script também aceita as opções --api-url e --web-url se as portas locais forem diferentes. O código de saída é diferente de zero quando uma verificação falha. Um resultado SKIP significa que aquela etapa não foi comprovada; não deve ser tratado como aprovação.

A pré-verificação exige:
- serviços db, api, frontend, clamav, document-scan-worker e notification-worker em execução;
- /health/live, /health/ready e o health check do frontend respondendo;
- revisão atual do banco correspondente à revisão head do Alembic;
- consulta real ao ClamAV com assinaturas dentro do limite configurado, além de estado de saúde persistido recente;
- se --public-url for fornecida, HTTPS funcional, HSTS, cabeçalhos de proteção e redirecionamento HTTP para HTTPS.

Não anexe relatórios contendo informações internas em canais públicos. O script não imprime segredos do arquivo de ambiente.

## 2. Ensaio de backup e restauração

Faça esta etapa apenas numa instalação descartável de homologação. O backup para temporariamente a API e os workers de escrita; a restauração substitui banco e arquivos atuais.

1. Leia [Backup e restauração](backup-restore.md) até o fim e confirme que o alvo é o ambiente de homologação, não produção.
2. Execute bash scripts/backup.sh e registre o diretório, o horário e o resultado da validação de SHA256SUMS.
3. Copie o backup para um segundo local autorizado e protegido, quando aplicável ao ambiente de teste.
4. Prepare um estado descartável, restaure com bash scripts/restore.sh CAMINHO_DO_BACKUP e confirme explicitamente a operação ao digitar RESTORE-UNIK.
5. Depois da restauração, confira /health/ready, login com usuário de teste, clientes, permissões, pendências, notificações, auditoria e consistência entre registros de documentos e arquivos. Teste download de um documento limpo e bloqueio de um documento em quarentena.
6. Registre início/fim, duração, falhas e o resultado de cada verificação. Não basta que o comando de restauração tenha terminado sem erro.

**Nunca execute o ensaio de restauração no ambiente de produção nem com dados reais sem uma janela de manutenção e autorização formal.**

## 3. Resiliência do ClamAV

Os testes automatizados do repositório cobrem falha de conexão, resposta inválida, assinaturas antigas, alertas de transição e recuperação. O teste do worker confirma também que a fila não é processada enquanto o scanner está indisponível ou as assinaturas estão vencidas, e que o alerta operacional alcança os responsáveis/administradores dos escritórios de teste:

~~~bash
pytest -q tests/test_antivirus.py tests/test_antivirus_worker.py tests/test_api.py -k antivirus
~~~

Para validar o comportamento operacional numa instância descartável, interrompa temporariamente o serviço ClamAV e confirme que a saúde muda para indisponível, os documentos novos permanecem em quarentena e os responsáveis/administradores recebem apenas um alerta por transição. Reinicie o serviço e confirme que há alerta de recuperação e que a fila retoma o processamento quando a saúde volta a healthy.

Faça essa simulação somente em homologação: parar o ClamAV pausa as análises de documentos. A lógica de assinaturas vencidas é coberta pelos testes com relógio e resposta do scanner controlados, sem alterar artificialmente a base de assinaturas de produção.

## 4. Teste de e-mail com destinatário autorizado

1. Mantenha SMTP desativado até que servidor, remetente e política de segurança tenham sido revisados.
2. Em homologação, habilite SMTP com credenciais armazenadas apenas no ambiente e use uma caixa interna autorizada.
3. Gere uma notificação de teste pelo fluxo normal do sistema (por exemplo, atribua uma pendência fictícia a um usuário de teste).
4. Verifique recebimento, spam, destinatário, links, email_status e logs do notification-worker.
5. Confirme que notificações antigas que excederam EMAIL_QUEUE_MAX_AGE_HOURS não são enviadas sem reenvio explícito.
6. Desative ou remova a configuração de teste e não registre senhas, tokens ou conteúdo sensível no relatório.

A existência de uma notificação dentro do sistema não prova a entrega externa do e-mail.

## 5. Isolamento entre escritórios

Execute os testes de regressão de autorização e antivírus:

~~~bash
pytest -q tests/test_api.py -k "tenant or antivirus_status"
~~~

Em homologação, confirme também manualmente com dois escritórios fictícios: um não deve conseguir listar ou baixar os documentos, ver as notificações ou consultar contagens do outro. Faça o teste com perfis de responsável, administrador e consulta.

## 6. Proxy, TLS e limites de requisição

Com a URL pública real:
- confirme que HTTP redireciona para HTTPS e que o certificado TLS é válido;
- confira HSTS e os cabeçalhos X-Content-Type-Options, X-Frame-Options e Referrer-Policy;
- verifique que o proxy de borda sobrescreve X-Real-IP com o endereço remoto real, em vez de confiar no cabeçalho fornecido pelo navegador;
- valide que os limites de requisição do Nginx funcionam sem expor diretamente as portas de API ou frontend à internet;
- confirme que os logs do proxy não registram tokens de links nem dados pessoais desnecessários.

O script automatiza parte das verificações HTTP, mas não prova a configuração do IP confiável nem o comportamento de rate limiting. Esses pontos exigem inspeção e teste no proxy que realmente atende o domínio.

## 7. Registro de evidências

Registre, sem dados pessoais ou segredos:

| Campo | Registro |
|---|---|
| Data/hora UTC | |
| Ambiente e commit validado | |
| Relatório automático e resultado | |
| Backup/checksum e local protegido | |
| Restauração isolada: duração e resultado | |
| ClamAV indisponível/recuperado | |
| SMTP: destinatário de teste autorizado e resultado | |
| Isolamento multi-tenant e perfis | |
| TLS/HSTS, IP confiável e rate limiting | |
| Pendências, responsável e decisão final | |

**Critério de conclusão:** nenhum FAIL sem correção e nova execução; todos os SKIP relevantes resolvidos por verificação manual; restauração completa comprovada; SMTP e controles de borda testados; aprovação explícita do responsável. Até então, mantenha o sistema em homologação.
