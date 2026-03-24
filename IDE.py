import sys
import traceback
import re
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPlainTextEdit, QToolBar, 
                             QSplitter, QTabWidget, QTableWidget, QTreeWidget, QTreeWidgetItem,
                             QFileDialog, QTextEdit, QWidget)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QThread, QRect, QSize
from PyQt6.QtGui import QFont, QAction, QTextCharFormat, QColor, QTextCursor, QTextFormat, QPainter
import threading
from PyQt6.QtWidgets import QTableWidgetItem
from antlr4.tree.Tree import TerminalNodeImpl

from Parser import parse
from Optimizer import optimize
from Interpreter import InterpreterVisitor, TypeManager
import time

# --- STDOUT REDIRECTOR ---
# Captures standard prints and semantic error logs and sends them to the GUI console
class EmittingStream(QObject):
    textWritten = pyqtSignal(str)
    def write(self, text):
        self.textWritten.emit(str(text))
    def flush(self):
        pass

class InterpreterWorker(QThread):
    # Signals to talk back to the main GUI
    paused = pyqtSignal(object, object, int) 
    finished = pyqtSignal(int)
    error = pyqtSignal(str)
    input_requested = pyqtSignal(str)

    def __init__(self, interpreter, optimized_tree):
        super().__init__()
        self.interpreter = interpreter
        self.optimized_tree = optimized_tree
        self.step_event = threading.Event() 
        
        self.input_event = threading.Event()
        self.input_value = ""

    def run(self):
        # Attach the hooks before running
        self.interpreter.debug_hook = self.pause_execution
        self.interpreter.input_hook = self.request_input 
        
        try:
            exit_code = self.interpreter.visit(self.optimized_tree)
            self.finished.emit(exit_code if exit_code is not None else 0)
        except Exception as e:
            self.error.emit(str(e))
            traceback.print_exc()

    def pause_execution(self, interpreter_instance, ctx):
        line_num = ctx.start.line if hasattr(ctx, 'start') else 0
        self.paused.emit(interpreter_instance, ctx, line_num)
        self.step_event.clear()
        self.step_event.wait()

    def request_input(self, prompt):
        time.sleep (0.1)
        self.input_requested.emit(prompt)
        self.input_event.clear()
        self.input_event.wait() 
        return self.input_value 
    
class InteractiveConsole(QPlainTextEdit):
    input_submitted = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.waiting_for_input = False
        self.input_start_pos = 0

    # Called when the interpreter hits an INPUT statement.
    def prompt_for_input(self, prompt_text):
        self.setReadOnly(False)
        
        # Move cursor to the very end
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.setTextCursor(cursor)
        
        # Insert the prompt and lock the starting position
        self.insertPlainText(prompt_text)
        self.input_start_pos = self.textCursor().position()
        self.waiting_for_input = True
        self.setFocus()

    def keyPressEvent(self, event):
        # 1. If we aren't waiting for input, act mostly read-only 
        if not self.waiting_for_input:
            if event.key() == Qt.Key.Key_C and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                super().keyPressEvent(event)
            return

        cursor = self.textCursor()

        # 2. Block Backspace and Left Arrow from crossing into the prompt/output
        if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Left):
            if cursor.position() <= self.input_start_pos:
                return # Block the keypress

        # 3. Handle 'Enter' to submit the input
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Grab everything from the start position to the end of the line
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.setPosition(self.input_start_pos, cursor.MoveMode.KeepAnchor)
            input_text = cursor.selectedText()
            
            # Lock the console back down
            self.waiting_for_input = False
            self.setReadOnly(True)
            cursor.movePosition(cursor.MoveOperation.End) 
            self.setTextCursor(cursor)
            self.insertPlainText("\n")
            
            self.input_submitted.emit(input_text)
            return

        # 4. For all standard typing, let the normal behavior happen
        super().keyPressEvent(event)

# A small custom widget to hold the line numbers.
class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)

# An upgraded QPlainTextEdit that includes a line number gutter.
class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.line_number_area = LineNumberArea(self)

        # Connect signals to automatically resize and scroll the line number area
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        
        # Initialize margin size
        self.update_line_number_area_width(0)

    def line_number_area_width(self):
        # Calculate how much space we need based on the number of digits
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1
        
        # Add a little padding (3px) + the width of the digits
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space + 10 # Add 10 for a nice right-margin breathing room

    def update_line_number_area_width(self, _):
        # Set the left margin of the text editor to make room for the numbers
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        # Ensure the line number area stretches from top to bottom
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        
        # Paint the background of the line number gutter
        painter.fillRect(event.rect(), QColor("#2b2b2b")) # Dark grey background

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        # Iterate through all visible lines and draw their numbers
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                
                painter.setPen(QColor("#888888")) # Light grey text
                painter.drawText(0, top, self.line_number_area.width() - 5, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

class C4ChineseIDE(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Henhao IDE: The C4Chinese IDE & Debugger")
        self.setGeometry(100, 100, 1200, 800)
        
        self.current_file = None
        self.init_ui()
        
        # Redirect standard output to our console widget
        sys.stdout = EmittingStream(textWritten=self.append_to_console)
        # Redirect standard error as well, just in case Python throws a hard crash
        sys.stderr = EmittingStream(textWritten=self.append_to_console)

    def init_ui(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        btn_run = QAction("▶ Run", self)
        btn_run.triggered.connect(self.run_code)
        toolbar.addAction(btn_run)
        
        btn_debug = QAction("🐞 Debug", self)
        btn_debug.triggered.connect(self.debug_code)
        toolbar.addAction(btn_debug)

        # Add this right after the btn_debug action in init_ui()
        self.btn_step = QAction("⏭ Step", self)
        self.btn_step.triggered.connect(self.step_debugger)
        self.btn_step.setEnabled(False) # Disabled until we are actually debugging
        toolbar.addAction(self.btn_step)
        
        toolbar.addSeparator()

        btn_open = QAction("📂 Open", self)
        btn_open.triggered.connect(self.open_file)
        toolbar.addAction(btn_open)
        
        btn_save = QAction("💾 Save", self)
        btn_save.triggered.connect(self.save_file)
        toolbar.addAction(btn_save)
        
        btn_save_as = QAction("💾 Save As...", self)
        btn_save_as.triggered.connect(self.save_as_file)
        toolbar.addAction(btn_save_as)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        left_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Code Editor
        self.editor = CodeEditor()
        font = QFont("Consolas", 12)
        self.editor.setFont(font)
        self.editor.setPlaceholderText("Write your C4Chinese code here...")
        left_splitter.addWidget(self.editor)
        
        # Console Output
        self.console = InteractiveConsole()
        self.console.setFont(font)
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: #1e1e1e; color: #00ff00;")
        self.console.input_submitted.connect(self.submit_input)
        left_splitter.addWidget(self.console)
        
        left_splitter.setSizes([600, 200]) 
        
        # Debug Tabs
        self.debug_tabs = QTabWidget()
        
        self.env_table = QTableWidget(0, 4)
        self.env_table.setHorizontalHeaderLabels(["Scope", "Variable", "Address", "Value"])
        self.debug_tabs.addTab(self.env_table, "Environment Table")

        self.call_stack_table = QTableWidget(0, 2)
        self.call_stack_table.setHorizontalHeaderLabels(["Depth", "Function Call"])
        self.call_stack_table.horizontalHeader().setStretchLastSection(True)
        self.debug_tabs.addTab(self.call_stack_table, "Call Stack")
        
        self.sym_table = QTableWidget(0, 4)
        self.sym_table.setHorizontalHeaderLabels(["Name", "Type", "Category", "RHS Count"])
        self.debug_tabs.addTab(self.sym_table, "Symbol Table")
        
        self.parse_tree = QTreeWidget()
        self.parse_tree.setHeaderLabel("Abstract Syntax Tree (Original)")
        self.debug_tabs.addTab(self.parse_tree, "Parse Tree")

        self.optimized_parse_tree = QTreeWidget()
        self.optimized_parse_tree.setHeaderLabel("Abstract Syntax Tree (Optimized)")
        self.debug_tabs.addTab(self.optimized_parse_tree, "Optimized Tree")
        
        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(self.debug_tabs)
        main_splitter.setSizes([800, 400]) 
        
        self.setCentralWidget(main_splitter)

    # --- UI LOGIC ---
    def append_to_console(self, text):
        cursor = self.console.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        
        # Regex to find ANSI escape codes: \x1b[...m (Note: \033 is \x1b in regex)
        ansi_regex = re.compile(r'\x1b\[([0-9;]*)m')
        
        # Setup the default formatting
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#00ff00")) # Default console green
        fmt.setFontWeight(QFont.Weight.Normal)
        
        last_end = 0
        
        # Search through the incoming text for color codes
        for match in ansi_regex.finditer(text):
            # 1. Insert the normal text BEFORE the color code
            plain_text = text[last_end:match.start()]
            if plain_text:
                cursor.insertText(plain_text, fmt)
            
            # 2. Change the 'paint brush' color based on the code we found
            code = match.group(1)
            if code == '0':
                fmt.setForeground(QColor("#00ff00")) # Reset
                fmt.setFontWeight(QFont.Weight.Normal)
            elif code == '1':
                fmt.setFontWeight(QFont.Weight.Bold) # Bold
            elif code == '91':
                fmt.setForeground(QColor("#ff5555")) # Red
            elif code == '92':
                fmt.setForeground(QColor("#55ff55")) # Green
            elif code == '93':
                fmt.setForeground(QColor("#ffff55")) # Yellow
            elif code == '94':
                fmt.setForeground(QColor("#5555ff")) # Blue
            elif code == '95':
                fmt.setForeground(QColor("#ff55ff")) # Magenta
            elif code == '96':
                fmt.setForeground(QColor("#55ffff")) # Cyan
                
            last_end = match.end()
            
        # 3. Insert any remaining text after the final color code
        remaining_text = text[last_end:]
        if remaining_text:
            cursor.insertText(remaining_text, fmt)
            
        self.console.setTextCursor(cursor)

    # Triggered by the background worker when it needs data.
    def prompt_for_input(self, prompt_text):
        # Pass the prompt directly to our smart console
        self.console.prompt_for_input(prompt_text)

    # Triggered by the console when the user hits Enter.
    def submit_input(self, text):
        # Send the string to the waiting background thread to resume execution
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.input_value = text
            self.worker.input_event.set()
    
    def open_file(self):
        options = QFileDialog.Option.DontUseNativeDialog
        # Use the exact same file filters used for saving
        filename, _ = QFileDialog.getOpenFileName(
            self, 
            "Open File", 
            "", 
            "C4Chinese Files (*.c4);;All Files (*)", 
            options=options
        )
        
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Load the code into the editor
                self.editor.setPlainText(content)
                
                # Update the current file tracker
                self.current_file = filename
                print(f"Opened file: {self.current_file}")
                
            except Exception as e:
                print(f"\n[IDE Error] Failed to open file: {e}")

    def save_file(self):
        if self.current_file:
            with open(self.current_file, 'w', encoding='utf-8') as f:
                f.write(self.editor.toPlainText())
            print(f"Saved to {self.current_file}")
        else:
            self.save_as_file()

    def save_as_file(self):
        options = QFileDialog.Option.DontUseNativeDialog
        filename, _ = QFileDialog.getSaveFileName(self, "Save File", "", "C4Chinese Files (*.c4);;All Files (*)", options=options)
        if filename:
            self.current_file = filename
            self.save_file()

    # --- COMPILER INTEGRATION ---
    def run_code(self):
        # 1. Clear the console for a fresh run...
        self.console.clear()
        print("Compiling and Running...\n" + "="*40 + "\n")
        
        # 2. Save the current text to a temporary file...
        code = self.editor.toPlainText()
        temp_file = "temp_run.c4"
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(code)
            
        # 3. Run the pipeline...
        try:
            parse_result = parse(temp_file, p=False)
            
            if parse_result is None:
                print("\nCompilation stopped due to parser/semantic errors.")
                return
                
            tree, parser, symbol_table = parse_result
            self.populate_symbol_table(symbol_table)
            self.populate_parse_tree(tree, parser, self.parse_tree)
            
            optimized_tree = optimize(tree, parser, symbol_table)
            self.populate_parse_tree(optimized_tree, parser, self.optimized_parse_tree)
            interpreter = InterpreterVisitor(symbol_table, interactive_debug=False, print_trace=False)
            
            self.worker = InterpreterWorker(interpreter, optimized_tree)
            self.worker.input_requested.connect(self.prompt_for_input)
            self.worker.finished.connect(self.on_run_finished) 
            self.worker.error.connect(self.on_debugger_error)
            
            self.worker.start() 
                
        except Exception as e:
            print(f"\nRuntime Error: {str(e)}")
            print("\n--- Python Traceback ---")
            traceback.print_exc()
    def on_run_finished(self, exit_code):
        if hasattr(self, 'worker'):
            interpreter = self.worker.interpreter
            self.update_dynamic_tables(interpreter)
        print(f"\n" + "="*40 + f"\nProgram exited with code: {exit_code}")

    def debug_code(self):
        self.console.clear()
        print("Starting Debug Mode...\n" + "="*40)
        
        code = self.editor.toPlainText()
        temp_file = "temp_debug.c4"
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(code)
            
        try:
            parse_result = parse(temp_file, False)
            if parse_result is None:
                print("Compilation stopped due to errors.")
                return
                
            tree, parser, symbol_table = parse_result

            self.populate_symbol_table(symbol_table)
            self.populate_parse_tree(tree, parser, self.parse_tree)
            optimized_tree = optimize(tree, parser, symbol_table)
            self.populate_parse_tree(optimized_tree, parser, self.optimized_parse_tree)

            # Initialize with interactive_debug=True
            interpreter = InterpreterVisitor(symbol_table, interactive_debug=True, print_trace=False)
            
            # Setup and start the background thread
            self.worker = InterpreterWorker(interpreter, optimized_tree)
            self.worker.paused.connect(self.on_debugger_paused)
            self.worker.finished.connect(self.on_debugger_finished)
            self.worker.error.connect(self.on_debugger_error)
            self.worker.input_requested.connect(self.prompt_for_input)
            
            self.btn_step.setEnabled(True)
            self.worker.start()
            
        except Exception as e:
            print(f"Failed to start debugger: {e}")

    def step_debugger(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.step_event.set()

    def on_debugger_finished(self, exit_code):
        print(f"\nDebug session finished with code: {exit_code}")
        self.btn_step.setEnabled(False)
        
    def on_debugger_error(self, err_msg):
        print(f"\nRuntime Error during debug: {err_msg}")
        self.btn_step.setEnabled(False)

    # Triggered every time the background InterpreterWorker hits a statement
    # while interactive_debug is enabled.
    def on_debugger_paused(self, interpreter, ctx, line_num):
        
        # 1. Provide feedback in the console
        print(f"Debugger paused at line {line_num}...")
        
        # 2. Update all visual tabs (Environment, Call Stack, etc.)
        # We delegate the heavy lifting to update_dynamic_tables to avoid 
        # redundant code between 'Run' and 'Debug' modes.
        self.update_dynamic_tables(interpreter)
        
        self.highlight_current_line(line_num)

    # ==========================================
    # --- TABLE & TREE POPULATION METHODS ---
    # ==========================================

    # Recursively builds the visual AST for the specified Tree Tab
    def populate_parse_tree(self, tree, parser, target_widget, parent_item=None):
        if parent_item is None:
            target_widget.clear() # Clear old tree on new run
            
        if isinstance(tree, TerminalNodeImpl):
            token = tree.getSymbol()
            token_type_idx = token.type
            token_name = parser.symbolicNames[token_type_idx] if token_type_idx != -1 else "EOF"
            text = f"{token_name} ('{token.text.strip()}')"
            item = QTreeWidgetItem([text])
        else:
            rule_index = tree.getRuleIndex()
            rule_name = parser.ruleNames[rule_index]
            item = QTreeWidgetItem([rule_name])
            
        if parent_item:
            parent_item.addChild(item)
        else:
            target_widget.addTopLevelItem(item)
            
        # Recurse children
        for i in range(tree.getChildCount()):
            self.populate_parse_tree(tree.getChild(i), parser, target_widget, item)
            
        if parent_item is None:
            target_widget.expandAll()

    # Builds the static Symbol Table
    def populate_symbol_table(self, symbol_table):
        self.sym_table.setRowCount(0)
        self._add_scope_to_sym_table(symbol_table.global_scope, "Global")

    def _add_scope_to_sym_table(self, scope, scope_name):
        # 1. Add symbols in current scope
        for name, sym in scope.symbols.items():
            row = self.sym_table.rowCount()
            self.sym_table.insertRow(row)
            
            sym_type = getattr(sym, 'type', 'Unknown')
            if hasattr(sym_type, 'name'): sym_type = sym_type.name
            sym_cat = type(sym).__name__.replace('Symbol', '') # e.g. 'VarSymbol' -> 'Var'
            
            self.sym_table.setItem(row, 0, QTableWidgetItem(name))
            self.sym_table.setItem(row, 1, QTableWidgetItem(str(sym_type)))
            self.sym_table.setItem(row, 2, QTableWidgetItem(sym_cat))
            self.sym_table.setItem(row, 3, QTableWidgetItem(scope_name))
            
            # If the symbol is a function/struct, recurse into its internal symbols
            if hasattr(sym, 'symbols'):
                self._add_scope_to_sym_table(sym, f"{scope_name}.{name}")
                
        # 2. Add symbols from nested if/while blocks
        if hasattr(scope, 'blocks'):
            for i, block in enumerate(scope.blocks):
                self._add_scope_to_sym_table(block, f"{scope_name}.Block{i}")

    # Updates Environment & Call Stack using live memory and recursive helpers.
    def update_dynamic_tables(self, interpreter):
        try:
            # --- 1. POPULATE ENVIRONMENT TABLE ---
            self.env_table.setRowCount(0)
            
            # Use the live environment to accurately resolve nested struct/array memory
            current = interpreter.current_env
            
            # Calculate total depth for labeling...
            total_depth = 0
            temp = current
            while temp and temp.parent:
                total_depth += 1
                temp = temp.parent

            while current is not None:
                scope_label = "Global" if current.parent is None else f"Local (Scope {total_depth})"
                
                if current.variables:
                    for name, address in current.variables.items():
                        var_sym = interpreter.symbol_table.resolve(name)
                        
                        # Get the base type (handles both normal variables and direct types)
                        var_type = getattr(var_sym, 'type', var_sym)
                        type_name = type(var_type).__name__

                        if type_name == "StructTypeSymbol":
                            self._insert_env_row(scope_label, name, address, "<Struct>")
                            self._add_struct_fields_to_table(interpreter, name, address, var_type, scope_label, 1)
                        elif type_name == "ArrayType":
                            arr_size = getattr(var_type, 'size', '?')
                            self._insert_env_row(scope_label, name, address, f"<Array[{arr_size}]>")
                            self._add_array_elements_to_table(interpreter, name, address, var_type, scope_label, 1)
                        else:
                            self._insert_value_row(interpreter, scope_label, name, address)

                current = current.parent
                total_depth -= 1

            # --- 2. POPULATE CALL STACK TABLE ---
            self.call_stack_table.setRowCount(0)
            
            stack_data = getattr(interpreter, 'final_call_stack', None) or getattr(interpreter, 'call_stack', [])
            
            for i, frame in enumerate(reversed(stack_data)):
                idx = self.call_stack_table.rowCount()
                self.call_stack_table.insertRow(idx)
                self.call_stack_table.setItem(idx, 0, QTableWidgetItem(f"Level {len(stack_data) - i}"))
                self.call_stack_table.setItem(idx, 1, QTableWidgetItem(str(frame)))
                
        except Exception as e:
            print(f"\n[IDE Error] Tables failed to update: {e}")

    # Helper to quickly append a new row to the Environment Table.
    def _insert_env_row(self, scope, name, address, value):
        row_idx = self.env_table.rowCount()
        self.env_table.insertRow(row_idx)
        self.env_table.setItem(row_idx, 0, QTableWidgetItem(str(scope)))
        self.env_table.setItem(row_idx, 1, QTableWidgetItem(str(name)))
        self.env_table.setItem(row_idx, 2, QTableWidgetItem(str(address)))
        self.env_table.setItem(row_idx, 3, QTableWidgetItem(str(value)))

    # Helper to read a memory address and insert it safely.
    def _insert_value_row(self, interpreter, scope_label, name, address):
        try:
            val = interpreter.memory.read(address)
            val_str = str(val) if val is not None else "null"
        except Exception:
            val_str = "Mem Error"
        self._insert_env_row(scope_label, name, address, val_str)

    # Recursively breaks down struct fields and adds them to the IDE table.
    def _add_struct_fields_to_table(self, interpreter, base_name, base_address, struct_type, scope_label, indent_level):
        offsets = TypeManager.get_struct_offsets(struct_type)
        indent_str = "  " * indent_level + "↳ "
        
        for field_name, offset in offsets.items():
            field_addr = base_address + offset
            full_name = f"{indent_str}{base_name}.{field_name}" 
            clean_base_name = f"{base_name}.{field_name}"
            
            member_sym = struct_type.symbols.get(field_name)
            field_type = member_sym.type if hasattr(member_sym, 'type') else member_sym
            type_name = type(field_type).__name__
            
            if type_name == "StructTypeSymbol":
                self._insert_env_row(scope_label, full_name, field_addr, "<Struct>")
                self._add_struct_fields_to_table(interpreter, clean_base_name, field_addr, field_type, scope_label, indent_level + 1)
            elif type_name == "ArrayType":
                arr_size = getattr(field_type, 'size', '?')
                self._insert_env_row(scope_label, full_name, field_addr, f"<Array[{arr_size}]>")
                self._add_array_elements_to_table(interpreter, clean_base_name, field_addr, field_type, scope_label, indent_level + 1)
            else:
                self._insert_value_row(interpreter, scope_label, full_name, field_addr)

    # Recursively breaks down array elements and adds them to the IDE table.
    def _add_array_elements_to_table(self, interpreter, base_name, base_address, array_type, scope_label, indent_level):
        element_type = array_type.base_type
        element_size = TypeManager.get_size(element_type)
        indent_str = "  " * indent_level + "↳ "
        
        for i in range(array_type.size):
            elem_addr = base_address + (i * element_size)
            full_name = f"{indent_str}{base_name}[{i}]"
            clean_base_name = f"{base_name}[{i}]"
            
            type_name = type(element_type).__name__
            
            if type_name == "StructTypeSymbol":
                self._insert_env_row(scope_label, full_name, elem_addr, "<Struct>")
                self._add_struct_fields_to_table(interpreter, clean_base_name, elem_addr, element_type, scope_label, indent_level + 1)
            elif type_name == "ArrayType":
                arr_size = getattr(element_type, 'size', '?')
                self._insert_env_row(scope_label, full_name, elem_addr, f"<Array[{arr_size}]>")
                self._add_array_elements_to_table(interpreter, clean_base_name, elem_addr, element_type, scope_label, indent_level + 1)
            else:
                self._insert_value_row(interpreter, scope_label, full_name, elem_addr)
    def highlight_current_line(self, line_num):
        if not isinstance(line_num, int) or line_num <= 0:
            self.editor.setExtraSelections([])
            return
            
        selection = QTextEdit.ExtraSelection()
        line_color = QColor(100, 150, 255, 60) 
        selection.format.setBackground(line_color)
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        
        cursor = self.editor.textCursor()
        cursor.setPosition(0)

        # Move cursor down (0-indexed, so we subtract 1)
        cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, line_num - 1)
        
        selection.cursor = cursor
        self.editor.setExtraSelections([selection])

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ide = C4ChineseIDE()
    ide.show()
    sys.exit(app.exec())