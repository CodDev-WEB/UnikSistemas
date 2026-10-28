# Backup e restauração do UnikSistemas

> **Estado:** scripts e procedimento preparados; a restauração completa ainda precisa ser ensaiada em homologação antes de qualquer uso com dados reais. Não trate a existência do backup como prova de que ele é recuperável.

O backup reúne **duas partes que precisam corresponder**: um dump PostgreSQL em formato customizado e um arquivo compactado do volume `document_uploads`. O banco sozinho não recupera os anexos; o volume sozinho não recupera cadastros, permissões, auditoria e metadados.

## Criar backup

Execute na raiz do repositório, em um host com Docker Compose, com `.env` configurado e serviços do projeto em execução:

```bash
bash scripts/backup.sh
```

Por padrão, o backup será salvo em `backups/unik-AAAAmmddTHHMMSSZ/`. É possível escolher outro local com `BACKUP_DIR=/caminho/privado bash scripts/backup.sh`.

O procedimento cria diretório privado (modo `700`), limita arquivos a leitura/escrita do usuário local (modo `600`), para temporariamente API e workers que escrevem no banco ou em documentos, gera o dump e o arquivo de uploads, valida os formatos, calcula SHA-256 e reinicia apenas esses serviços que estavam ativos antes da operação. O frontend pode apresentar erros temporários enquanto a API estiver parada.

Ao terminar, confira `SHA256SUMS` e `MANIFEST.txt`. O diretório inclui:

- `database.dump`: dump PostgreSQL em formato customizado, sem proprietários e ACLs.
- `uploads.tar.gz`: arquivos do volume persistente de documentos, inclusive arquivos em quarentena.
- `SHA256SUMS`: checksums para detectar corrupção ou alteração acidental.
- `MANIFEST.txt`: metadados mínimos da cópia.

O checksum prova integridade em relação ao manifesto, não a origem ou autenticidade do backup. Para proteção contra invasores com acesso ao host, copie o diretório para armazenamento externo com controle de acesso e criptografia gerenciada fora do repositório. Não comite cópias no Git, não as salve em pastas públicas e não envie dados reais de clientes para serviços externos sem autorização e avaliação adequadas.

## Restaurar backup

**Atenção:** a restauração substitui os dados atuais do PostgreSQL e os arquivos do volume de uploads. Antes de iniciar, guarde uma cópia recuperável do estado atual e faça o primeiro ensaio em ambiente de homologação isolado.

```bash
bash scripts/restore.sh backups/unik-AAAAmmddTHHMMSSZ
```

O script verifica os arquivos requeridos, os checksums, o formato do dump e os caminhos internos do arquivo de uploads antes de solicitar confirmação. Só continua quando o operador digita exatamente `RESTORE-UNIK`. Em seguida, para API e workers, recria o banco da aplicação, restaura o dump e substitui o conteúdo do volume de documentos. Em caso de falha, mantém os serviços da aplicação parados para evitar uso consciente de um estado parcialmente restaurado; corrija o problema e repita a restauração.

Após uma restauração bem-sucedida, verifique manualmente:

1. `docker compose ps` e os logs de API, workers e banco.
2. `/health/ready`, login com conta de teste e isolamento entre dois escritórios de teste.
3. Quantidade de clientes, usuários, pendências, notificações e registros de auditoria comparada com os dados conhecidos do ambiente de ensaio.
4. Download autenticado de um documento de teste limpo e bloqueio de um documento em quarentena.
5. Consistência entre registros no banco e arquivos existentes no volume.

O script só inicia novamente os serviços de aplicação que estavam ativos no início da operação. O banco de dados não é apagado pelo fluxo de backup normal; durante a restauração, o banco da aplicação é recriado a partir do dump escolhido.

## Ensaio isolado de restauração (sem substituir o ambiente ativo)

Para comprovar que um backup é restaurável antes do ensaio operacional completo, execute em um ambiente de homologação **isolado**, com o Docker Compose ativo e a aplicação configurada com `APP_ENV=staging`:

```bash
bash scripts/restore-drill.sh backups/unik-AAAAmmddTHHMMSSZ
```

O script verifica os checksums usando apenas os nomes esperados, valida os formatos do dump e do arquivo compactado, e pede a confirmação literal `RESTORE-UNIK-DRILL`. Em seguida, restaura o dump em um banco PostgreSQL temporário e extrai os documentos em um volume Docker separado. Confere a revisão Alembic, tabelas essenciais e se cada documento que não foi marcado como purgado tem um arquivo correspondente. Ao sair, tenta remover o banco e o volume temporários, inclusive em caso de erro.

O script bloqueia execução quando a configuração da API não informa `APP_ENV=staging`. Ainda assim, use somente uma instalação descartável de homologação: a criação temporária de um banco consome espaço e recursos no mesmo servidor PostgreSQL. Se o processo for interrompido abruptamente ou a limpeza automática falhar, verifique recursos com prefixo `unik_restore_drill_` antes de tentar novamente.

Este ensaio não altera o banco principal nem o volume `document_uploads`, e não comprova login real, permissões, entrega SMTP ou comportamento do proxy. Para liberar homologação, continue o roteiro completo de restauração e valide a aplicação após uma restauração efetiva em alvo descartável.

## Política operacional recomendada

- Defina a frequência conforme a perda de dados aceitável (RPO) e o tempo máximo de recuperação (RTO); não presuma valores sem acordo operacional.
- Guarde cópias cifradas fora do host principal e limite quem pode restaurá-las.
- Estabeleça retenção para as cópias, monitore espaço em disco e confirme se os arquivos foram transferidos por completo.
- Faça ensaios de restauração periódicos em ambiente isolado e registre a duração, os erros e o resultado das validações.
- Proteja os segredos do `.env` separadamente. Os backups não incluem `.env`, chaves de assinatura, certificados HTTPS nem a base de assinaturas ClamAV (esta última pode ser baixada de novo).
- Uma cópia local no mesmo servidor não protege contra perda do host, ransomware, exclusão por operador ou corrupção física.

Este procedimento cobre PostgreSQL e uploads do Docker Compose atual. Se os nomes dos serviços, usuários, bancos, caminhos ou volumes forem alterados, revise os scripts antes da execução. Não execute uma restauração em produção sem ensaio bem-sucedido, janela de manutenção e aprovação do responsável.
