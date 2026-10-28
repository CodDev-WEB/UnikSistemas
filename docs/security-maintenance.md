# Manutenção de dependências e análise de segurança

## Verificações automáticas

O repositório mantém três controles no GitHub Actions:

- **CodeQL** analisa o backend Python e o frontend TypeScript/JavaScript em pull requests, pushes para `main` e semanalmente. Os resultados devem ser revistos em **Security → Code scanning**.
- **Dependency Review** examina alterações de dependências em pull requests e falha quando uma alteração introduz uma vulnerabilidade classificada como alta ou crítica.
- **Dependabot** propõe atualizações semanais para dependências Python, imagens declaradas nos arquivos Docker e GitHub Actions.

Esses controles complementam a CI existente; não substituem revisão de código, testes, validação de imagens, execução segura ou homologação. Uma análise sem alertas não prova que a aplicação está livre de vulnerabilidades.

## Como tratar um alerta

1. Identifique o pacote, arquivo afetado, severidade, versão corrigida e caminho de dependência.
2. Prefira atualizar para uma versão corrigida compatível com os limites declarados. Evite ampliar intervalos de versão sem revisar compatibilidade e impacto.
3. Execute a CI completa: lint, testes backend, migrações, build frontend e validação de Docker Compose/Nginx.
4. Revise mudanças de comportamento, migrações e notas de lançamento do pacote; nunca habilite merge automático só porque a CI passou.
5. Se não houver correção compatível, registre o risco, os controles compensatórios, o responsável e a data para reavaliação. Não ignore alertas altos/críticos sem decisão explícita.
6. Só integre após revisão humana. Atualização de dependências não autoriza deploy.

## Limites e cuidados

- Dependabot pode abrir pull requests de atualização; ele não deve fazer merge nem implantar a aplicação automaticamente.
- Os manifests Python usam intervalos de versão, portanto não constituem por si só um inventário imutável do ambiente implantado. Para reproduzir builds, adote posteriormente um processo de lock/constraints e uma estratégia de atualização testada.
- O frontend ainda não mantém lockfile npm versionado; por isso, o controle atual do Dependabot não declara uma rotina npm. Adote e versione um lockfile antes de habilitar atualizações automatizadas específicas do npm.
- Resultados do CodeQL e Dependency Review dependem das permissões e funcionalidades de segurança habilitadas no repositório. Confirme após a primeira execução que os resultados foram publicados e que os controles estão atuando nos pull requests.
- Não publique tokens, arquivos `.env`, relatórios que contenham segredos nem dados reais de clientes em issues ou logs.

## Operação

Revise semanalmente os alertas de segurança e pull requests do Dependabot. Em atualizações urgentes que corrigem exploração ativa, priorize triagem imediata em vez de esperar pelo ciclo semanal. Registre a decisão, testes executados e commit aprovado.
