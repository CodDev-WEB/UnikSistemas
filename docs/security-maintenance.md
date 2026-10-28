# Manutenção de dependências e análise de segurança

## Verificações automáticas

O repositório mantém estes controles no GitHub Actions e no Dependabot:

- **CodeQL** analisa o backend Python e o frontend TypeScript/JavaScript em pull requests, pushes para `main` e semanalmente. Os resultados devem ser revistos em **Security → Code scanning**.
- **Dependency Review** pode examinar alterações de dependências em pull requests e falhar quando uma alteração introduz uma vulnerabilidade alta ou crítica. A execução é condicionada à variável de repositório `ENABLE_DEPENDENCY_REVIEW=true`, pois o GitHub exige que o Dependency graph esteja habilitado. Mantenha a variável desativada até confirmar que o graph está habilitado.
- **Dependabot** propõe atualizações semanais para dependências Python, npm do frontend, imagens declaradas nos arquivos Docker e GitHub Actions.
- **Frontend reproduzível** usa `frontend/package-lock.json` versionado. CI e build Docker instalam exclusivamente as versões resolvidas com `npm ci`; alterações de dependência devem atualizar o manifesto e o lockfile juntos.

Esses controles complementam a CI existente; não substituem revisão de código, testes, validação de imagens, execução segura ou homologação. Uma análise sem alertas não prova que a aplicação está livre de vulnerabilidades.

## Como tratar um alerta

1. Identifique o pacote, arquivo afetado, severidade, versão corrigida e caminho de dependência.
2. Prefira atualizar para uma versão corrigida compatível. No frontend, confirme que `package.json` e `package-lock.json` foram alterados juntos; não edite o lockfile manualmente.
3. Execute a CI completa: lint, testes backend, migrações, `npm ci`, build frontend e validação de Docker Compose/Nginx.
4. Revise mudanças de comportamento, migrações e notas de lançamento do pacote; nunca habilite merge automático só porque a CI passou.
5. Se não houver correção compatível, registre o risco, os controles compensatórios, o responsável e a data para reavaliação. Não ignore alertas altos/críticos sem decisão explícita.
6. Só integre após revisão humana. Atualização de dependências não autoriza deploy.

## Limites e cuidados

- Dependabot pode abrir pull requests de atualização; ele não deve fazer merge nem implantar a aplicação automaticamente.
- Os manifests Python ainda usam intervalos de versão, portanto não constituem por si só um inventário imutável do backend implantado. Considere posteriormente um processo de lock/constraints para Python.
- Resultados do CodeQL e Dependency Review dependem das permissões e funcionalidades de segurança habilitadas no repositório. Confirme que os resultados foram publicados e que os controles estão atuando nos pull requests. A análise de dependências deve permanecer condicionada até que o Dependency graph esteja realmente ativado; não habilite a variável apenas para forçar a execução.
- Não publique tokens, arquivos `.env`, relatórios que contenham segredos nem dados reais de clientes em issues ou logs.

## Operação

Revise semanalmente os alertas de segurança e pull requests do Dependabot. Em atualizações urgentes que corrigem exploração ativa, priorize triagem imediata em vez de esperar pelo ciclo semanal. Registre a decisão, testes executados e commit aprovado.
