#!/usr/bin/env python3
"""
tinypy - Tiny Python-like Language Interpreter

A dynamically-typed language with indentation-based blocks.
Supports: variables, arithmetic, comparisons, if/elif/else,
while loops, functions, recursion, print.

Usage:
    python tinypy.py <source_file>
"""

import sys
import re
import os

# ============================================================
# 1. Token Specification
# ============================================================
token_spec = [
    ('COMMENT',  r'#.*'),
    ('NUMBER',   r'\d+'),
    ('STRING',   r'"[^"]*"'),
    ('IDENT',    r'[a-zA-Z_][a-zA-Z0-9_]*'),
    ('EQ',       r'=='), ('NE', r'!='), ('LE', r'<='), ('GE', r'>='),
    ('LT',       r'<'),  ('GT', r'>'),
    ('ASSIGN',   r'='),
    ('PLUS',     r'\+'), ('MINUS', r'-'), ('MUL', r'\*'), ('DIV', r'/'), ('MOD', r'%'),
    ('LPAREN',   r'\('), ('RPAREN', r'\)'),
    ('COLON',    r':'),  ('COMMA', r','),
    ('SKIP',     r'[ \t]+'),
    ('MISMATCH', r'.'),
]

KEYWORDS = {
    'if': 'IF', 'elif': 'ELIF', 'else': 'ELSE',
    'while': 'WHILE', 'def': 'DEF', 'return': 'RETURN',
    'break': 'BREAK', 'and': 'AND', 'or': 'OR', 'not': 'NOT',
}


class Token:
    def __init__(self, typ, value, lineno):
        self.type = typ
        self.value = value
        self.lineno = lineno

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, L{self.lineno})"


# ============================================================
# 2. Lexer
# ============================================================
def tokenize_line(line, lineno):
    """Tokenize a single line (without leading whitespace)."""
    tokens = []
    pos = 0
    while pos < len(line):
        match = None
        for tok_type, pattern in token_spec:
            m = re.match(pattern, line[pos:])
            if m:
                match = m
                break
        if not match:
            raise SyntaxError(f"Unexpected character {line[pos]!r} at line {lineno}")
        value = match.group(0)
        pos += len(value)
        if tok_type == 'COMMENT' or tok_type == 'SKIP':
            continue
        if tok_type == 'IDENT' and value in KEYWORDS:
            typ = KEYWORDS[value]
        elif tok_type == 'MISMATCH':
            raise SyntaxError(f"Unexpected character {value!r} at line {lineno}")
        else:
            typ = tok_type
        tokens.append(Token(typ, value, lineno))
    return tokens


def lex(source):
    """Lex the entire source, handling indentation."""
    lines = source.split('\n')
    tokens = []
    indent_stack = [0]
    lineno = 0

    for raw_line in lines:
        lineno += 1
        stripped = raw_line.lstrip()
        # empty line or comment-only line: no indent change
        if stripped == '' or stripped.startswith('#'):
            continue

        indent = len(raw_line) - len(stripped)

        if indent > indent_stack[-1]:
            indent_stack.append(indent)
            tokens.append(Token('INDENT', '', lineno))
        elif indent < indent_stack[-1]:
            while indent_stack and indent_stack[-1] > indent:
                indent_stack.pop()
                tokens.append(Token('DEDENT', '', lineno))
            if indent_stack[-1] != indent:
                raise SyntaxError(
                    f"Indentation mismatch at line {lineno}: "
                    f"expected indent {indent_stack[-1]}, got {indent}"
                )

        line_tokens = tokenize_line(stripped, lineno)
        tokens.extend(line_tokens)
        tokens.append(Token('NEWLINE', '\n', lineno))

    # close all remaining indent levels
    while len(indent_stack) > 1:
        indent_stack.pop()
        tokens.append(Token('DEDENT', '', lineno))

    tokens.append(Token('EOF', '', lineno))
    return tokens


# ============================================================
# 3. AST Node Definitions
# ============================================================
class Program:
    def __init__(self, statements):
        self.statements = statements


class Number:
    def __init__(self, value):
        self.value = value


class String:
    def __init__(self, value):
        self.value = value


class Name:
    def __init__(self, name):
        self.name = name


class BinOp:
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right


class UnaryOp:
    def __init__(self, op, expr):
        self.op = op
        self.expr = expr


class Assign:
    def __init__(self, name, value):
        self.name = name
        self.value = value


class Call:
    def __init__(self, func, args):
        self.func = func
        self.args = args


class If:
    def __init__(self, cond, body, elifs, else_body):
        self.cond = cond
        self.body = body
        self.elifs = elifs
        self.else_body = else_body


class While:
    def __init__(self, cond, body):
        self.cond = cond
        self.body = body


class FuncDef:
    def __init__(self, name, params, body):
        self.name = name
        self.params = params
        self.body = body


class Return:
    def __init__(self, value):
        self.value = value


class Break:
    pass


# ============================================================
# 4. Parser
# ============================================================
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def consume(self, expected=None):
        tok = self.tokens[self.pos]
        if expected is not None and tok.type != expected:
            raise SyntaxError(
                f"Expected {expected}, got {tok.type} ({tok.value}) "
                f"at line {tok.lineno}"
            )
        self.pos += 1
        return tok

    def parse(self):
        statements = self.parse_block()
        return Program(statements)

    def parse_block(self):
        statements = []
        while self.peek().type not in ('DEDENT', 'EOF'):
            stmt = self.parse_statement()
            if stmt is not None:
                statements.append(stmt)
        return statements

    def parse_statement(self):
        tok = self.peek()
        if tok.type == 'IF':
            return self.parse_if()
        elif tok.type == 'WHILE':
            return self.parse_while()
        elif tok.type == 'DEF':
            return self.parse_funcdef()
        elif tok.type == 'RETURN':
            return self.parse_return()
        elif tok.type == 'BREAK':
            return self.parse_break()
        elif tok.type == 'NEWLINE':
            self.consume('NEWLINE')
            return None
        else:
            return self.parse_simple_stmt()

    def parse_simple_stmt(self):
        expr = self.parse_expression()
        if self.peek().type == 'ASSIGN':
            if not isinstance(expr, Name):
                raise SyntaxError(f"Left-hand side of assignment must be a name at line {expr.lineno}")
            self.consume('ASSIGN')
            value = self.parse_expression()
            self.consume('NEWLINE')
            return Assign(expr.name, value)
        else:
            self.consume('NEWLINE')
            return expr

    def parse_if(self):
        self.consume('IF')
        cond = self.parse_expression()
        self.consume('COLON')
        self.consume('NEWLINE')
        self.consume('INDENT')
        body = self.parse_block()
        self.consume('DEDENT')

        elifs = []
        while self.peek().type == 'ELIF':
            self.consume('ELIF')
            elif_cond = self.parse_expression()
            self.consume('COLON')
            self.consume('NEWLINE')
            self.consume('INDENT')
            elif_body = self.parse_block()
            self.consume('DEDENT')
            elifs.append((elif_cond, elif_body))

        else_body = None
        if self.peek().type == 'ELSE':
            self.consume('ELSE')
            self.consume('COLON')
            self.consume('NEWLINE')
            self.consume('INDENT')
            else_body = self.parse_block()
            self.consume('DEDENT')

        return If(cond, body, elifs, else_body)

    def parse_while(self):
        self.consume('WHILE')
        cond = self.parse_expression()
        self.consume('COLON')
        self.consume('NEWLINE')
        self.consume('INDENT')
        body = self.parse_block()
        self.consume('DEDENT')
        return While(cond, body)

    def parse_funcdef(self):
        self.consume('DEF')
        name = self.consume('IDENT').value
        self.consume('LPAREN')
        params = []
        while self.peek().type != 'RPAREN':
            params.append(self.consume('IDENT').value)
            if self.peek().type == 'COMMA':
                self.consume('COMMA')
        self.consume('RPAREN')
        self.consume('COLON')
        self.consume('NEWLINE')
        self.consume('INDENT')
        body = self.parse_block()
        self.consume('DEDENT')
        return FuncDef(name, params, body)

    def parse_return(self):
        self.consume('RETURN')
        value = None
        if self.peek().type != 'NEWLINE':
            value = self.parse_expression()
        self.consume('NEWLINE')
        return Return(value)

    def parse_break(self):
        self.consume('BREAK')
        self.consume('NEWLINE')
        return Break()

    # --- Expression parsing (recursive descent) ---
    def parse_expression(self):
        return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        while self.peek().type == 'AND':
            self.consume('AND')
            right = self.parse_and()
            left = BinOp(left, 'and', right)
        return left

    def parse_and(self):
        left = self.parse_not()
        while self.peek().type == 'AND':
            self.consume('AND')
            right = self.parse_not()
            left = BinOp(left, 'and', right)
        return left

    def parse_not(self):
        if self.peek().type == 'NOT':
            self.consume('NOT')
            return UnaryOp('not', self.parse_not())
        return self.parse_comparison()

    def parse_comparison(self):
        left = self.parse_arith()
        while self.peek().type in ('EQ', 'NE', 'LT', 'GT', 'LE', 'GE'):
            op = self.consume().value
            right = self.parse_arith()
            left = BinOp(left, op, right)
        return left

    def parse_arith(self):
        left = self.parse_term()
        while self.peek().type in ('PLUS', 'MINUS'):
            op = self.consume().value
            right = self.parse_term()
            left = BinOp(left, op, right)
        return left

    def parse_term(self):
        left = self.parse_factor()
        while self.peek().type in ('MUL', 'DIV', 'MOD'):
            op = self.consume().value
            right = self.parse_factor()
            left = BinOp(left, op, right)
        return left

    def parse_factor(self):
        tok = self.peek()
        if tok.type == 'NUMBER':
            self.consume()
            return Number(int(tok.value))
        elif tok.type == 'STRING':
            self.consume()
            return String(tok.value[1:-1])
        elif tok.type == 'IDENT':
            name = self.consume().value
            if self.peek().type == 'LPAREN':
                self.consume('LPAREN')
                args = []
                while self.peek().type != 'RPAREN':
                    args.append(self.parse_expression())
                    if self.peek().type == 'COMMA':
                        self.consume('COMMA')
                self.consume('RPAREN')
                return Call(name, args)
            return Name(name)
        elif tok.type == 'LPAREN':
            self.consume()
            expr = self.parse_expression()
            self.consume('RPAREN')
            return expr
        elif tok.type == 'MINUS':
            self.consume()
            return UnaryOp('-', self.parse_factor())
        elif tok.type == 'PLUS':
            self.consume()
            return self.parse_factor()
        raise SyntaxError(
            f"Unexpected token {tok.type} ({tok.value}) at line {tok.lineno}"
        )


# ============================================================
# 5. Evaluator
# ============================================================
class ReturnException(Exception):
    def __init__(self, value):
        self.value = value


class BreakException(Exception):
    pass


class Function:
    def __init__(self, name, params, body, closure):
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure


class Environment:
    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent

    def get(self, name):
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.get(name)
        raise NameError(f"Name '{name}' is not defined")

    def set(self, name, value):
        if name in self.vars:
            self.vars[name] = value
        elif self.parent:
            self.parent.set(name, value)
        else:
            self.vars[name] = value

    def define(self, name, value):
        self.vars[name] = value


class Evaluator:
    def __init__(self):
        self.env = Environment()
        self.env.define('print', print)
        self.env.define('range', range)

    def eval(self, node, env=None):
        if env is None:
            env = self.env

        if isinstance(node, Program):
            for stmt in node.statements:
                self.eval(stmt, env)
            return None

        elif isinstance(node, Number):
            return node.value

        elif isinstance(node, String):
            return node.value

        elif isinstance(node, Name):
            return env.get(node.name)

        elif isinstance(node, BinOp):
            left = self.eval(node.left, env)
            right = self.eval(node.right, env)
            if node.op == '+':
                return left + right
            elif node.op == '-':
                return left - right
            elif node.op == '*':
                return left * right
            elif node.op == '/':
                return left // right
            elif node.op == '%':
                return left % right
            elif node.op == '==':
                return left == right
            elif node.op == '!=':
                return left != right
            elif node.op == '<':
                return left < right
            elif node.op == '>':
                return left > right
            elif node.op == '<=':
                return left <= right
            elif node.op == '>=':
                return left >= right
            elif node.op == 'and':
                return left and right
            elif node.op == 'or':
                return left or right

        elif isinstance(node, UnaryOp):
            val = self.eval(node.expr, env)
            if node.op == '-':
                return -val
            elif node.op == 'not':
                return not val

        elif isinstance(node, Assign):
            val = self.eval(node.value, env)
            env.set(node.name, val)
            return val

        elif isinstance(node, Call):
            func = env.get(node.func)
            args = [self.eval(a, env) for a in node.args]
            if isinstance(func, type(print)):
                return func(*args)
            if isinstance(func, Function):
                new_env = Environment(func.closure)
                for param, arg in zip(func.params, args):
                    new_env.define(param, arg)
                try:
                    for stmt in func.body:
                        self.eval(stmt, new_env)
                    return None
                except ReturnException as e:
                    return e.value
            raise TypeError(f"'{node.func}' is not callable")

        elif isinstance(node, If):
            if self.eval(node.cond, env):
                for stmt in node.body:
                    self.eval(stmt, env)
            else:
                found = False
                for elif_cond, elif_body in node.elifs:
                    if self.eval(elif_cond, env):
                        for stmt in elif_body:
                            self.eval(stmt, env)
                        found = True
                        break
                if not found and node.else_body:
                    for stmt in node.else_body:
                        self.eval(stmt, env)
            return None

        elif isinstance(node, While):
            while self.eval(node.cond, env):
                try:
                    for stmt in node.body:
                        self.eval(stmt, env)
                except BreakException:
                    break
            return None

        elif isinstance(node, FuncDef):
            func = Function(node.name, node.params, node.body, env)
            env.define(node.name, func)
            return func

        elif isinstance(node, Return):
            value = self.eval(node.value, env) if node.value else None
            raise ReturnException(value)

        elif isinstance(node, Break):
            raise BreakException()

        raise TypeError(f"Unknown AST node: {type(node).__name__}")


# ============================================================
# 6. Main
# ============================================================
def run(source):
    tokens = lex(source)
    parser = Parser(tokens)
    ast = parser.parse()
    ev = Evaluator()
    ev.eval(ast)


def main():
    if len(sys.argv) < 2:
        print("Usage: python tinypy.py <source_file>")
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)

    with open(path, 'r', encoding='utf-8') as f:
        source = f.read()

    try:
        run(source)
    except SyntaxError as e:
        print(f"SyntaxError: {e}", file=sys.stderr)
        sys.exit(1)
    except NameError as e:
        print(f"NameError: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"RuntimeError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
