# HW2: tinypy — 小型 Python-like 語言直譯器

## 語言設計

tinypy 是一個模仿 Python 語法的小型程式語言，使用**縮排**來定義程式區塊，採用**動態弱型別**，以**直譯器**方式執行。

### 設計目標

1. **簡單易學**：語法與 Python 相似，適合初學者
2. **功能完整**：支援變數、四則運算、比較運算、邏輯運算、條件判斷、迴圈、函數與遞迴
3. **教學用途**：程式碼精簡，易於理解直譯器的工作原理

### 功能特性

| 特性 | 說明 |
|------|------|
| 型別系統 | 動態弱型別（整數、字串、布林） |
| 執行方式 | 直譯器（AST walker） |
| 區塊定義 | 縮排（indentation） |
| 變數 | 動態宣告，無需關鍵字 |
| 運算 | `+`, `-`, `*`, `/`, `%` |
| 比較 | `==`, `!=`, `<`, `>`, `<=`, `>=` |
| 邏輯 | `and`, `or`, `not` |
| 條件 | `if` / `elif` / `else` |
| 迴圈 | `while`，支援 `break` |
| 函數 | `def`，支援遞迴 |
| 內建函數 | `print()`, `range()` |
| 註解 | `#` 到行尾 |
| 垃圾蒐集 | 無（Python 的 GC 自動管理） |

### 程式範例

```python
# 遞迴費氏數列
def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)

print(fib(10))
```

---

## EBNF 語法

```
program      = { statement }
statement    = simple_stmt | compound_stmt
simple_stmt  = assign_stmt | expr_stmt
compound_stmt = if_stmt | while_stmt | func_def

assign_stmt  = IDENT "=" expression NEWLINE
expr_stmt    = expression NEWLINE

if_stmt      = "if" expression ":" NEWLINE INDENT { statement } DEDENT
               { "elif" expression ":" NEWLINE INDENT { statement } DEDENT }
               [ "else" ":" NEWLINE INDENT { statement } DEDENT ]
while_stmt   = "while" expression ":" NEWLINE INDENT { statement } DEDENT
func_def     = "def" IDENT "(" [ IDENT { "," IDENT } ] ")" ":"
               NEWLINE INDENT { statement } DEDENT
return_stmt  = "return" [ expression ] NEWLINE
break_stmt   = "break" NEWLINE

expression   = or_expr
or_expr      = and_expr { "or" and_expr }
and_expr     = not_expr { "and" not_expr }
not_expr     = [ "not" ] comparison
comparison   = arith_expr { ("==" | "!=" | "<" | ">" | "<=" | ">=") arith_expr }
arith_expr   = term { ("+" | "-") term }
term         = factor { ("*" | "/" | "%") factor }
factor       = NUMBER
             | STRING
             | IDENT [ "(" [ expression { "," expression } ] ")" ]
             | "(" expression ")"
             | "+" factor
             | "-" factor
```

---

## 實作架構

直譯器 `tinypy.py` 由三個主要模組組成：

### 1. Lexer（詞法分析器）
- 逐行掃描原始碼，處理縮排層級
- 將縮排變化轉為 `INDENT` / `DEDENT` 記號
- 使用正規表達式將每行內容切分為 Token

### 2. Parser（語法分析器）
- 遞迴下降解析（Recursive Descent Parsing）
- 根據 EBNF 語法建構抽象語法樹（AST）
- 每個語法規則對應一個 `parse_xxx()` 方法

### 3. Evaluator（求值器）
- 走訪 AST 並執行
- 使用 `Environment` 類別實作變數作用域（scope chain）
- 函數呼叫時建立新的環境框架（lexical scoping）
- 透過 `ReturnException` 處理回傳值

---

## 執行方式

```bash
python tinypy.py samples/hello.tpy
python tinypy.py samples/fib.tpy
python tinypy.py samples/fact.tpy
python tinypy.py samples/while.tpy
python tinypy.py samples/if.tpy
```
