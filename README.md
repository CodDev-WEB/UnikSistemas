# UnikSistemas
### Sistema integrado para escritórios contábeis

O **UnikSistemas** está começando como uma plataforma web para apoiar escritórios contábeis, com objetivo de evoluir para um SaaS multi-tenant. Esta primeira entrega implementa uma fundação de API: escritórios, usuário responsável, autenticação e cadastro inicial de clientes com isolamento por tenant.

> **Status:** fundação técnica inicial em desenvolvimento. Ainda não é um sistema contábil completo e não deve ser usado para processar obrigações fiscais ou dados reais de clientes em produção.

## O que esta versão implementa

- API REST em FastAPI com documentação OpenAPI.
- PostgreSQL e migrações de banco com Alembic.
- Provisionamento controlado de um escritório e seu usuário owner por meio de segredo operacional.
- Login com slug do escritório, e-mail e senha.
- JWT Bearer com expiração e armazenamento de senha com Argon2.
- Cadastro e listagem de clientes.
- Consultas de clientes limitadas ao tenant extraído do token validado no servidor.
- Registro de auditoria na criação de clientes.
- Docker Compose, testes automatizados, Ruff e GitHub Actions.

Consulte a [arquitetura inicial](docs/architecture-initial.md) e o [briefing do sistema contábil](docs/briefing-sistema-contabil.md).

## Requisitos

- Docker Engine com Docker Compose
- Git
- Um segredo aleatório para SECRET_KEY e outro para BOOTSTRAP_TOKEN

## Executar localmente

1. Copie .env.example para .env.
2. Altere SECRET_KEY e BOOTSTRAP_TOKEN para valores aleatórios fortes. Nunca use os valores de exemplo fora de desenvolvimento local.
3. Inicie os serviços:

    docker compose up --build -d
    docker compose logs -f api

A API fica vinculada a 127.0.0.1:8000 por padrão para não ser exposta diretamente à rede. Documentação: <http://127.0.0.1:8000/docs>.

Verifique:
- <http://127.0.0.1:8000/health/live>
- <http://127.0.0.1:8000/health/ready>

## Provisionar o primeiro escritório

O segredo de provisionamento configurado em BOOTSTRAP_TOKEN deve ser enviado apenas pelo operador autorizado. Exemplo via curl:

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

Depois, autentique-se em POST /api/v1/auth/token enviando tenant_slug, email e password. Use o access_token retornado no cabeçalho Authorization: Bearer ....

**Não comite .env e não compartilhe o segredo de provisionamento.** Após criar o tenant inicial, remova ou rotacione BOOTSTRAP_TOKEN se não precisar provisionar outros escritórios.

## Executar testes localmente

    python -m venv .venv
    # Windows PowerShell: .venv\Scripts\Activate.ps1
    # Linux/macOS: source .venv/bin/activate
    pip install -r requirements-dev.txt
    ruff check app tests
    pytest -q

Os testes de API usam um banco SQLite efêmero. O workflow do GitHub Actions também verifica as migrações contra PostgreSQL.

## Segurança e escopo

- Não exponha a API diretamente à internet sem HTTPS, proxy/gateway, rate limiting, logs e monitoramento.
- A base inicial ainda não implementa MFA, recuperação de senha, gestão completa de usuários e papéis, importação de arquivos, integrações fiscais, frontend ou deploy.
- Use dados fictícios nos testes. Não envie documentos fiscais ou dados pessoais a modelos de IA sem avaliação prévia das condições de tratamento.
- Toda mudança deve passar por testes e Pull Request; merge e deploy exigem aprovação humana.

## Desenvolvimento

Abra uma branch por tarefa, mantenha diffs pequenos, escreva testes e documente decisões. A integração ChatGPT + Claude apoia o desenvolvimento, mas não substitui validação profissional nem fontes oficiais para regras fiscais.

## Licença

Consulte o arquivo [LICENSE](LICENSE).
