"""Traduz fórmulas de colunas calculadas do Power BI (DAX) para SQL DuckDB."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable

from pq.translators.errors import ParseError


class TokKind(Enum):
    NUMBER = auto()
    STRING = auto()
    IDENT = auto()
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()
    DOT = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    OP = auto()
    EOF = auto()


@dataclass
class Token:
    kind: TokKind
    value: str
    pos: int


def split_column_definition(text: str) -> tuple[str, str]:
    """Separa 'Nome da Coluna = expressão' em nome e corpo."""
    stripped = text.strip()
    if not stripped:
        raise ParseError("Fórmula vazia.")

    eq = stripped.find("=")
    if eq <= 0:
        raise ParseError("Use o formato: Nome da Coluna = expressão")

    name = stripped[:eq].strip()
    expr = stripped[eq + 1 :].strip()
    if not name:
        raise ParseError("Nome da coluna ausente antes do '='.")
    if not expr:
        raise ParseError("Expressão ausente após o '='.")
    return name, expr


class _Tokenizer:
    def __init__(self, source: str) -> None:
        self._source = source
        self._pos = 0
        self._len = len(source)

    def _peek(self, offset: int = 0) -> str | None:
        idx = self._pos + offset
        return self._source[idx] if idx < self._len else None

    def _advance(self, n: int = 1) -> None:
        self._pos += n

    def _skip_ws(self) -> None:
        while self._peek() is not None and self._peek() in " \t\r\n":
            self._advance()

    def _skip_comments(self) -> None:
        """Ignora comentários de linha `--` e `//` (estilo DAX / SQL)."""
        while True:
            self._skip_ws()
            if self._peek() == "-" and self._peek(1) == "-":
                while self._peek() is not None and self._peek() not in "\r\n":
                    self._advance()
                continue
            if self._peek() == "/" and self._peek(1) == "/":
                while self._peek() is not None and self._peek() not in "\r\n":
                    self._advance()
                continue
            break

    def next_token(self) -> Token:
        self._skip_comments()
        start = self._pos
        ch = self._peek()
        if ch is None:
            return Token(TokKind.EOF, "", start)

        if ch == "'":
            self._advance()
            buf: list[str] = []
            while self._peek() is not None:
                c = self._peek()
                if c == "'":
                    if self._peek(1) == "'":
                        buf.append("'")
                        self._advance(2)
                        continue
                    self._advance()
                    break
                buf.append(c)
                self._advance()
            return Token(TokKind.IDENT, "".join(buf), start)

        if ch == '"':
            self._advance()
            buf = []
            while self._peek() is not None:
                c = self._peek()
                if c == '"':
                    if self._peek(1) == '"':
                        buf.append('"')
                        self._advance(2)
                        continue
                    self._advance()
                    break
                buf.append(c)
                self._advance()
            return Token(TokKind.STRING, "".join(buf), start)

        if ch.isdigit() or (ch == "." and self._peek(1) is not None and self._peek(1).isdigit()):
            buf = []
            while self._peek() is not None and (self._peek().isdigit() or self._peek() == "."):
                buf.append(self._peek())
                self._advance()
            return Token(TokKind.NUMBER, "".join(buf), start)

        if ch in "([),." or ch == "[":
            self._advance()
            mapping = {
                "(": TokKind.LPAREN,
                ")": TokKind.RPAREN,
                ",": TokKind.COMMA,
                ".": TokKind.DOT,
                "[": TokKind.LBRACKET,
            }
            return Token(mapping[ch], ch, start)

        if ch == "]":
            self._advance()
            return Token(TokKind.RBRACKET, "]", start)

        two = self._source[self._pos : self._pos + 2]
        if two in ("<=", ">=", "<>", "&&", "||"):
            self._advance(2)
            return Token(TokKind.OP, two, start)

        if ch in "+-*/<>=!&":
            self._advance()
            return Token(TokKind.OP, ch, start)

        if ch.isalpha() or ch == "_":
            buf = []
            while self._peek() is not None and (self._peek().isalnum() or self._peek() == "_"):
                buf.append(self._peek())
                self._advance()
            return Token(TokKind.IDENT, "".join(buf), start)

        raise ParseError(f"Caractere inesperado '{ch}' na posição {self._pos + 1}.")


class _Parser:
    _DATE_PARTS = {
        "Date": lambda col: f'CAST("{col}" AS DATE)',
        "Year": lambda col: f'EXTRACT(YEAR FROM CAST("{col}" AS DATE))',
        "Month": lambda col: f'EXTRACT(MONTH FROM CAST("{col}" AS DATE))',
        "MonthNo": lambda col: f'EXTRACT(MONTH FROM CAST("{col}" AS DATE))',
        "Day": lambda col: f'EXTRACT(DAY FROM CAST("{col}" AS DATE))',
    }

    def __init__(self, source: str) -> None:
        self._tok = _Tokenizer(source)
        self._cur = self._tok.next_token()
        self._vars: dict[str, str] = {}

    def _resolve_var(self, name: str) -> str | None:
        if name in self._vars:
            return self._vars[name]
        upper = name.upper()
        if upper in self._vars:
            return self._vars[upper]
        return None

    def _register_var(self, name: str, sql_expr: str) -> None:
        self._vars[name] = sql_expr
        self._vars[name.upper()] = sql_expr

    def parse(self) -> str:
        if self._match(TokKind.IDENT, "VAR"):
            return self._parse_var_block()
        expr = self._parse_or()
        if self._cur.kind != TokKind.EOF:
            raise ParseError(f"Tokens extras após a expressão: '{self._cur.value}'.")
        return expr

    def _parse_var_block(self) -> str:
        while self._match(TokKind.IDENT, "VAR"):
            self._advance()
            var_name = self._eat(TokKind.IDENT).value
            self._eat(TokKind.OP, "=")
            value = self._parse_or()
            self._register_var(var_name, value)
        if not self._match(TokKind.IDENT, "RETURN"):
            raise ParseError("Bloco VAR deve terminar com RETURN.")
        self._advance()
        result = self._parse_or()
        if self._cur.kind != TokKind.EOF:
            raise ParseError(f"Tokens extras após RETURN: '{self._cur.value}'.")
        return result

    def _eat(self, kind: TokKind, value: str | None = None) -> Token:
        if self._cur.kind != kind or (value is not None and self._cur.value != value):
            got = self._cur.value or self._cur.kind.name
            raise ParseError(f"Esperado '{value or kind.name}', encontrado '{got}'.")
        tok = self._cur
        self._cur = self._tok.next_token()
        return tok

    def _match(self, kind: TokKind, value: str | None = None) -> bool:
        return self._cur.kind == kind and (value is None or self._cur.value == value)

    def _parse_or(self) -> str:
        left = self._parse_and()
        while self._match(TokKind.IDENT, "OR") or self._match(TokKind.OP, "||"):
            self._advance()
            right = self._parse_and()
            left = f"({left} OR {right})"
        return left

    def _parse_and(self) -> str:
        left = self._parse_comparison()
        while self._match(TokKind.IDENT, "AND") or self._match(TokKind.OP, "&&"):
            self._advance()
            right = self._parse_comparison()
            left = f"({left} AND {right})"
        return left

    def _parse_comparison(self) -> str:
        left = self._parse_concat()
        ops = ("=", "<>", "!=", "<=", ">=", "<", ">")
        while self._cur.kind == TokKind.OP and self._cur.value in ops:
            op = self._cur.value
            self._advance()
            right = self._parse_concat()
            sql_op = "<>" if op == "!=" else op
            left = f"({left} {sql_op} {right})"
        return left

    def _parse_concat(self) -> str:
        left = self._parse_additive()
        while self._match(TokKind.OP, "&"):
            self._advance()
            right = self._parse_additive()
            left = f"({left} || {right})"
        return left

    def _parse_additive(self) -> str:
        left = self._parse_multiplicative()
        while self._match(TokKind.OP, "+") or self._match(TokKind.OP, "-"):
            op = self._cur.value
            self._advance()
            right = self._parse_multiplicative()
            left = f"({left} {op} {right})"
        return left

    def _parse_multiplicative(self) -> str:
        left = self._parse_unary()
        while self._match(TokKind.OP, "*") or self._match(TokKind.OP, "/"):
            op = self._cur.value
            self._advance()
            right = self._parse_unary()
            left = f"({left} {op} {right})"
        return left

    def _parse_unary(self) -> str:
        if self._match(TokKind.OP, "-"):
            self._advance()
            return f"(-{self._parse_unary()})"
        if self._match(TokKind.IDENT, "NOT"):
            self._advance()
            return f"(NOT {self._parse_unary()})"
        return self._parse_primary()

    def _parse_primary(self) -> str:
        if self._match(TokKind.NUMBER):
            tok = self._advance()
            return tok.value

        if self._match(TokKind.STRING):
            tok = self._advance()
            escaped = tok.value.replace("'", "''")
            return f"'{escaped}'"

        if self._match(TokKind.IDENT, "TRUE"):
            self._advance()
            return "TRUE"

        if self._match(TokKind.IDENT, "FALSE"):
            self._advance()
            return "FALSE"

        if self._match(TokKind.IDENT):
            return self._parse_call_or_ident()

        if self._match(TokKind.LBRACKET):
            return self._parse_bracket_column(None)

        if self._match(TokKind.LPAREN):
            self._advance()
            inner = self._parse_or()
            self._eat(TokKind.RPAREN)
            return f"({inner})"

        raise ParseError(f"Expressão inválida perto de '{self._cur.value}'.")

    def _parse_call_or_ident(self) -> str:
        name_tok = self._eat(TokKind.IDENT)
        name = name_tok.value.upper()

        if self._match(TokKind.LBRACKET):
            return self._parse_bracket_column(name_tok.value)

        if not self._match(TokKind.LPAREN):
            resolved = self._resolve_var(name_tok.value)
            if resolved is not None:
                return resolved
            return name_tok.value

        self._advance()
        args: list[str] = []
        if not self._match(TokKind.RPAREN):
            args.append(self._parse_or())
            while self._match(TokKind.COMMA):
                self._advance()
                args.append(self._parse_or())
        self._eat(TokKind.RPAREN)

        return self._translate_call(name, args)

    def _parse_bracket_column(self, table: str | None) -> str:
        self._eat(TokKind.LBRACKET)
        parts: list[str] = []
        while not self._match(TokKind.RBRACKET):
            if self._cur.kind == TokKind.IDENT:
                parts.append(self._advance().value)
            else:
                raise ParseError(
                    f"Nome de coluna inválido entre colchetes: '{self._cur.value}'."
                )
        self._advance()
        if not parts:
            raise ParseError("Nome de coluna vazio entre colchetes.")
        col = " ".join(parts)

        if self._match(TokKind.DOT):
            self._advance()
            self._eat(TokKind.LBRACKET)
            if self._cur.kind != TokKind.IDENT:
                raise ParseError("Propriedade inválida após coluna.")
            prop = self._advance().value
            self._eat(TokKind.RBRACKET)
            fn = self._DATE_PARTS.get(prop)
            if fn:
                return fn(col)
            raise ParseError(f"Propriedade '.[{prop}]' não suportada.")

        _ = table
        return f'"{col}"'

    def _translate_call(self, name: str, args: list[str]) -> str:
        translators: dict[str, Callable[[list[str]], str]] = {
            "IF": self._fn_if,
            "FORMAT": self._fn_format,
            "TODAY": lambda a: self._fn_nullary(a, "CURRENT_DATE"),
            "NOW": lambda a: self._fn_nullary(a, "CURRENT_TIMESTAMP"),
            "DATE": self._fn_date,
            "YEAR": lambda a: self._fn_unary(a, "EXTRACT(YEAR FROM CAST({} AS DATE))"),
            "MONTH": lambda a: self._fn_unary(a, "EXTRACT(MONTH FROM CAST({} AS DATE))"),
            "DAY": lambda a: self._fn_unary(a, "EXTRACT(DAY FROM CAST({} AS DATE))"),
            "INT": lambda a: self._fn_unary(a, "CAST(FLOOR({}) AS BIGINT)"),
            "ROUND": self._fn_round,
            "ABS": lambda a: self._fn_unary(a, "ABS({})"),
            "BLANK": lambda a: self._fn_nullary(a, "NULL"),
            "UPPER": lambda a: self._fn_unary(a, "UPPER({})"),
            "LOWER": lambda a: self._fn_unary(a, "LOWER({})"),
            "LEN": lambda a: self._fn_unary(a, "LENGTH({})"),
            "LEFT": self._fn_left,
            "RIGHT": self._fn_right,
            "FIND": self._fn_find,
            "SEARCH": self._fn_search,
            "SUBSTITUTE": self._fn_substitute,
            "TRIM": lambda a: self._fn_unary(a, "TRIM(CAST({} AS VARCHAR))"),
            "CONCATENATE": self._fn_concatenate,
            "SWITCH": self._fn_switch,
        }
        fn = translators.get(name)
        if fn is None:
            raise ParseError(f"Função '{name}' não suportada.")
        return fn(args)

    @staticmethod
    def _fn_nullary(args: list[str], sql: str) -> str:
        if args:
            raise ParseError(f"Função não aceita argumentos.")
        return sql

    @staticmethod
    def _fn_unary(args: list[str], template: str) -> str:
        if len(args) != 1:
            raise ParseError("Função espera exatamente 1 argumento.")
        return template.format(args[0])

    @staticmethod
    def _fn_if(args: list[str]) -> str:
        if len(args) == 2:
            cond, when_true = args
            return f"CASE WHEN {cond} THEN {when_true} ELSE NULL END"
        if len(args) == 3:
            cond, when_true, when_false = args
            return f"CASE WHEN {cond} THEN {when_true} ELSE {when_false} END"
        raise ParseError("IF espera 2 ou 3 argumentos.")

    @staticmethod
    def _fn_format(args: list[str]) -> str:
        if len(args) != 2:
            raise ParseError("FORMAT espera 2 argumentos.")
        value, fmt = args
        fmt_clean = fmt.strip().strip("'").strip('"')
        if fmt_clean in ("0", "General Number", "#,##0"):
            return f"CAST(ROUND({value}, 0) AS BIGINT)"
        if fmt_clean in ("0.00", "Fixed", "#,##0.00"):
            return f"ROUND({value}, 2)"
        return f"CAST({value} AS VARCHAR)"

    @staticmethod
    def _fn_date(args: list[str]) -> str:
        if len(args) != 3:
            raise ParseError("DATE espera 3 argumentos (ano, mês, dia).")
        y, m, d = args
        return f"MAKE_DATE({y}, {m}, {d})"

    @staticmethod
    def _fn_round(args: list[str]) -> str:
        if len(args) == 1:
            return f"ROUND({args[0]}, 0)"
        if len(args) == 2:
            return f"ROUND({args[0]}, {args[1]})"
        raise ParseError("ROUND espera 1 ou 2 argumentos.")

    @staticmethod
    def _fn_left(args: list[str]) -> str:
        if len(args) != 2:
            raise ParseError("LEFT espera 2 argumentos.")
        return f"LEFT({args[0]}, {args[1]})"

    @staticmethod
    def _fn_right(args: list[str]) -> str:
        if len(args) != 2:
            raise ParseError("RIGHT espera 2 argumentos.")
        return f"RIGHT({args[0]}, {args[1]})"

    @staticmethod
    def _str_pos(find_text: str, within_text: str, *, case_insensitive: bool) -> str:
        haystack = f"CAST({within_text} AS VARCHAR)"
        needle = f"CAST({find_text} AS VARCHAR)"
        if case_insensitive:
            haystack = f"LOWER({haystack})"
            needle = f"LOWER({needle})"
        return f"STRPOS({haystack}, {needle})"

    @staticmethod
    def _str_pos_from(args: list[str], *, case_insensitive: bool) -> str:
        if len(args) < 2 or len(args) > 4:
            label = "SEARCH" if case_insensitive else "FIND"
            raise ParseError(f"{label} espera 2 a 4 argumentos.")
        find_text, within_text = args[0], args[1]
        start_num = args[2] if len(args) >= 3 else "1"
        not_found = args[3] if len(args) == 4 else "0"
        pos = _Parser._str_pos(find_text, within_text, case_insensitive=case_insensitive)
        if start_num == "1":
            pos_expr = pos
        else:
            pos_expr = (
                f"(CASE WHEN STRPOS(SUBSTRING(CAST({within_text} AS VARCHAR), "
                f"CAST({start_num} AS INTEGER)), CAST({find_text} AS VARCHAR)) > 0 "
                f"THEN STRPOS(SUBSTRING(CAST({within_text} AS VARCHAR), "
                f"CAST({start_num} AS INTEGER)), CAST({find_text} AS VARCHAR)) "
                f"+ CAST({start_num} AS INTEGER) - 1 ELSE 0 END)"
            )
            if case_insensitive:
                pos_expr = (
                    f"(CASE WHEN STRPOS(LOWER(SUBSTRING(CAST({within_text} AS VARCHAR), "
                    f"CAST({start_num} AS INTEGER))), LOWER(CAST({find_text} AS VARCHAR))) > 0 "
                    f"THEN STRPOS(LOWER(SUBSTRING(CAST({within_text} AS VARCHAR), "
                    f"CAST({start_num} AS INTEGER))), LOWER(CAST({find_text} AS VARCHAR))) "
                    f"+ CAST({start_num} AS INTEGER) - 1 ELSE 0 END)"
                )
        return f"CASE WHEN ({pos_expr}) > 0 THEN ({pos_expr}) ELSE {not_found} END"

    @classmethod
    def _fn_find(cls, args: list[str]) -> str:
        return cls._str_pos_from(args, case_insensitive=False)

    @classmethod
    def _fn_search(cls, args: list[str]) -> str:
        return cls._str_pos_from(args, case_insensitive=True)

    @staticmethod
    def _fn_substitute(args: list[str]) -> str:
        if len(args) == 3:
            text, old, new = args
            return (
                f"REPLACE(CAST({text} AS VARCHAR), CAST({old} AS VARCHAR), "
                f"CAST({new} AS VARCHAR))"
            )
        if len(args) == 4:
            raise ParseError(
                "SUBSTITUTE com número de ocorrência (4º argumento) ainda não suportado."
            )
        raise ParseError("SUBSTITUTE espera 3 ou 4 argumentos.")

    @staticmethod
    def _fn_concatenate(args: list[str]) -> str:
        if len(args) < 2:
            raise ParseError("CONCATENATE espera ao menos 2 argumentos.")
        return " || ".join(f"({a})" for a in args)

    @staticmethod
    def _fn_switch(args: list[str]) -> str:
        if len(args) < 3:
            raise ParseError("SWITCH espera expressão, pares valor/resultado e opcional padrão.")
        expr = args[0]
        pairs = args[1:]
        if len(pairs) % 2 == 1:
            default = pairs[-1]
            pairs = pairs[:-1]
        else:
            default = "NULL"
        parts = [f"CASE"]
        for i in range(0, len(pairs), 2):
            parts.append(f"WHEN {expr} = {pairs[i]} THEN {pairs[i + 1]}")
        parts.append(f"ELSE {default} END")
        return " ".join(parts)

    def _advance(self) -> Token:
        tok = self._cur
        self._cur = self._tok.next_token()
        return tok


def translate_dax_expression(expr: str) -> str:
    """Converte expressão DAX (corpo da fórmula) para SQL DuckDB."""
    return _Parser(expr.strip()).parse()


def translate_power_column(definition: str) -> tuple[str, str]:
    """Converte 'Coluna = expressão' do Power BI para (nome, sql_expr)."""
    name, expr = split_column_definition(definition)
    sql_expr = translate_dax_expression(expr)
    return name, sql_expr


def strip_dax_comments(text: str) -> str:
    """Remove comentários de linha `--` e `//` respeitando strings."""
    lines: list[str] = []
    for line in text.splitlines():
        cleaned = _strip_line_comment(line)
        if cleaned.strip():
            lines.append(cleaned)
    return "\n".join(lines)


def _strip_line_comment(line: str) -> str:
    in_string: str | None = None
    i = 0
    while i < len(line):
        ch = line[i]
        if in_string:
            if ch == in_string and i + 1 < len(line) and line[i + 1] == in_string:
                i += 2
                continue
            if ch == in_string:
                in_string = None
        elif ch in ("'", '"'):
            in_string = ch
        elif ch == "-" and i + 1 < len(line) and line[i + 1] == "-":
            return line[:i].rstrip()
        elif ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
            return line[:i].rstrip()
        i += 1
    return line


def normalize_power_formula(text: str) -> str:
    """Remove comentários e colapsa espaços em branco redundantes."""
    without_comments = strip_dax_comments(text.strip())
    return re.sub(r"\s+", " ", without_comments).strip()
