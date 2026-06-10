# HW1: p0 Compiler — Adding `while` Syntax & Function Call Mechanism

## 1. Adding `while` Syntax: Design Principle

### Overview

I extended the p0 compiler (based on `07-if/compiler.c`) to support the `while` loop construct. The implementation required modifications to three core components: the **lexer**, the **parser**, and the **virtual machine (VM)**.

### Changes Made

#### (a) Lexer (`compiler.c` lines 24, 60-61)

- Added `TK_WHILE` to the TokenType enum.
- In `next_token()`, added `else if (strcmp(cur_token.text, "while") == 0) cur_token.type = TK_WHILE;` so the lexer recognizes the `while` keyword and emits the proper token.

#### (b) Parser (`compiler.c` lines 137-146)

Added a new clause in `statement()` for `TK_WHILE`:

```
while (cond) { body }
```

The intermediate code pattern generated is:

```
cond_pc:   ...compute condition into t1...
           JMP_F t1  end_pc
body_pc:   ...body statements...
           JMP      cond_pc
end_pc:
```

The implementation uses **backpatching**:
1. Record `cond_idx = quad_count` before generating the condition expression so we know where to jump back to.
2. Emit the condition expression code, which computes into a temporary variable `cond`.
3. Emit `JMP_F cond ?` with a placeholder result (`"?"`), recording its index as `jmp_f_idx`.
4. Parse all statements inside `{ }`.
5. After the body, emit `JMP - - cond_idx` to jump back to the condition check.
6. **Backpatch**: Write the current `quad_count` into `quads[jmp_f_idx].result`, so the `JMP_F` knows where to jump when the condition is false.

#### (c) VM (`compiler.c` lines 201-203)

Added handling for the `JMP` instruction:

```c
else if (strcmp(q.op, "JMP") == 0) {
    pc = atoi(q.result) - 1;
}
```

This performs an unconditional jump to the target quad index.

### Why This Design?

- **Backpatching** is a standard technique for code generation when the target address of a jump is not yet known at emission time. It avoids a separate "fixup" pass.
- The IR pattern `cond → JMP_F → body → JMP cond` is minimal and directly maps to how CPUs implement loops.
- The approach is consistent with the existing `if` statement implementation, which also uses backpatching for `JMP_F`.

### Example

Input: `test_while.p0`

```
func main() {
    i = 0;
    s = 0;
    while (i < 10) {
        s = s + i;
        i = i + 1;
    }
}
```

Generated IR:

```
000: FUNC_BEG   main       -          -
001: IMM        0          -          t1
002: STORE      t1         -          i
003: IMM        0          -          t2
004: STORE      t2         -          s
005: IMM        10         -          t3
006: CMP_LT     i          t3         t4
007: JMP_F      t4         -          012
008: ADD        s          i          t5
009: STORE      t5         -          s
010: IMM        1          -          t6
011: ADD        i          t6         t7
012: STORE      t7         -          i
013: JMP        -          -          005
014: FUNC_END   main       -          -
```

---

## 2. Function Call Mechanism in p0 Compiler

The p0 compiler supports function definitions and calls with parameter passing and return values. Here's how it works:

### Function Definition

A function is defined as:

```
func add(a, b) {
    return a + b;
}
```

The compiler parses this and emits:

```
FUNC_BEG  add     -       -
FORMAL    a       -       -
FORMAL    b       -       -
...function body...
FUNC_END  add     -       -
```

### Function Call

A function call like `add(3, 5)` is compiled into:

```
IMM       3       -       t1
PARAM     t1      -       -
IMM       5       -       t2
PARAM     t2      -       -
CALL      add     2       t3
```

### Runtime Mechanism

The VM uses a **stack-based frame model** with `Frame` structs:

```c
typedef struct {
    char names[100][32]; int values[100]; int count;
    int ret_pc; char ret_var[32];
    int incoming_args[10]; int formal_idx;
} Frame;
```

#### Step-by-step execution:

1. **Pre-scan**: Before execution, the VM scans all quads to build a function table (`func_names[]`/`func_pc[]`) mapping function names to entry point PCs (the quad after `FUNC_BEG`).

2. **PARAM**: When `PARAM` is encountered, the argument value is pushed onto a **parameter stack** (`param_stack`).

3. **CALL**: The `CALL` instruction:
   - Reads the argument count `p_count`.
   - Looks up the target function's PC in the function table.
   - **Creates a new stack frame**: increments `sp`, initializes the new frame's variable table, sets `ret_pc` to the next instruction after CALL, and stores the return variable name.
   - **Transfers arguments**: copies `p_count` values from `param_stack` into the new frame's `incoming_args[]`.
   - **Jumps** to the function's entry PC.

4. **FORMAL**: Maps each formal parameter to the corresponding incoming argument by index (`formal_idx`), storing the value into the frame's local variable table.

5. **RET_VAL**:
   - Evaluates the return expression (stored in the return variable).
   - Captures the return value, the return address (`ret_pc`), and the target variable name from the current frame.
   - **Pops the frame** (`sp--`), destroying the callee's scope.
   - **Stores the return value** into the caller's frame using the stored target variable name.
   - **Jumps** to `ret_address` (the instruction after the CALL in the caller).

6. **FUNC_END**: When a function ends without an explicit `return`, control returns to the caller with a nil/0 value.

### Supporting Recursion

The **separate parameter stack** (`param_stack`) is critical for recursion support. Without it, recursive calls would overwrite the caller's arguments. Each CALL:
- Saves arguments from `param_stack` into the new frame's `incoming_args[]`.
- Removes them from `param_stack` by adjusting `param_sp -= p_count`.

Since each recursive call creates a **new Frame** on the `stack[]` array, each invocation gets its own local variable scope and return address. This allows arbitrary-depth recursion, as demonstrated by the Fibonacci test.

### Visualizing a Call: `fib(10)`

```
CALL fib 1 t1        → create Frame, set ret_var=t1, copy 1 arg, jump to fib entry
FORMAL n              → n = 10
...fib body...
RET_VAL ...           → pop Frame, set t1 = return value, jump back to caller
```
