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
- Auditoria inicial para criação de clientes, importações confirmadas e alterações de usuários.
- Interface React + TypeScript com login, painel, busca/filtro e formulário de clientes.
- Nginx servindo a aplicação web e encaminhando chamadas de API pelo mesmo domínio/origem.
- Docker Compose, testes de API, Ruff e GitHub Actions para backend e build do frontend.

Consulte a [arquitetura inicial](docs/architecture-initial.md) e o [briefing do sistema contábil](docs/briefing-sistema-contabil.md).

## Requisitos

- Docker Engine com Docker Compose
- Git
- Segredos aleatórios para `SECRET_KEY` e `BOOTSTRAP_TOKEN`

## Executar localmente

1. Copie `.env.example` para `.env`.
2. Troque `SECRET_KEY` e `BOOTSTRAP_TOKEN` por valores aleatórios fortes. Nunca use os valores de exemplo fora do desenvolvimento local.
3. Inicie a API, PostgreSQL e frontend:

    docker compose up --build -d
    docker compose logs -f api frontend

4. Acesse a interface em <http://127.0.0.1:3000> e a documentação da API em <http://127.0.0.1:8000/docs>.

Verificações de saúde:
- <http://127.0.0.1:8000/health/live>
- <http://127.0.0.1:8000/health/ready>
- <http://127.0.0.1:3000/health>

As portas estão vinculadas ao loopback por padrão e não expostas diretamente para a rede local.

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

- Convites por e-mail, recuperação de senha e MFA.
- Gestão documental, pendências e rotinas contábeis.
- Integrações fiscais, envio de declarações ou automações irreversíveis.
- Limites de requisição, rate limiting, observabilidade avançada e procedimento validado de backup/restauração.
- Estratégia de sessão adequada para produção, gestão de segredos e implantação com HTTPS.

Não exponha a aplicação à internet antes de implementar e revisar esses controles. Use dados fictícios nos testes e não envie dados de clientes a modelos de IA sem avaliar previamente as condições de tratamento aplicáveis.

## Importação assistida de clientes

Acesse **Importações** pelo menu lateral para enviar CSV (UTF-8 ou Windows-1252) ou Excel (.xlsx). A planilha precisa ter uma primeira linha com títulos e a coluna **Razão Social** (ou `legal_name`). Colunas opcionais reconhecidas: Nome Fantasia, CNPJ/CPF, E-mail, Telefone e Status. O MVP aceita até 5 MiB e 1.000 linhas por arquivo.

A importação é dividida em etapas: envio e validação, revisão das linhas sinalizadas e confirmação explícita. Se houver linha inválida ou identificador fiscal duplicado, o lote inteiro fica bloqueado; nenhum cliente é gravado parcialmente. A confirmação é transacional, restrita ao escritório autenticado e não pode ser repetida. Após a confirmação ou descarte, o conteúdo da prévia é apagado; o registro resumido permanece no histórico e gera auditoria.

Na tela **Importações**, baixe o modelo CSV ou Excel, preencha uma linha por cliente e consulte o histórico dos últimos 50 lotes, com arquivo, data, responsável, situação e total importado. Lotes pendentes podem ser abertos ou descartados. O modelo Excel inclui uma aba de instruções; mantenha CNPJ/CPF como texto para preservar zeros à esquerda.

Endpoints: `GET /api/v1/imports/client-template.csv`, `GET /api/v1/imports/client-template.xlsx`, `GET /api/v1/imports/clients?limit=50`, `POST /api/v1/imports/clients/preview` (multipart com campo `file`), `GET /api/v1/imports/clients/{batch_id}`, `POST /api/v1/imports/clients/{batch_id}/confirm` e `DELETE /api/v1/imports/clients/{batch_id}` (descarta o lote mantendo histórico). Os perfis de consulta (viewer) não podem importar ou consultar o histórico.

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
