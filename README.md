# C4Chinese

Welcome to **C4Chinese**, a custom programming language designed with a Chinese-based syntax. This project includes a full compilation pipeline (Lexer, Parser, Semantic Checker, Optimizer, Interpreter) and a custom IDE built specifically to make writing and debugging C4Chinese code a seamless experience.

## Documentation
For a comprehensive breakdown of the language, covering all of its features and various implementation details, the programmer can review the full specifications here:
* [C4Chinese Official Documentation](https://drive.google.com/file/d/1c6ozU1xNoHP2J9BehI_ZossxNFltzYir/view?usp=sharing)

---

## Getting Started

There are two ways to get C4Chinese up and running: using the pre-compiled executable for a quick start, or building it directly from the source code for development and debugging.

### Option 1: Using the Standalone Executable (Recommended)
For the most seamless experience without the need to install any dependencies, you can use our pre-built binary. 

Simply navigate to the project folder and double-click the **`IDE.exe`** file. This will instantly launch our custom IDE where you can write, compile, and debug C4Chinese.

### Option 2: Running from Source
If you want to modify the source code, recompile the grammar, or run the project from scratch, navigate to the `/Source Code` folder and execute the following commands. This will generate the necessary lexer and parser files via ANTLR4, as well as install all required Python dependencies.

```bash
# Generate the Lexer
antlr4.jar -Dlanguage=Python3 C4ChineseLexer.g4

# Generate the Parser and Visitor
antlr4.jar -Dlanguage=Python3 -visitor -no-listener C4ChineseParser.g4

# Install required dependencies
pip install -r requirements.txt
```
*(Note: Depending on your system setup, you might need to run the jar files using: `java antlr4.jar ...`)*

Once everything is set up, you can launch the custom IDE by running the following command:
```bash
python IDE.py
```

## Execution Modes: Run vs. Debug
The IDE features two modes of executing programs, allowing the programmer to execute programs continuously or analyze them line-by-line.

### Run Mode (Continuous Execution)
Selecting Run executes the program from start to finish without interruption.
- First, the IDE saves the active code to a temporary file (temp_run.c4).
- The code passes through the Lexer, Parser, and Semantic Checkers, sequentially.
- If an error is detected, the compilation halts and informs the programmer of the errors that must be fixed.
- If no errors are found, the code continues through the Optimizer.
- The runtime interpreter executes the program normally, pushing all standard output to the Interactive Console.
- If an input (geiwo) statement is encountered, execution pauses automatically and displays a prompt in the console. Once the programmer submits the input, execution of the program simply resumes.

### Debug Mode (Line-by-Line Execution)
Selecting Debug initiates an interactive debugging session. Instead of executing the program continuously, the interpreter pauses to allow for manual progression.
- **Line Highlighting**: Execution pauses at the first statement, highlighting the active line of code within the editor.
- **Live Memory Tracking**: Whenever execution pauses, the Environment Table and Call Stack dynamically refresh. This displays exactly how variables and memory addresses change during runtime.
- **Stepping Through Code**: Once Debug Mode is active, the Step button becomes available. Pressing this button advances the interpreter by exactly one statement. This enables the programmer to systematically walk through complex loops (buduan), recursive function calls, or pointer dereferences (^^) to isolate logical errors and observe data changes incrementally.

## The Debugger Tabs (Side Panel)
Located on the right, this panel lets you inspect the underlying memory and execution context of the program. It updates in real-time during debugging and includes:
- **Environment Table**: A live look at memory addresses, variable scopes, and nested struct/array values.
- **Call Stack**: Tracks the current depth within recursive functions or nested calls.
- **Symbol Table**: A static snapshot of all declared types, variables, and scopes.
- **Parse & Optimized Trees**: Visual breakdowns of the code’s Abstract Syntax Tree before and after optimization.

