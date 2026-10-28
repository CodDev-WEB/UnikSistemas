# UnikSistemas
### Sistema integrado para escritórios contábeis

O **UnikSistemas** está começando como uma plataforma web para apoiar escritórios contábeis, com objetivo de evoluir para um SaaS multi-tenant. A fundação inicial inclui uma API autenticada para escritórios e cadastro de clientes, e a primeira interface web conecta o login e a gestão de clientes aos endpoints da API.

> **Status:** MVP inicial em desenvolvimento. Não é um sistema contábil completo e não deve ser usado para processar obrigações fiscais ou dados reais de clientes em produção.

## O que está incluído nesta entrega

- API REST em FastAPI com documentação OpenAPI.
- PostgreSQL, SQLAlchemy e migrações Alembic.
- Provisionamento controlado de escritório e usuário responsável.
- Login por identificador do escritório, e-mail e senha, com JWT de expiração e hashes Argon2.
- Cadastro, listagem e consulta de clientes isolados por tenant.
- Gestão de equipe: criar usuários, consultar a equipe, alterar papéis e ativar/desativar acessos.
- Perfis iniciais: responsável, administrador, contador(a), assistente e consulta (somente leitura).
- Importação assistida de clientes por CSV/XLSX, com prévia, validação, detecção de duplicidades e confirmação explícita.
- Auditoria inicial para criação de clientes, importações confirmadas, alterações de usuários e recebimento/revisão de documentos.
- Recebimento público em quarentena com análise ClamAV assíncrona; downloads e conferência ficam bloqueados até o resultado limpo.
- Caixa de notificações por usuário, alertas diários de prazo e fila de e-mail SMTP opcional para a equipe.
- Interface React + TypeScript com login, painel, busca/filtro e formulário de clientes.
- Nginx servindo a aplicação web e encaminhando chamadas de API pelo mesmo domínio/origem.
- Docker Compose, testes de API, Ruff e GitHub Actions para backend e build do frontend.

Consulte a [arquitetura inicial](docs/architecture-initial.md), o [briefing do sistema contábil](docs/briefing-sistema-contabil.md), o [procedimento de backup e restauração](docs/backup-restore.md) e o [roteiro de prontidão em homologação](docs/homologation-readiness.md).

## Requisitos

- Docker Engine com Docker Compose
- Git
- Segredos aleatórios para `SECRET_KEY` e `BOOTSTRAP_TOKEN`

## Executar localmente

1. Copie `.env.example` para `.env`.
2. Troque `SECRET_KEY`, `BOOTSTRAP_TOKEN` e `POSTGRES_PASSWORD` por valores aleatórios fortes. Atualize também a senha na `DATABASE_URL`; os dois valores precisam corresponder. Para evitar erros de codificação da URL, prefira uma senha aleatória alfanumérica longa ou codifique os caracteres reservados. Nunca use os valores de exemplo em qualquer ambiente compartilhado.
3. Inicie a API, PostgreSQL e frontend:

    docker compose up --build -d
    docker compose logs -f api frontend notification-worker document-scan-worker clamav

4. Acesse a interface em <http://127.0.0.1:3000> e a documentação da API em <http://127.0.0.1:8000/docs>.

Verificações de saúde:
- <http://127.0.0.1:8000/health/live>
- <http://127.0.0.1:8000/health/ready>
- <http://127.0.0.1:3000/health>

As portas estão vinculadas ao loopback por padrão e não expostas diretamente para a rede local.

## Backup e restauração

Os scripts `bash scripts/backup.sh` e `bash scripts/restore.sh CAMINHO_DO_BACKUP` geram e restauram em conjunto o dump PostgreSQL e o volume de documentos. O backup valida os arquivos e cria checksums; a restauração exige confirmação explícita e mantém a API/workers parados se houver erro. **Teste a restauração em homologação isolada antes de qualquer uso com dados reais.** O procedimento completo, os arquivos incluídos e a lista de validação estão em [Backup e restauração](docs/backup-restore.md). Antes de liberar homologação, use também `python scripts/staging_readiness.py` e siga o [roteiro de prontidão](docs/homologation-readiness.md); essa pré-verificação não substitui o ensaio real de restauração nem o teste autorizado de SMTP.

## Provisionar o primeiro escritório

O segredo de provisionamento em `BOOTSTRAP_TOKEN` deve ser usado apenas pelo operador autorizado. Exemplo via curl:

    curl -X POST http://127.0.0.1:8000/api/v1/setup/tenants \
      -H "Content-Type: application/json" \
      -H "X-Bootstrap-Token: SUBSTITUA_PELO_SEU_SEGREDO" \
      -d '{
        "tenant_name": "Escritório Exemplo",
        "tenant_slug": "escritorio-exemplo",
        "owner_email": "responsavel@example.com",
        "owner_full_name": "Responsável do Escritório",
        "owner_password": "Use-Uma-Senha-Forte-Aqui-2026"
      }'

Na primeira versão, o provisionamento é uma operação do operador, não um cadastro público. Depois, entre na interface usando o slug do escritório, e-mail e senha do usuário owner criado. O frontend armazena o token no `sessionStorage` e o descarta ao sair; antes de produção, a estratégia de sessão deve passar por revisão específica de segurança.

**Não comite `.env` e não compartilhe o segredo de provisionamento.** Rotacione/remova `BOOTSTRAP_TOKEN` quando não for mais necessário.

## Executar testes localmente

Backend:

    python -m venv .venv
    # Windows PowerShell: .venv\Scripts\Activate.ps1
    # Linux/macOS: source .venv/bin/activate
    pip install -r requirements-dev.txt
    ruff check app tests
    pytest -q

Frontend:

    cd frontend
    npm install
    npm run build

O CI executa lint, testes do backend e migração contra PostgreSQL, além de compilar o frontend.

## Funcionalidades ainda não implementadas

- E-mails automáticos enviados aos clientes, convites por e-mail, recuperação de senha e MFA.
- Integrações fiscais, envio de declarações ou automações irreversíveis.
- Observabilidade externa e restauração de backup validada em homologação.
- Estratégia de sessão adequada para produção, gestão de segredos e implantação com HTTPS.
- Revisão contínua do scanner e plano de resposta a incidentes.

O recebimento de arquivos usa ClamAV em serviço isolado, com base de assinaturas persistida. A primeira inicialização pode levar vários minutos enquanto as assinaturas são baixadas e carregadas. Reserve cerca de 4 GiB de memória para o contêiner ClamAV. O worker consulta `VERSION` a cada ciclo e só processa a fila quando o scanner responde e a base de assinaturas tem até `ANTIVIRUS_SIGNATURE_MAX_AGE_HOURS` horas (padrão: 72). Se o scanner estiver indisponível ou as assinaturas estiverem antigas, a análise é pausada e responsáveis/administradores recebem alerta interno. Na página **Notificações**, responsáveis e administradores veem o estado do scanner, a idade das assinaturas e as contagens da própria organização. Os novos envios ficam em `quarantine/` e só são movidos para `clean/` após resultado limpo. Conteúdos infectados são removidos após `ANTIVIRUS_INFECTED_RETENTION_DAYS` dias (padrão: 30), mantendo metadados e o registro de auditoria. Falhas de limpeza são tentadas novamente em ciclos posteriores. Para acompanhar a análise, use `docker compose logs -f document-scan-worker clamav`.

O perfil de produção também exige PostgreSQL via `postgresql+psycopg` e senha de banco com ao menos 24 caracteres; as rotas de documentação OpenAPI são desativadas nesse perfil. O Nginx aplica cabeçalhos básicos de proteção no navegador e limites de requisição para login (5/min, burst 4), provisionamento (2/min, burst 1), consulta pública de links (30/min, burst 10) e envio de arquivos (6/min, burst 2). Esses limites são aplicados na borda Nginx e usam `X-Real-IP` quando informado; o proxy HTTPS externo deve **sobrescrever** esse cabeçalho com o IP real do cliente, nunca confiar no valor enviado pelo próprio cliente. Se o proxy não estiver configurado para isso, os limites podem compartilhar o mesmo bucket entre usuários. Não exponha a API diretamente e não publique o serviço frontend fora do proxy confiável. O proxy de borda ainda deve terminar TLS/HTTPS e aplicar HSTS.

Não exponha a aplicação à internet antes de implementar e revisar esses controles. Use dados fictícios nos testes e não envie dados de clientes a modelos de IA sem avaliar previamente as condições de tratamento aplicáveis.

## Importação assistida de clientes

Acesse **Importações** pelo menu lateral para enviar CSV (UTF-8 ou Windows-1252) ou Excel (.xlsx). A planilha precisa ter uma primeira linha com títulos e a coluna **Razão Social** (ou `legal_name`). Colunas opcionais reconhecidas: Nome Fantasia, CNPJ/CPF, E-mail, Telefone e Status. O MVP aceita até 5 MiB e 1.000 linhas por arquivo.

A importação é dividida em etapas: envio e validação, revisão das linhas sinalizadas e confirmação explícita. Se houver linha inválida ou identificador fiscal duplicado, o lote inteiro fica bloqueado; nenhum cliente é gravado parcialmente. A confirmação é transacional, restrita ao escritório autenticado e não pode ser repetida. Após a confirmação ou descarte, o conteúdo da prévia é apagado; o registro resumido permanece no histórico e gera auditoria.

Na tela **Importações**, baixe o modelo CSV ou Excel, preencha uma linha por cliente e consulte o histórico dos últimos 50 lotes, com arquivo, data, responsável, situação e total importado. Lotes pendentes podem ser abertos ou descartados. O modelo Excel inclui uma aba de instruções; mantenha CNPJ/CPF como texto para preservar zeros à esquerda.

Endpoints: `GET /api/v1/imports/client-template.csv`, `GET /api/v1/imports/client-template.xlsx`, `GET /api/v1/imports/clients?limit=50`, `POST /api/v1/imports/clients/preview` (multipart com campo `file`), `GET /api/v1/imports/clients/{batch_id}`, `POST /api/v1/imports/clients/{batch_id}/confirm` e `DELETE /api/v1/imports/clients/{batch_id}` (descarta o lote mantendo histórico). Os perfis de consulta (viewer) não podem importar ou consultar o histórico.

## Pendências e documentos por cliente

Acesse **Pendências e documentos** no menu lateral para registrar documentos solicitados, acompanhamentos e rotinas internas vinculadas a um cliente. Cada item pode ter descrição, prioridade, prazo e um responsável interno ativo do mesmo escritório.

Situações disponíveis: **Pendente**, **Recebido**, **Concluído** e **Cancelado**. Documentos podem ser marcados como recebidos e depois concluídos; itens encerrados podem ser reabertos. Pendências vencidas são destacadas na tela. Alterações e mudanças de estado geram eventos na auditoria.

Endpoints: `GET /api/v1/tasks?limit=100` com filtros opcionais `status` e `client_id`; `POST /api/v1/tasks` para criar e `PATCH /api/v1/tasks/{task_id}` para atualizar. O perfil Consulta pode visualizar, mas não criar nem atualizar. Todos os acessos são limitados ao escritório do token; cliente e responsável atribuídos são validados no servidor.

Este módulo é um controle operacional manual. Pendências do tipo Documento podem gerar um link temporário de envio: o link expira em 7 dias, admite até 5 arquivos e pode ser revogado pela equipe; a emissão de um novo link invalida o anterior. O portal aceita PDF, PNG, JPG, CSV, XLSX e DOCX, com limite de 10 MiB por arquivo e verificação básica do formato. A equipe autenticada pode baixar os anexos e registrar conferência ou pedido de correção; downloads, recebimentos e revisões geram auditoria. O recebimento não envia e-mails nem transmite declarações, calcula tributos ou executa prazos fiscais automaticamente.

O armazenamento padrão usa volume persistente Docker (`document_uploads`) no caminho configurado por `DOCUMENT_STORAGE_PATH`. Antes de produção, configure HTTPS, limites de taxa, antivírus/inspeção de arquivos, política de retenção e backup testado. Não compartilhe links de envio em canais públicos; quem possui o link pode enviar arquivos para a pendência correspondente.


## Central de notificações e alertas

Acesse **Notificações** pela navegação lateral ou pelo ícone de sino. A caixa é pessoal: cada usuário vê apenas os próprios avisos, pode marcar um aviso ou todos como lidos e acompanha eventos de atribuição de pendências e recebimento de documentos.

O worker dedicado verifica a cada minuto as pendências abertas ou recebidas com prazo até amanhã, no fuso configurado em `NOTIFICATION_TIMEZONE`. Um mesmo usuário recebe no máximo um lembrete por pendência por dia; tarefas concluídas ou canceladas não geram novos alertas. O responsável ou administrador também pode solicitar uma verificação imediata pela tela.

O envio de e-mails é **desabilitado por padrão**. Para ativá-lo, configure no arquivo de ambiente do servidor: `EMAIL_NOTIFICATIONS_ENABLED=true`, `EMAIL_QUEUE_MAX_AGE_HOURS=24`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL` e, quando exigidos pelo provedor, `SMTP_USERNAME` e `SMTP_PASSWORD`. Use `SMTP_STARTTLS=true` para STARTTLS, que é a opção padrão na porta 587. Para SSL direto, habilite `SMTP_USE_SSL=true` e defina `SMTP_STARTTLS=false`. `APP_BASE_URL` deve apontar para a origem HTTPS real da aplicação e `NOTIFICATION_TIMEZONE` deve ser um fuso IANA válido. Nunca coloque credenciais SMTP no repositório.

Quando a configuração está desligada, os avisos continuam aparecendo dentro do sistema e nenhum e-mail é enviado. A fila automática tem idade máxima configurável por `EMAIL_QUEUE_MAX_AGE_HOURS` (padrão: 24 horas; faixa aceita: 1 a 720 horas). Ao habilitar SMTP, registros pendentes mais antigos que esse limite são marcados como expirados/falhos e **não são enviados automaticamente**. O responsável ou administrador pode revisar a situação e solicitar um reenvio explícito; essa ação reinicia a idade da fila e registra auditoria. O estado “Expirados” na tela mostra quantos e-mails requerem essa decisão manual. As falhas de entrega também ficam registradas para reenvio após a correção da configuração.

Endpoints: `GET /api/v1/notifications?limit=50`, `GET /api/v1/notifications?unread_only=true`, `PATCH /api/v1/notifications/{notification_id}/read`, `POST /api/v1/notifications/read-all`, `GET /api/v1/notifications/email-status`, `POST /api/v1/notifications/process-due-reminders`, `POST /api/v1/notifications/{notification_id}/retry-email` e `POST /api/v1/notifications/retry-failed-emails` para reenfileirar e-mails com falha do escritório. Os endpoints de fila e de lembretes manuais exigem o perfil responsável ou administrador; a caixa é sempre restrita ao usuário autenticado e ao escritório.

Em execução local, acompanhe o worker com `docker compose logs -f notification-worker`. Antes de produção, faça um teste real com um destinatário interno autorizado, verifique entrega e spam e documente o procedimento de rotação de credenciais SMTP.

## Perfis de acesso

| Perfil | Permissões iniciais |
|---|---|
| Responsável | Administra a equipe e os clientes do escritório |
| Administrador | Gerencia usuários comuns e clientes; não gerencia o responsável nem outros administradores |
| Contador(a) | Consulta e cadastra clientes |
| Assistente | Consulta e cadastra clientes |
| Consulta | Visualiza clientes; não cadastra nem administra usuários |

O perfil é verificado pela API, não apenas pela interface. Usuários e clientes são sempre consultados dentro do escritório associado ao token. A senha inicial é armazenada em hash, mas a entrega segura da senha ao colaborador ainda é um processo manual e deve ser feita por um canal seguro.

## Desenvolvimento

Abra uma branch por tarefa, mantenha diffs pequenos, escreva testes e documente decisões. Toda mudança deve passar por Pull Request e aprovação humana antes de integrar à branch principal. Deploy deve ser uma etapa separada e autorizada.

As APIs de ChatGPT e Claude são ferramentas de apoio ao desenvolvimento, não fontes de verdade para regras fiscais. Regras tributárias e obrigações legais exigem fontes oficiais e validação profissional.

## Licença

Consulte o arquivo [LICENSE](LICENSE).
