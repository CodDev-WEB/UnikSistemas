# Briefing do Sistema Contábil — UnikSistemas

> Documento de alinhamento do projeto. Este briefing registra o contexto de planejamento e não substitui os requisitos detalhados, decisões arquiteturais ou validação jurídica/fiscal.

## Objetivo

Desenvolver um sistema integrado para escritórios contábeis, preparado para operar como SaaS multiempresa/multitenant, com segurança de dados, automações progressivas e possibilidade de utilizar agentes de IA como apoio ao desenvolvimento e às operações.

## Diretrizes já definidas

- **Modelo de entrega:** aplicação web em nuvem.
- **Estratégia de desenvolvimento:** IA gerando código, com revisão humana, testes e aprovação antes de integrar mudanças.
- **Integrações iniciais:** importação de dados e operação assistida; automação progressiva após validação.
- **Posicionamento:** preparar a arquitetura para múltiplos escritórios clientes (SaaS).
- **Prioridade:** MVP seguro, com escopo controlado e trilha de auditoria.

## Princípios de segurança e produto

1. Isolamento obrigatório dos dados por escritório/tenant, aplicado no backend e no banco de dados.
2. Autenticação, autorização por função, princípio do menor privilégio e auditoria das ações relevantes.
3. Segredos em secret manager/variáveis protegidas; nunca versionar chaves, credenciais ou dados reais de clientes.
4. Testes automatizados e revisão humana antes de integrar código à branch principal.
5. Ambiente de desenvolvimento/testes separado da produção; backups e procedimento de restauração testados.
6. Dados fiscais/contábeis usados no desenvolvimento devem ser fictícios ou devidamente anonimizados.
7. Regras tributárias e obrigações legais devem ser confirmadas com fontes oficiais e validação profissional antes da implementação em produção.

## Fluxo recomendado de trabalho com IA

1. Registrar a tarefa e os critérios de aceitação.
2. Agente arquiteto propõe plano e identifica riscos.
3. Agente implementador trabalha em branch isolada.
4. Executar testes, linters e verificações de segurança em ambiente isolado.
5. Um revisor independente analisa diff, testes e impactos.
6. Abrir Pull Request com evidências; aprovação humana obrigatória para merge.
7. Deploy só ocorre por pipeline separado e autorizado.

## Escopo do MVP — proposta inicial para validação

- Cadastro de escritórios/tenants e usuários.
- Gestão de clientes/empresas atendidas pelo escritório.
- Cadastro de usuários, perfis e permissões.
- Importação inicial de dados por arquivos, com validação, prévia de erros e registro de origem.
- Gestão de documentos e metadados com acesso restrito por tenant.
- Painel de tarefas, pendências e status operacional.
- Auditoria e logs sem exposição de segredos ou informações desnecessárias.
- Testes essenciais, backup e monitoração.
- Sem transmissão automática de obrigações fiscais nem execução irreversível no MVP sem aprovação expressa.

Este escopo é uma proposta de partida e precisa ser confrontado com o briefing integral e validado pelo responsável pelo produto.

## Próxima etapa técnica

Antes de implementar funcionalidades de negócio, inspecionar a estrutura atual do repositório, identificar stack e estado real do código, consolidar requisitos e decisões técnicas, e só então criar backlog priorizado, modelo de dados, contratos de API e plano de testes alinhados ao código existente.

## Integração ChatGPT + Claude

O objetivo é orquestrar modelos via APIs oficiais num serviço controlado:
- OpenAI: planejamento/arquitetura e tarefas específicas;
- Anthropic Claude: implementação/revisão independente;
- GitHub: fonte versionada, branches e Pull Requests;
- CI: testes automáticos;
- aprovação humana obrigatória antes de merge/deploy.

A integração das APIs exige chaves próprias e cobrança de API separada das assinaturas de chat. O histórico de conversas não é compartilhado automaticamente: requisitos e decisões relevantes precisam ser salvos em arquivos deste repositório.

## Estado deste documento

Este arquivo conecta o contexto disponível da conversa intitulada “Briefing Sistema Contábil” ao repositório UnikSistemas, mas não importa magicamente o histórico completo daquela conversa. Os detalhes de requisitos que não estejam presentes neste resumo deverão ser recuperados e adicionados antes de tratar este documento como especificação completa.
