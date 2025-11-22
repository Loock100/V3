# Arquitetura do Projeto – PMV Agente de Estratégias

## Objetivo

Este projeto é um PMV (Produto Mínimo Viável) de um sistema local para:

- Criar e evoluir estratégias quantitativas em Python;
- Executar backtests em dados históricos;
- Registrar métricas e logs;
- Futuramente, ser controlado por um agente de IA (via driver) que lê/escreve arquivos e roda comandos.

Nenhuma parte deste projeto deve se conectar diretamente a corretoras, exchanges ou contas reais.

---

## Estrutura de Diretórios

- `config/`
  - `system.json`: configurações básicas do sistema (ex.: caminhos padrão de dados).
- `data/`
  - Arquivos de dados históricos (CSV ou outro formato tabular).
- `engine/`
  - Código do motor de backtest (por enquanto, um único arquivo `backtest.py`).
- `strategies/`
  - Arquivos Python contendo estratégias (ex.: `example_ma_crossover.py`).
- `logs/`
  - Logs de execução (mensagens do agente, erros, etc.).
- `runs/`
  - Resultados de backtests (métricas em JSON/CSV).
- `agent/`
  - Código do driver que conversa com o modelo de linguagem (GPT) e executa ações.

Arquivos na raiz:

- `README.md`: instruções de uso.
- `ARCHITECTURE.md`: este documento.
- `PROMPT_MESTRE.md`: prompt mestre usado como system prompt do agente.
- `requirements.txt`: dependências Python.
- `.gitignore`: arquivos/pastas ignorados pelo Git.

---

## Convenção de Estratégias

- As estratégias residem em `strategies/`.
- Nome sugerido: `nome_da_estrategia_v001.py`, `nome_da_estrategia_v002.py` etc.
- Cada arquivo de estratégia deve conter:
  - Uma função principal que recebe dados (DataFrame) e retorna sinais/trades;
  - Docstring explicando a lógica;
  - Comentários relevantes.

Para o PMV, usaremos apenas uma estratégia de exemplo:

- `strategies/example_ma_crossover.py`

---

## Backtests

- O motor principal está em `engine/backtest.py`.
- O fluxo mínimo de um backtest:
  1. Ler dados de um arquivo CSV em `data/` (ex.: `data/sample_prices.csv`);
  2. Carregar uma estratégia (ex.: `strategies/example_ma_crossover.py`);
  3. Aplicar a lógica da estratégia sobre os dados;
  4. Calcular:
     - Retorno total;
     - Retorno anualizado (aprox.);
     - Máximo drawdown;
     - Número de trades;
  5. Salvar as métricas em um arquivo JSON em `runs/` (ex.: `runs/run_YYYYMMDD_HHMMSS_example_ma_crossover.json`).

---

## Logs

- Logs gerais do sistema podem ser salvos em `logs/agent.log`.
- Cada execução de backtest pode ter também um log específico, se necessário (ex.: `logs/run_YYYYMMDD_HHMMSS.log`).

Formato sugerido de log (texto simples, uma linha por evento), exemplo:

```text
[2025-11-21T13:00:00] INFO - Running backtest for strategy=example_ma_crossover.py
[2025-11-21T13:00:02] ERROR - Backtest failed: <mensagem de erro>
```

---

## Futuro (fora do PMV imediato)

- Acrescentar mais estratégias;
- Backtests com múltiplos ativos;
- Walk-forward / out-of-sample;
- Dockerização;
- Dashboard.

Por enquanto, o foco é: **fazer um exemplo simples funcionar com clareza e rastreabilidade**.
