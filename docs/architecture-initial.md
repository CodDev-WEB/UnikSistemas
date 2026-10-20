# Arquitetura inicial — UnikSistemas

## Decisões da primeira entrega

- API REST: FastAPI com documentação OpenAPI.
- Linguagem: Python 3.12.
- Persistência: PostgreSQL; SQLite usado somente em testes rápidos.
- ORM e migrações: SQLAlchemy 2 e Alembic.
- Autenticação: JWT Bearer com expiração; senhas armazenadas com Argon2.
- Isolamento multi-tenant: o usuário pertence a um tenant; o tenant é obtido do token validado e as consultas de clientes são filtradas no servidor pelo tenant_id.
- Operação local: Docker Compose com API e PostgreSQL.
- Qualidade: pytest, Ruff e verificação de migrações no GitHub Actions.
- Entrega: branch de funcionalidade e Pull Request; sem merge ou deploy automático.

## Endpoints iniciais

| Método | Endpoint | Descrição |
|---|---|---|
| GET | /health/live | Liveness sem dependência do banco |
| GET | /health/ready | Verifica conexão com o banco |
| POST | /api/v1/setup/tenants | Provisiona um tenant e seu owner com segredo operacional |
| POST | /api/v1/auth/token | Login por slug do escritório, e-mail e senha |
| GET | /api/v1/me | Retorna o usuário autenticado e o tenant |
| GET | /api/v1/clients | Lista clientes somente do tenant autenticado |
| POST | /api/v1/clients | Cria cliente e gera evento de auditoria |
| GET | /api/v1/clients/{client_id} | Consulta um cliente dentro do tenant autenticado |

## Limites conhecidos

Esta entrega é uma fundação, não um sistema contábil pronto para produção.

- Provisionamento de tenant exige segredo operacional. Remova ou rotacione BOOTSTRAP_TOKEN após o provisionamento quando não for necessário.
- Ainda não existe recuperação de senha, MFA, gestão completa de usuários/perfis, rate limiting, fila de tarefas, frontend ou integrações fiscais.
- Auditoria inicial cobre criação de clientes; precisa ser ampliada e protegida conforme requisitos de auditoria.
- Não há validação de dígitos verificadores nem consulta oficial para identificadores fiscais.
- Antes de uso público, adicionar rate limiting, secret manager, HTTPS/reverse proxy, monitoramento, backups/restauração e revisão de segurança.
- Não enviar dados reais de clientes às IAs sem revisão de políticas, contratos e bases legais.
- Regras tributárias exigem validação com fontes oficiais e profissional responsável.

## Próximas entregas candidatas

1. Edição de cadastros com auditoria.
2. Gestão de usuários e permissões por função.
3. Importação assistida de planilhas com prévia e relatório de erros.
4. Frontend para login, painel e clientes.
5. Filas de processamento, alertas e observabilidade.
6. Plano de testes de isolamento multi-tenant e revisão de segurança.
