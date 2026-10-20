# UnikSistemas
### Sistema integrado para escritórios contábeis

O **UnikSistemas** é um projeto de sistema web para apoiar a operação de escritórios contábeis, com foco em organização de clientes e tarefas, importação de dados, segurança e evolução gradual para um modelo **SaaS multi-tenant** — vários escritórios usando a mesma plataforma com isolamento rigoroso entre seus dados.

> **Status do projeto:** fase inicial de planejamento e estruturação. As funcionalidades descritas neste README representam objetivos e propostas de escopo; não devem ser interpretadas como funcionalidades já implementadas ou disponíveis em produção.

## Objetivo

Construir um sistema seguro, modular e sustentável para centralizar rotinas do escritório contábil, começando por um MVP de escopo controlado e ampliando as integrações e automações somente após testes e validação operacional.

## Diretrizes do produto

- **Nuvem:** aplicação web preparada para operação hospedada e evolução contínua.
- **SaaS multi-tenant:** isolamento de dados, usuários e permissões por escritório.
- **MVP seguro:** priorizar os fluxos essenciais antes de ampliar o escopo.
- **Integração progressiva:** começar com importação de dados e operação assistida; automatizar etapas depois de validar regras e resultados.
- **Rastreabilidade:** registrar ações importantes, origem dos dados, erros de importação e alterações relevantes.
- **Desenvolvimento com IA:** usar ChatGPT e Claude como apoio à análise, implementação e revisão, com testes e aprovação humana antes do merge.
- **Conformidade:** regras contábeis, tributárias e obrigações legais devem ser verificadas com fontes oficiais e validadas por profissional responsável antes de uso operacional.

## Escopo inicial proposto

O escopo abaixo é uma base para refinamento do produto, não uma declaração de entrega concluída.

1. **Escritórios e usuários** — cadastro de tenants, usuários, perfis e permissões.
2. **Clientes do escritório** — cadastro e organização das empresas atendidas.
3. **Importação de dados** — envio de arquivos, validação, prévia de inconsistências, relatório de erros e registro da origem.
4. **Documentos** — armazenamento e organização de metadados com acesso restrito e trilha de auditoria.
5. **Tarefas e pendências** — acompanhamento de atividades, responsáveis, prazos e status.
6. **Painel operacional** — visão de pendências e status dos fluxos principais.
7. **Auditoria e observabilidade** — eventos relevantes, erros e monitoramento sem registrar segredos desnecessários.

Transmissões fiscais, operações financeiras irreversíveis e outras ações de alto impacto não devem ser automatizadas no MVP sem autorização explícita, controles e validação adequada.

## Princípios de arquitetura e segurança

- Toda operação que envolva dados de negócio deve ser autorizada no servidor e delimitada pelo tenant correto.
- Aplicar menor privilégio para usuários, serviços, agentes de IA e tokens de integração.
- Manter segredos em variáveis protegidas ou serviço de gerenciamento de segredos; nunca versionar chaves, senhas ou tokens.
- Separar ambientes de desenvolvimento, testes e produção.
- Usar dados fictícios ou anonimizados durante o desenvolvimento; não enviar documentos reais de clientes a modelos de IA sem avaliação prévia das bases legais, contratos e políticas de tratamento aplicáveis.
- Ter backups e testar procedimentos de restauração.
- Cobrir com testes os limites de autorização e o isolamento entre tenants.
- Fazer revisão humana das mudanças e validar dependências, migrações e impactos antes de integrar código.
- Aplicar monitoramento, limites de consumo e registro de auditoria nas integrações externas.

A stack tecnológica definitiva, o modelo de dados e os contratos de API devem ser registrados em documentos técnicos revisados antes de serem considerados decisões oficiais do projeto.

## Fluxo de desenvolvimento

1. Registrar cada demanda com objetivo, requisitos e critérios de aceitação.
2. Analisar o código e as decisões já documentadas antes de planejar mudanças.
3. Propor a implementação e identificar riscos.
4. Trabalhar em uma branch dedicada por tarefa.
5. Executar testes automatizados e verificações estáticas em ambiente isolado.
6. Abrir um Pull Request com resumo, arquivos alterados, resultados dos testes e limitações conhecidas.
7. Exigir revisão e aprovação humana antes do merge.
8. Executar deploy por processo separado, autorizado e auditável.

### Uso de ChatGPT e Claude

Os dois provedores podem ser coordenados por um orquestrador via APIs oficiais. Por exemplo, um agente pode planejar uma tarefa e outro propor ou revisar a implementação. O GitHub permanece como fonte versionada do código e dos documentos. As APIs têm credenciais e custos próprios; as conversas dos produtos ChatGPT e Claude não são compartilhadas automaticamente. Requisitos e decisões importantes devem ser registrados no repositório.

## Roadmap sugerido

| Fase | Resultado esperado |
|---|---|
| 1. Descoberta | Requisitos priorizados, personas, fluxos e critérios de aceitação |
| 2. Fundação técnica | Stack validada, arquitetura, modelo de dados, autenticação e isolamento multi-tenant |
| 3. MVP operacional | Cadastros essenciais, importação assistida, tarefas e auditoria |
| 4. Qualidade e segurança | Testes, revisão de permissões, backups, monitoração e validação com dados fictícios |
| 5. Integrações | Conectores e automações graduais, inicialmente com supervisão |
| 6. SaaS e escala | Provisionamento de tenants, gestão de planos e controles operacionais, após validação da base |

A ordem e o conteúdo deste roadmap devem ser ajustados conforme os requisitos detalhados e as limitações técnicas descobertas durante a inspeção do repositório.

## Documentação do projeto

- [Briefing do Sistema Contábil](docs/briefing-sistema-contabil.md) — contexto inicial, diretrizes, proposta de MVP e próximos passos técnicos.
- Arquitetura, modelo de dados, contratos de API, mapa de telas, backlog e plano de testes deverão ser adicionados quando revisados e aprovados.

## Estrutura do repositório

A estrutura evoluirá conforme a implementação. Não presuma que diretórios ou módulos previstos já existem. Antes de adicionar uma funcionalidade, verifique o estado atual do código e atualize a documentação correspondente.

## Configuração e execução

A configuração para desenvolvimento será documentada assim que a stack e o esqueleto executável do produto forem definidos e adicionados ao repositório. Este README, por si só, não significa que a aplicação já esteja pronta para executar ou implantar.

## Como contribuir

- Mantenha as mudanças pequenas e focadas.
- Documente decisões que afetem arquitetura, segurança ou comportamento de negócio.
- Inclua testes para novas regras e correções.
- Não inclua credenciais, dados pessoais reais ou documentos contábeis de clientes.
- Abra Pull Requests para revisão; não integre diretamente à branch principal sem seguir as regras do repositório.

## Licença

Consulte o arquivo [LICENSE](LICENSE) para os termos aplicáveis ao repositório.
