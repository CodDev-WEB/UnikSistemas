# Arquitetura atual — UnikSistemas

## Componentes

- **Frontend:** React + TypeScript + Vite; servido pelo Nginx e encaminhando `/api/` para a API na mesma origem.
- **API:** FastAPI / Python 3.12 com autenticação JWT Bearer e senhas em Argon2.
- **Banco:** PostgreSQL; SQLAlchemy 2 e migrações Alembic.
- **Armazenamento de arquivos:** volume persistente Docker configurado por `DOCUMENT_STORAGE_PATH`.
- **Worker:** processo separado que gera lembretes e processa a fila SMTP quando o envio estiver habilitado.
- **Qualidade:** pytest, Ruff, build do frontend e migração PostgreSQL em GitHub Actions.

## Recursos já implementados

1. Provisionamento de escritório controlado e login por slug, e-mail e senha.
2. Isolamento por `tenant_id` para cadastros, equipe, pendências, documentos e notificações.
3. Papéis `owner`, `admin`, `accountant`, `assistant` e `viewer`, com verificações no backend.
4. Cadastro de clientes e importação CSV/XLSX com prévia, validação, confirmação explícita, modelos e histórico.
5. Pendências por cliente com responsável, prioridade, prazo e estado.
6. Link público temporário para envio de documentos, com expiração, limite de uploads, revogação, metadados, download autenticado e revisão pela equipe.
7. Caixa de notificações por usuário para documentos recebidos, novas atribuições e lembretes de prazo.
8. Fila de e-mail SMTP opcional, desabilitada por padrão, com estado de entrega e reenvio manual de falhas.
9. Auditoria de operações relevantes e pipeline automatizado de testes.

## Principais fluxos de segurança

- A API determina o escritório a partir do token validado; não confia no `tenant_id` fornecido pelo cliente.
- Listas, alterações e downloads filtram o recurso pelo escritório autenticado; notificações são também restritas ao destinatário.
- O perfil de Consulta é somente leitura para os módulos operacionais.
- Links de upload armazenam apenas o hash do token, expiram em sete dias e aceitam até cinco arquivos de até 10 MiB. O Nginx aplica rate limiting distinto a login, provisionamento, consulta do link e transferência de arquivos.
- Cada novo documento é gravado em `quarantine/`, varrido por ClamAV em worker separado e movido a `clean/` somente após resposta limpa; a API bloqueia download e conferência enquanto não estiver limpo.
- Credenciais SMTP são lidas do ambiente. O worker não tenta entregar e-mails enquanto `EMAIL_NOTIFICATIONS_ENABLED=false`.
- O perfil `production` exige PostgreSQL via psycopg, segredos fortes e senha de banco com pelo menos 24 caracteres.

## Limites e riscos remanescentes

- O MVP não é um sistema contábil/fiscal completo: não transmite declarações, calcula tributos nem integra serviços fiscais oficiais.
- ClamAV e a quarentena reduzem o risco de liberar arquivos maliciosos, mas não são garantia absoluta: assinaturas podem não detectar ameaças novas. Os arquivos infectados permanecem bloqueados em quarentena até política operacional de retenção e remoção.
- O rate limiting existe no Nginx, mas depende de o proxy externo sobrescrever `X-Real-IP` com o endereço real do cliente; sem essa configuração, muitos usuários podem compartilhar um bucket.
- A proteção de segredos e banco em produção exige secret manager, política de rotação e backups com restauração testada.
- O deploy precisa de TLS/HTTPS, HSTS na borda, monitoramento, alertas e estratégia de retenção de documentos.
- A autenticação ainda usa token no `sessionStorage`; revisar sessão, proteção contra XSS, recuperação de senha e MFA antes de uso externo.
- A fila SMTP exige teste real em homologação, política para e-mails antigos acumulados e verificação de entrega/reenvio.
- O CORS atual permite PATCH e DELETE para eventuais frontends em origem separada; o caminho recomendado continua sendo frontend/API na mesma origem.
- Não são aceitos dados reais de clientes em desenvolvimento/testes. Regras tributárias dependem de fonte oficial e revisão profissional.

## Próxima etapa recomendada

Antes de módulos fiscais, concluir uma etapa de prontidão operacional: verificar atualização e disponibilidade das assinaturas ClamAV, política de limpeza da quarentena, teste do transporte SMTP com mock e homologação, política para fila acumulada, revisão independente do isolamento multi-tenant, backup/restauração e definição de ambiente de staging. Também deve ser validada a configuração do proxy de borda para IP real, TLS/HSTS e observabilidade. Só depois preparar deployment HTTPS com segredos protegidos e aprovação humana.
