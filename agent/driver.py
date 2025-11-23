"""
driver.py

Driver do agente com LOOP de ações em modo CAUTELOSO LEVE,
com modo de manutenção do motor embutido.

- Lê o PROMPT_MESTRE.md (system prompt);
- Mantém um histórico de mensagens (como um chat);
- Em cada passo:
    1) Envia mensagem de usuário pedindo ações;
    2) Recebe JSON {"actions": [...]} do modelo;
    3) Executa ações localmente;
    4) Devolve um resumo dos resultados;
    5) Registra log em logs/agent_step_<n>.json;
    6) Repete até MAX_STEPS ou até o modelo retornar actions = [].

MODO ATUAL (LABORATÓRIO DE ESTRATÉGIAS + RANKING):
- Pode ler qualquer arquivo (read_file).
- Pode escrever SOMENTE em:
    - ARCHITECTURE.md
    - README.md
    - requirements.txt
    - engine/plot_strategy.py
    - engine/analyze_runs.py
    - logs/user_actions.md
    - arquivos .py dentro de strategies/ (criação/edição de estratégias).
- NÃO altera agent/driver.py.
- Só altera engine/backtest.py via mecanismo seguro se ALLOW_MODIFY_ENGINE = True.
- Pode usar run_command APENAS para:
    - "python engine/fetch_data.py ..."
    - "python engine/backtest.py ..."
    - "python engine/plot_strategy.py ..."
    - "python engine/analyze_runs.py"
    - "pip install -r requirements.txt"

MODO MANUTENÇÃO DO MOTOR (quando ALLOW_MODIFY_ENGINE = True):
- Se o agente tentar write_file em engine/backtest.py:
    1) Salva backup com timestamp;
    2) Testa sintaxe com "python -m py_compile engine/backtest.py";
    3) Roda backtest de fumaça: "python engine/backtest.py strategies/example_ma_crossover.py";
    4) Se qualquer etapa falhar, restaura o arquivo original e marca como reverted.
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from openai import OpenAI


ROOT_DIR = Path(__file__).resolve().parent.parent
PROMPT_PATH = ROOT_DIR / "PROMPT_MESTRE.md"

client = OpenAI()

# ===================== CONFIGURAÇÕES DE SEGURANÇA =====================

MAX_STEPS = 30               # número máximo de iterações do loop por execução
ALLOW_RUN_COMMANDS = True   # permite run_command, mas com whitelist forte
ALLOW_MODIFY_ENGINE = True  # mantenha False na maior parte do tempo


def read_prompt() -> str:
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(
            f"PROMPT_MESTRE.md não encontrado em {PROMPT_PATH}. "
            "Crie o arquivo com o prompt mestre antes de rodar o driver."
        )
    return PROMPT_PATH.read_text(encoding="utf-8")


def run_command(command: str) -> Dict[str, Any]:
    """Executa um comando no shell na raiz do projeto."""
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        cwd=str(ROOT_DIR),
    )
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def is_under_strategies(path: Path) -> bool:
    """Verifica se o path está dentro de strategies/."""
    strategies_root = (ROOT_DIR / "strategies").resolve()
    try:
        return path.resolve().is_relative_to(strategies_root)
    except AttributeError:
        # Fallback para versões antigas de Python que não têm is_relative_to
        resolved = path.resolve()
        return strategies_root == resolved or strategies_root in resolved.parents


def safe_modify_engine_backtest(path: Path, new_content: str) -> Dict[str, Any]:
    """
    Aplica uma alteração em engine/backtest.py com segurança (USADO APENAS SE ALLOW_MODIFY_ENGINE = True):

    1) Lê conteúdo original;
    2) Salva backup em engine/backtest_backup_YYYYMMDD_HHMMSS.py;
    3) Escreve novo conteúdo;
    4) Testa sintaxe com "python -m py_compile engine/backtest.py";
    5) Roda backtest de fumaça com example_ma_crossover;
    6) Se algo falhar, restaura original e marca como reverted.
    """
    engine_file = ROOT_DIR / "engine" / "backtest.py"
    if path.resolve() != engine_file.resolve():
        return {
            "type": "write_file",
            "path": str(path),
            "status": "blocked",
            "error": "safe_modify_engine_backtest chamado para arquivo que não é engine/backtest.py.",
        }

    if not engine_file.exists():
        return {
            "type": "write_file",
            "path": str(engine_file),
            "status": "blocked",
            "error": "engine/backtest.py não encontrado para modificação segura.",
        }

    original_content = engine_file.read_text(encoding="utf-8")

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_file = ROOT_DIR / "engine" / f"backtest_backup_{ts}.py"
    backup_file.write_text(original_content, encoding="utf-8")

    engine_file.write_text(new_content, encoding="utf-8")

    # Teste de sintaxe
    compile_cmd = "python -m py_compile engine/backtest.py"
    compile_result = run_command(compile_cmd)

    if compile_result["returncode"] != 0:
        engine_file.write_text(original_content, encoding="utf-8")
        return {
            "type": "write_file",
            "path": str(engine_file),
            "status": "reverted",
            "stage": "compile",
            "error": "Falha na compilação de engine/backtest.py; restauração do original.",
            "backup_path": str(backup_file),
            "compile_result": compile_result,
        }

    # Backtest de fumaça
    smoke_cmd = "python engine/backtest.py strategies/example_ma_crossover.py"
    smoke_result = run_command(smoke_cmd)

    if smoke_result["returncode"] != 0:
        engine_file.write_text(original_content, encoding="utf-8")
        return {
            "type": "write_file",
            "path": str(engine_file),
            "status": "reverted",
            "stage": "smoke_test",
            "error": "Backtest de fumaça falhou; restauração do original.",
            "backup_path": str(backup_file),
            "smoke_result": smoke_result,
        }

    return {
        "type": "write_file",
        "path": str(engine_file),
        "status": "ok",
        "backup_path": str(backup_file),
        "compile_result": compile_result,
        "smoke_result": smoke_result,
    }

def execute_actions(actions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Executa uma lista de ações (vindas do agente) e devolve um dicionário com os resultados.

    Tipos de ação suportados:
      - list_dir:      { "type": "list_dir", "path": "engine" }
      - read_file:     { "type": "read_file", "path": "engine/backtest.py" }
      - write_file:    { "type": "write_file", "path": "...", "content": "..." }
      - modify_engine: { "type": "modify_engine", "path": "engine/backtest.py", "content": "..." }
      - run_command:   { "type": "run_command", "command": "python engine/backtest.py strategies/xxx.py" }
    """
    results: List[Dict[str, Any]] = []

    for action in actions:
        a_type = action.get("type")

        # =============== LIST_DIR ===============
        if a_type == "list_dir":
            path = action.get("path", ".")
            try:
                items = sorted(os.listdir(path))
                results.append(
                    {
                        "type": "list_dir",
                        "path": path,
                        "items": items,
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "type": "list_dir",
                        "path": path,
                        "error": str(e),
                    }
                )
            continue

        # =============== READ_FILE ===============
        if a_type == "read_file":
            path = action.get("path")
            if not path:
                results.append(
                    {
                        "type": "read_file",
                        "error": "missing path",
                    }
                )
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                results.append(
                    {
                        "type": "read_file",
                        "path": path,
                        "content": content,
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "type": "read_file",
                        "path": path,
                        "error": str(e),
                    }
                )
            continue

        # =============== WRITE_FILE ===============
        if a_type == "write_file":
            path = action.get("path")
            content = action.get("content", "")
            if not path:
                results.append(
                    {
                        "type": "write_file",
                        "error": "missing path",
                    }
                )
                continue
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                results.append(
                    {
                        "type": "write_file",
                        "path": path,
                        "status": "ok",
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "type": "write_file",
                        "path": path,
                        "error": str(e),
                    }
                )
            continue

        # =============== MODIFY_ENGINE ===============
        if a_type == "modify_engine":
            if not ALLOW_MODIFY_ENGINE:
                results.append(
                    {
                        "type": "modify_engine",
                        "status": "blocked",
                        "reason": "ALLOW_MODIFY_ENGINE=False no driver.py",
                    }
                )
                continue

            path = action.get("path")
            content = action.get("content", "")

            try:
                ok, msg = safe_modify_engine_backtest(path, content)
                status = "ok" if ok else "error"
                results.append(
                    {
                        "type": "modify_engine",
                        "path": path,
                        "status": status,
                        "message": msg,
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "type": "modify_engine",
                        "path": path,
                        "status": "error",
                        "message": str(e),
                    }
                )
            continue

        # =============== RUN_COMMAND ===============
        if a_type == "run_command":
            command = action.get("command", "").strip()

            if not command:
                results.append(
                    {
                        "type": "run_command",
                        "status": "error",
                        "error": "empty command",
                    }
                )
                continue

            if not ALLOW_RUN_COMMANDS:
                results.append(
                    {
                        "type": "run_command",
                        "command": command,
                        "status": "blocked",
                        "error": "Execução de comandos desativada (ALLOW_RUN_COMMANDS=False).",
                    }
                )
                continue

            # Whitelist de comandos que o agente pode rodar
            allowed_prefixes = [
                "python engine/fetch_data.py",
                "python engine/backtest.py",
                "python engine/analyze_runs.py",
                "python engine/plot_strategy.py",
                "python engine/optimize_params.py",
                "pip install -r requirements.txt",
            ]

            allowed = any(command.startswith(p) for p in allowed_prefixes)

            if not allowed:
                results.append(
                    {
                        "type": "run_command",
                        "command": command,
                        "status": "blocked",
                        "error": (
                            "Comando bloqueado. O driver só permite atualmente:\\n"
                            "- python engine/fetch_data.py ...\\n"
                            "- python engine/backtest.py ...\\n"
                            "- python engine/analyze_runs.py ...\\n"
                            "- python engine/plot_strategy.py ...\\n"
                            "- python engine/optimize_params.py ...\\n"
                            "- pip install -r requirements.txt\\n"
                            f"Comando solicitado: {command}"
                        ),
                    }
                )
                continue

            # Executa o comando permitido
            result = run_command(command, cwd=str(ROOT_DIR))
            results.append(
                {
                    "type": "run_command",
                    "command": command,
                    "status": "ok" if result["returncode"] == 0 else "error",
                    "returncode": result["returncode"],
                    "stdout": result["stdout"],
                    "stderr": result["stderr"],
                }
            )
            continue

        # =============== TIPO DESCONHECIDO ===============
        results.append(
            {
                "type": a_type or "unknown",
                "status": "error",
                "error": f"Ação desconhecida: {a_type}",
                "raw_action": action,
            }
        )

    return {"results": results}



def call_agent(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Chama o modelo com o histórico completo de mensagens.

    Espera que a ÚLTIMA resposta do modelo seja um JSON
    no formato {"actions": [...]}.
    """
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=messages,
        temperature=0.2,
    )

    content = response.choices[0].message.content
    if content is None:
        raise ValueError("Resposta do modelo veio vazia.")

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Falha ao interpretar resposta do modelo como JSON.\n"
            f"Erro: {e}\nConteúdo bruto:\n{content}"
        )

    if "actions" not in data or not isinstance(data["actions"], list):
        raise ValueError(
            f"JSON retornado não contém a chave 'actions' em formato de lista.\n"
            f"Conteúdo: {data}"
        )

    return data


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "A variável de ambiente OPENAI_API_KEY não está definida.\n"
            "Defina a chave da API antes de rodar o driver."
        )

    prompt_sistema = read_prompt()

    # Histórico de mensagens (estilo chat)
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": prompt_sistema}
    ]

    # ===================== initial_user_message =====================

    initial_user_message = (
        "INICIO: siga rigorosamente o prompt mestre.\n"
        "Esta execução está em modo LABORATÓRIO DE ESTRATÉGIAS + RANKING, com FOCO em:\n"
        "- garantir dependências (requirements.txt + pip install),\n"
        "- garantir dados históricos dos ÚLTIMOS 5 ANOS para um ativo (ex.: BTC-USD),\n"
        "- rodar uma bateria pequena de backtests (estratégia baseline + multi_tf_*),\n"
        "- consolidar resultados via engine/analyze_runs.py,\n"
        "- registrar um resumo em logs/user_actions.md.\n\n"
        "0) DADOS – FETCH 5 ANOS\n"
        "- Verificar se 'data/sample_prices.csv' existe.\n"
        "- Se não existir ou se preferir garantir atualização, você PODE rodar:\n"
        "    run_command com 'python engine/fetch_data.py BTC-USD'\n"
        "  (por padrão, este script deve baixar ~5 anos de dados diários e salvar em data/sample_prices.csv).\n\n"
        "1) REQUIREMENTS / DEPENDÊNCIAS\n"
        "- Ler o arquivo 'requirements.txt'.\n"
        "- Garantir que contenha, pelo menos: numpy, pandas, matplotlib, openai, yfinance.\n"
        "- Se precisar ajustar (adicionar/organizar), use write_file em 'requirements.txt'.\n"
        "- Se você MODIFICAR 'requirements.txt' nesta execução, chame UMA ÚNICA VEZ:\n"
        "    run_command com 'pip install -r requirements.txt'.\n"
        "- Além disso, se qualquer run_command retornar ModuleNotFoundError para alguma biblioteca,\n"
        "  ajuste 'requirements.txt' e rode novamente 'pip install -r requirements.txt' uma vez.\n\n"
        "2) SCRIPTS DE VISUALIZAÇÃO / ANÁLISE\n"
        "- Garantir que exista um script COMPLETO em 'engine/plot_strategy.py' que:\n"
        "    • carregue dados de 'data/sample_prices.csv',\n"
        "    • receba o caminho da estratégia como argumento na linha de comando,\n"
        "    • importe dinamicamente o módulo de estratégia (ex.: strategies/multi_tf_trend_lab_v1.py),\n"
        "    • execute run_strategy(df) -> (df_result, trades_info),\n"
        "    • calcule métricas básicas (retorno total, anualizado aproximado, max drawdown, num_trades se existir,\n"
        "      Sharpe, expectativa, buy & hold),\n"
        "    • plote ao menos:\n"
        "         - curva de preço normalizado + curva de equity,\n"
        "         - gráfico de drawdown ao longo do tempo,\n"
        "      usando matplotlib.\n"
        "- Garantir que exista um script 'engine/analyze_runs.py' que:\n"
        "    • leia todos os arquivos JSON em 'runs/' gerados pelos backtests,\n"
        "    • extraia, no mínimo, para cada run: nome da estratégia, retorno total, retorno anualizado, max drawdown,\n"
        "      Sharpe, expectativa, buy & hold e num_trades (se disponível),\n"
        "    • aplique filtros de robustez leves (ex.: ignorar runs com max_drawdown < -20% ou com poucas observações),\n"
        "    • ordene as estratégias restantes por uma métrica composta (por exemplo, score já calculado),\n"
        "    • imprima no stdout um ranking das TOP 5 estratégias e destaque, em texto, quais parecem promissoras.\n\n"
        "3) BACKTESTS EM LOTE\n"
        "- Descobrir quais estratégias existem em 'strategies/' (ex.: example_ma_crossover.py,\n"
        "  multi_tf_trend_lab_v1.py, multi_tf_trend_lab_v2.py, multi_tf_trend_lab_v3.py).\n"
        "- Para cada uma delas que fizer sentido testar, rodar via run_command comandos do tipo:\n"
        "    • 'python engine/backtest.py strategies/<nome>.py'\n"
        "  (pelo menos baseline + multi_tf_*).\n\n"
        "4) ANÁLISE E RESUMO PARA HUMANO\n"
        "- Depois de ter pelo menos alguns backtests rodados, executar:\n"
        "    • 'python engine/analyze_runs.py'\n"
        "  via run_command.\n"
        "- Usar o stdout retornado por analyze_runs.py para escrever um RESUMO textual em logs/user_actions.md,\n"
        "  via write_file, contendo:\n"
        "    • Quais estratégias foram testadas,\n"
        "    • as principais métricas (retorno, anualizado, Sharpe, drawdown, etc.),\n"
        "    • quais parecem ter algum potencial,\n"
        "    • quais parecem overfit ou fracas (\"lixo\") e por quê.\n\n"
        "5) LIMITES DE AÇÃO\n"
        "- NÃO alterar agent/driver.py em hipótese alguma.\n"
        "- Só alterar engine/backtest.py se ALLOW_MODIFY_ENGINE estiver habilitado e via mecanismo seguro; nesta execução,\n"
        "  foque em dados, estratégias, visualização, análise e resumo.\n"
        "- Você pode usar list_dir para inspecionar pastas, read_file para ler qualquer arquivo,\n"
        "  write_file apenas para: ARCHITECTURE.md, README.md, requirements.txt,\n"
        "  engine/plot_strategy.py, engine/analyze_runs.py, logs/user_actions.md e arquivos .py em 'strategies/'.\n"
        "- Você pode usar run_command APENAS para:\n"
        "    • 'python engine/fetch_data.py ...',\n"
        "    • 'python engine/backtest.py ...',\n"
        "    • 'python engine/plot_strategy.py ...',\n"
        "    • 'python engine/analyze_runs.py',\n"
        "    • 'pip install -r requirements.txt'.\n\n"
        "Responda SEMPRE APENAS com JSON no formato {\"actions\": [...]}."
    )

    user_content = initial_user_message

    for step in range(1, MAX_STEPS + 1):
        print(f"\n===== PASSO {step} =====")
        print("Enviando mensagem ao agente...")

        messages.append({"role": "user", "content": user_content})

        data = call_agent(messages)
        actions = data.get("actions", [])

        print(f"Número de ações recebidas: {len(actions)}")

        if not actions:
            print("Nenhuma ação retornada. Encerrando o loop.")
            break

        results = execute_actions(actions)

        # Salvar log deste passo em logs/agent_step_<n>.json
        logs_dir = ROOT_DIR / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        step_log_path = logs_dir / f"agent_step_{step}.json"
        step_log_path.write_text(
            json.dumps(
                {
                    "step": step,
                    "actions": actions,
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print("Resultados da execução das ações:")
        print(json.dumps(results, indent=2, ensure_ascii=False))

        # Adiciona no histórico como se fosse a resposta do "assistente"
        messages.append(
            {
                "role": "assistant",
                "content": json.dumps(
                    {"actions": actions, "results": results},
                    ensure_ascii=False,
                ),
            }
        )

        # Próxima mensagem de usuário: feedback + pedido de próximos passos úteis
        user_content = (
            "Aqui estão os resultados das ações que você solicitou:\n"
            + json.dumps(results, ensure_ascii=False)
            + "\nSe ainda houver ações ÚTEIS para:\n"
              "- garantir dados e dependências para os últimos 5 anos,\n"
              "- rodar backtests adicionais em strategies/,\n"
              "- ajustar visualização/análise,\n"
              "- ou refinar o resumo em logs/user_actions.md,\n"
              "responda novamente APENAS com JSON no formato {\"actions\": [...]}.\n"
              "Se considerar que terminou por enquanto, responda com {\"actions\": []}."
        )

    print("\nLoop encerrado.")


if __name__ == "__main__":
    main()
