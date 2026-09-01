"""Traduz passos Power Query (M) para SQL DuckDB (subconjunto de Table.*)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pq.translators.errors import ParseError


M_TYPE_TO_SQL: dict[str, str] = {
    "type date": "DATE",
    "type text": "VARCHAR",
    "type number": "DOUBLE",
    "int64.type": "BIGINT",
}


def _skip_ws(s: str, i: int) -> int:
    while i < len(s) and s[i] in " \t\r\n":
        i += 1
    return i


def _find_matching(s: str, start: int, open_ch: str, close_ch: str) -> int:
    if start >= len(s) or s[start] != open_ch:
        raise ParseError(f"Esperado '{open_ch}' na posição {start}.")
    depth = 0
    i = start
    in_string = False
    while i < len(s):
        ch = s[i]
        if in_string:
            if ch == '"':
                if i + 1 < len(s) and s[i + 1] == '"':
                    i += 2
                    continue
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            i += 1
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ParseError(f"'{open_ch}' sem fechamento '{close_ch}'.")


def _split_top_level(s: str, sep: str = ",") -> list[str]:
    parts: list[str] = []
    start = 0
    depth_paren = depth_brace = 0
    in_string = False
    i = 0
    while i < len(s):
        ch = s[i]
        if in_string:
            if ch == '"':
                if i + 1 < len(s) and s[i + 1] == '"':
                    i += 2
                    continue
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
        elif ch == "(":
            depth_paren += 1
        elif ch == ")":
            depth_paren -= 1
        elif ch == "{":
            depth_brace += 1
        elif ch == "}":
            depth_brace -= 1
        elif ch == sep and depth_paren == 0 and depth_brace == 0:
            parts.append(s[start:i].strip())
            start = i + 1
        i += 1
    tail = s[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _parse_step_name(s: str, i: int) -> tuple[str, int]:
    i = _skip_ws(s, i)
    if s.startswith('#"', i):
        end = s.find('"', i + 2)
        if end < 0:
            raise ParseError("Nome de passo M inválido (#\"...\").")
        return s[i + 2 : end], end + 1
    m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", s[i:])
    if not m:
        raise ParseError(f"Nome de passo inválido perto de: {s[i : i + 40]!r}")
    return m.group(0), i + m.end()


def split_m_steps(source: str) -> list[tuple[str, str]]:
    text = source.strip().rstrip(";").strip()
    if not text:
        raise ParseError("Código M vazio.")
    steps: list[tuple[str, str]] = []
    i = 0
    n = len(text)
    while i < n:
        i = _skip_ws(text, i)
        if i >= n:
            break
        if text[i] == ",":
            i += 1
            continue
        name, i = _parse_step_name(text, i)
        i = _skip_ws(text, i)
        if not text.startswith("=", i):
            raise ParseError(f"Esperado '=' após o passo '{name}'.")
        i += 1
        i = _skip_ws(text, i)
        expr_start = i
        depth_paren = depth_brace = 0
        in_string = False
        while i < n:
            ch = text[i]
            if in_string:
                if ch == '"':
                    if i + 1 < n and text[i + 1] == '"':
                        i += 2
                        continue
                    in_string = False
                i += 1
                continue
            if ch == '"':
                in_string = True
            elif ch == "(":
                depth_paren += 1
            elif ch == ")":
                depth_paren -= 1
            elif ch == "{":
                depth_brace += 1
            elif ch == "}":
                depth_brace -= 1
            elif ch == "," and depth_paren == 0 and depth_brace == 0:
                break
            i += 1
        expr = text[expr_start:i].strip()
        if not expr:
            raise ParseError(f"Expressão vazia no passo '{name}'.")
        steps.append((name, expr))
        if i < n and text[i] == ",":
            i += 1
    if not steps:
        raise ParseError("Nenhum passo M encontrado.")
    return steps


def _parse_quoted_name(s: str, i: int) -> tuple[str, int]:
    i = _skip_ws(s, i)
    if s.startswith('#"', i):
        end = s.find('"', i + 2)
        if end < 0:
            raise ParseError("Referência de passo inválida.")
        return s[i + 2 : end], end + 1
    m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", s[i:])
    if not m:
        raise ParseError(f"Identificador inválido: {s[i : i + 30]!r}")
    return m.group(0), i + m.end()


def _sql_ref(name: str) -> str:
    return f'"{name}"'


def _param_sql_name(name: str) -> str:
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return re.sub(r"[^a-z0-9_]", "_", snake)


def _m_string_to_sql(s: str) -> str:
    inner = s[1:-1].replace("'", "''").replace('""', '"')
    return f"'{inner}'"


def _translate_predicate(expr: str, params: set[str]) -> str:
    tokens: list[str] = []
    i = 0
    n = len(expr)
    while i < n:
        i = _skip_ws(expr, i)
        if i >= n:
            break
        if expr[i] == "[":
            end = expr.find("]", i + 1)
            if end < 0:
                raise ParseError("Coluna M sem fechamento ']'.")
            col = expr[i + 1 : end]
            tokens.append(_sql_ref(col))
            i = end + 1
            continue
        if expr[i] == '"':
            end = i + 1
            while end < n:
                if expr[end] == '"':
                    if end + 1 < n and expr[end + 1] == '"':
                        end += 2
                        continue
                    break
                end += 1
            tokens.append(_m_string_to_sql(expr[i : end + 1]))
            i = end + 1
            continue
        if expr[i] in "()":
            tokens.append(expr[i])
            i += 1
            continue
        m = re.match(
            r"(?i)^(>=|<=|<>|!=|and|or|not|=|<|>)",
            expr[i:],
        )
        if m:
            op = m.group(1)
            low = op.lower()
            if low in {"and", "or", "not"}:
                tokens.append(low.upper())
            else:
                tokens.append("<>" if low == "!=" else op)
            i += m.end()
            continue
        m = re.match(r"^[A-Za-z_][A-Za-z0-9_]*", expr[i:])
        if m:
            word = m.group(0)
            if word in params:
                tokens.append(f"p.{_param_sql_name(word)}")
            else:
                tokens.append(_sql_ref(word))
            i += m.end()
            continue
        raise ParseError(f"Predicado M inválido perto de: {expr[i : i + 30]!r}")
    return " ".join(tokens)


def _parse_m_list(s: str) -> list[str]:
    s = s.strip()
    if not s.startswith("{"):
        raise ParseError(f"Lista M esperada: {s[:40]!r}")
    end = _find_matching(s, 0, "{", "}")
    inner = s[1:end].strip()
    if not inner:
        return []
    return _split_top_level(inner)


def _parse_type_pairs(s: str) -> list[tuple[str, str]]:
    items = _parse_m_list(s)
    pairs: list[tuple[str, str]] = []
    for item in items:
        item = item.strip()
        if not item.startswith("{"):
            raise ParseError(f"Par tipo/coluna inválido: {item[:50]!r}")
        end = _find_matching(item, 0, "{", "}")
        parts = _split_top_level(item[1:end])
        if len(parts) != 2:
            raise ParseError(f"Par tipo/coluna inválido: {item[:50]!r}")
        col = parts[0].strip().strip('"')
        type_raw = parts[1].strip().lower()
        sql_type = M_TYPE_TO_SQL.get(type_raw)
        if not sql_type:
            raise ParseError(f"Tipo M não suportado: {parts[1].strip()}")
        pairs.append((col, sql_type))
    return pairs


def _parse_column_names_list(s: str) -> list[str]:
    return [p.strip().strip('"') for p in _parse_m_list(s)]


@dataclass
class _Step:
    name: str
    sql: str
    uses_params: bool = False


def _parse_table_call(expr: str) -> tuple[str, list[str]]:
    m = re.match(r"Table\.([A-Za-z_]+)\s*\(", expr)
    if not m:
        raise ParseError(f"Função Table.* esperada: {expr[:60]!r}")
    func = m.group(1)
    open_paren = m.end() - 1
    close_paren = _find_matching(expr, open_paren, "(", ")")
    inner = expr[open_paren + 1 : close_paren]
    args = _split_top_level(inner)
    return func, args


def _translate_step(
    name: str,
    expr: str,
    params: dict[str, str],
    known_steps: set[str],
) -> _Step:
    func, args = _parse_table_call(expr)
    param_names = set(params)

    if func == "SelectRows":
        if len(args) != 2:
            raise ParseError("Table.SelectRows requer 2 argumentos.")
        source, _i = _parse_quoted_name(args[0], 0)
        pred_raw = args[1].strip()
        if not pred_raw.lower().startswith("each "):
            raise ParseError("Table.SelectRows: segundo argumento deve ser 'each ...'.")
        pred = _translate_predicate(pred_raw[5:].strip(), param_names)
        src = _sql_ref(source)
        uses_params = bool(param_names) and any(
            f"p.{_param_sql_name(p)}" in pred for p in params
        )
        if uses_params:
            sql = (
                f"SELECT *\n"
                f"FROM {src}\n"
                f"CROSS JOIN params p\n"
                f"WHERE {pred}"
            )
        else:
            sql = f"SELECT *\nFROM {src}\nWHERE {pred}"
        return _Step(name, sql, uses_params)

    if func == "TransformColumnTypes":
        if len(args) != 2:
            raise ParseError("Table.TransformColumnTypes requer 2 argumentos.")
        source, _ = _parse_quoted_name(args[0], 0)
        pairs = _parse_type_pairs(args[1])
        casts = ",\n  ".join(
            f'CAST({_sql_ref(col)} AS {sql_type}) AS {_sql_ref(col)}' for col, sql_type in pairs
        )
        sql = f"SELECT * REPLACE (\n  {casts}\n)\nFROM {_sql_ref(source)}"
        return _Step(name, sql)

    if func == "RemoveColumns":
        if len(args) != 2:
            raise ParseError("Table.RemoveColumns requer 2 argumentos.")
        source, _ = _parse_quoted_name(args[0], 0)
        cols = _parse_column_names_list(args[1])
        excluded = ", ".join(_sql_ref(c) for c in cols)
        sql = f"SELECT * EXCLUDE ({excluded})\nFROM {_sql_ref(source)}"
        return _Step(name, sql)

    if func == "SelectColumns":
        if len(args) != 2:
            raise ParseError("Table.SelectColumns requer 2 argumentos.")
        source, _ = _parse_quoted_name(args[0], 0)
        cols = _parse_column_names_list(args[1])
        selected = ", ".join(_sql_ref(c) for c in cols)
        sql = f"SELECT {selected}\nFROM {_sql_ref(source)}"
        return _Step(name, sql)

    raise ParseError(f"Função Table.{func} não suportada.")


_RESERVED_PRED = frozenset({"each", "and", "or", "not", "type"})


def _strip_strings_and_brackets(expr: str) -> str:
    out: list[str] = []
    i = 0
    n = len(expr)
    while i < n:
        if expr[i] == '"':
            end = i + 1
            while end < n:
                if expr[end] == '"':
                    if end + 1 < n and expr[end + 1] == '"':
                        end += 2
                        continue
                    break
                end += 1
            out.append(" ")
            i = end + 1
            continue
        if expr[i] == "[":
            end = expr.find("]", i + 1)
            if end < 0:
                break
            out.append(" ")
            i = end + 1
            continue
        out.append(expr[i])
        i += 1
    return "".join(out)


def _collect_params(steps: list[tuple[str, str]], known_tables: set[str]) -> set[str]:
    found: set[str] = set()
    step_names = {n for n, _ in steps}
    for _name, expr in steps:
        if "Table.SelectRows" not in expr:
            continue
        _, args = _parse_table_call(expr)
        pred = args[1]
        if pred.strip().lower().startswith("each "):
            pred = pred.strip()[5:]
        cleaned = _strip_strings_and_brackets(pred)
        for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", cleaned):
            ident = m.group(1)
            if ident.lower() in _RESERVED_PRED:
                continue
            if ident in step_names or ident in known_tables:
                continue
            found.add(ident)
    return found


def _is_table_step(expr: str) -> bool:
    return expr.strip().startswith("Table.")


def _m_literal_to_sql(expr: str) -> str | None:
    """Converte literal M (#date, texto, número…) em literal SQL DuckDB."""
    raw = expr.strip().rstrip(",")
    if not raw:
        return None
    low = raw.lower()
    if low == "null":
        return "NULL"
    if low == "true":
        return "TRUE"
    if low == "false":
        return "FALSE"
    if raw.startswith('"') and raw.endswith('"'):
        return _m_string_to_sql(raw)
    if re.fullmatch(r"-?\d+", raw):
        return raw
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return raw
    m = re.fullmatch(r"#date\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", raw, re.I)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        return f"DATE '{y:04d}-{mo:02d}-{d:02d}'"
    m = re.fullmatch(
        r"#datetime(?:zone)?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*(\d+)(?:\s*,\s*(\d+)(?:\s*,\s*(\d+))?)?)?\s*\)",
        raw,
        re.I,
    )
    if m:
        y, mo, d = (int(x) for x in m.groups()[:3])
        h = int(m.group(4) or 0)
        mi = int(m.group(5) or 0)
        s = int(m.group(6) or 0)
        return f"TIMESTAMP '{y:04d}-{mo:02d}-{d:02d} {h:02d}:{mi:02d}:{s:02d}'"
    return None


def parse_m_script(source: str) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """
    Separa definições de parâmetros M (`Nome = #date(...)`) de passos `Table.*`.
    Retorna (param_defs, table_steps).
    """
    param_defs: dict[str, str] = {}
    table_steps: list[tuple[str, str]] = []
    for name, expr in split_m_steps(source):
        if _is_table_step(expr):
            table_steps.append((name, expr))
            continue
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ParseError(
                f"Passo '{name}' não é Table.* nem parâmetro M (use identificador simples)."
            )
        param_defs[name] = expr.strip()
    if not table_steps:
        raise ParseError("Nenhum passo Table.* encontrado.")
    return param_defs, table_steps


def m_source_table(m_code: str) -> str | None:
    """Retorna a tabela de origem do primeiro Table.SelectRows, se houver."""
    try:
        _param_defs, steps = parse_m_script(m_code)
        func, args = _parse_table_call(steps[0][1])
        if func != "SelectRows":
            return None
        src, _ = _parse_quoted_name(args[0], 0)
        return src
    except (ParseError, IndexError):
        return None


def m_parameter_names(m_code: str) -> list[str]:
    """Parâmetros M: definidos no script + referenciados em predicados each."""
    param_defs, steps = parse_m_script(m_code)
    known_tables: set[str] = set()
    for _n, expr in steps:
        func, args = _parse_table_call(expr)
        if func == "SelectRows":
            src, _ = _parse_quoted_name(args[0], 0)
            if src not in {s[0] for s in steps}:
                known_tables.add(src)
    inferred = _collect_params(steps, known_tables)
    return sorted(set(param_defs) | inferred)


def m_parameter_defaults(m_code: str) -> dict[str, str]:
    """Literais SQL inferidos de definições M (`MeuParam = #date(...)`)."""
    param_defs, _steps = parse_m_script(m_code)
    out: dict[str, str] = {}
    for name, expr in param_defs.items():
        sql = _m_literal_to_sql(expr)
        if sql is not None:
            out[name] = sql
    return out


def translate_m_to_sql(
    m_code: str,
    *,
    table_map: dict[str, str] | None = None,
    param_values: dict[str, str] | None = None,
) -> str:
    """
    Converte passos Power Query (M) em SQL DuckDB com CTEs.

    table_map: nome M -> nome da view DuckDB (ex.: base carregada).
    param_values: parâmetros M -> literal SQL DuckDB (ex.: MeuParam -> DATE '2025-01-01').
    """
    param_defs, steps = parse_m_script(m_code)
    if table_map:
        for i, (name, expr) in enumerate(steps):
            for src, dst in table_map.items():
                if src != dst:
                    expr = re.sub(rf"\b{re.escape(src)}\b", dst, expr)
            steps[i] = (name, expr)

    known_tables = set(table_map or [])
    for _n, expr in steps:
        func, args = _parse_table_call(expr)
        if func == "SelectRows":
            src, _ = _parse_quoted_name(args[0], 0)
            if src not in {s[0] for s in steps}:
                known_tables.add(src)

    inferred = _collect_params(steps, known_tables)
    all_param_names = sorted(set(param_defs) | inferred)
    m_defaults = {name: sql for name, expr in param_defs.items() if (sql := _m_literal_to_sql(expr))}
    overrides = param_values or {}
    params: dict[str, str] = {}
    for p in all_param_names:
        if p in overrides and overrides[p].strip():
            params[p] = overrides[p].strip()
        elif p in m_defaults:
            params[p] = m_defaults[p]
        else:
            params[p] = "NULL"

    translated: list[_Step] = []
    for name, expr in steps:
        translated.append(_translate_step(name, expr, params, {s.name for s in translated}))

    lines: list[str] = []
    if params:
        cols = ",\n    ".join(
            f"{params[p]} AS {_param_sql_name(p)}" for p in sorted(params)
        )
        lines.append(f"WITH params AS (\n  SELECT\n    {cols}\n),")

    for i, step in enumerate(translated):
        comma = "," if i < len(translated) - 1 else ""
        prefix = "" if i == 0 and not params else ""
        if i == 0 and not params:
            lines.append(f"WITH {_sql_ref(step.name)} AS (")
        else:
            lines.append(f"{_sql_ref(step.name)} AS (")
        lines.append(step.sql)
        lines.append(f"){comma}")

    last = translated[-1].name
    lines.append(f"SELECT *")
    lines.append(f"FROM {_sql_ref(last)};")
    return "\n".join(lines)
