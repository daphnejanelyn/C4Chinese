from C4ChineseParserVisitor import C4ChineseParserVisitor
from C4ChineseParser import C4ChineseParser
from CheckingVisitor import PrimitiveTypeSymbol, ArrayType, StructTypeSymbol, PointerType, VarSymbol, TypedefSymbol
class Memory:
    def __init__(self):
        # Using a dictionary to simulate memory to easily use integer 
        # addresses without pre-allocating a massive array...
        self.heap = {} 
        self.next_address = 1000 # Start at an arbitrary offset for readability...
        
    def allocate(self, size: int) -> int:
        """Allocates contiguous blocks of memory and returns the starting address."""
        start_address = self.next_address
        for i in range(size):
            self.heap[self.next_address + i] = None # Initialize with null/None
        self.next_address += size
        return start_address

    def read(self, address: int):
        if address not in self.heap:
            raise Exception(f"Runtime Error: Segmentation fault. Unallocated read at {address}")
        return self.heap[address]

    def write(self, address: int, value):
        if address not in self.heap:
            raise Exception(f"Runtime Error: Segmentation fault. Unallocated write at {address}")
        self.heap[address] = value

class Environment:
    def __init__(self, parent=None, interactive_debug=False, print_trace=True, debug_hook=None):
        self.parent = parent
        self.variables = {} # Maps name -> memory address
        self.interactive_debug = interactive_debug
        self.print_trace = print_trace
        self.debug_hook = debug_hook

    def define(self, name: str, address: int):
        # Always defines in the current local scope...
        self.variables[name] = address

    def resolve_address(self, name: str) -> int:
        # 1. Check current scope...
        if name in self.variables:
            return self.variables[name]
        # 2. Check parent scope recursively...
        elif self.parent is not None:
            return self.parent.resolve_address(name)
        # 3. Crash if undefined...
        else:
            raise Exception(f"Runtime Error: Variable '{name}' not found in environment.")
        
class BreakException(Exception):
    pass

class ContinueException(Exception):
    pass

class ReturnException(Exception):
    def __init__(self, value):
        self.value = value

class InterpreterVisitor(C4ChineseParserVisitor):
    def __init__(self, symbol_table, interactive_debug=False, print_trace=True):
        self.memory = Memory()
        self.global_env = Environment(parent=None)
        self.current_env = self.global_env
        self.symbol_table = symbol_table # Passed in from the type checker
        self.function_bodies = {} # Maps function names to their parse tree contexts for later execution
        self.debug_trace = not interactive_debug
        self.print_trace = print_trace
        self.symbol_table.reset_all_block_indices()
        self.call_stack = []
        self.interactive_debug = interactive_debug

    def get_environment_data(self):
        """Extracts the environment into a safe, thread-friendly list of tuples."""
        data = []
        current = self.current_env
        
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
                    # Read the memory value safely...
                    try:
                        val = self.memory.read(address)
                        val_str = str(val) if val is not None else "null"
                    except Exception:
                        val_str = "Mem Error"

                    # Prettify structs and arrays slightly...
                    try:
                        var_sym = self.symbol_table.resolve(name)
                        if var_sym and hasattr(var_sym, 'type'):
                            type_name = type(var_sym.type).__name__
                            if type_name == "StructTypeSymbol":
                                val_str = "<Struct>"
                            elif type_name == "ArrayType":
                                arr_size = getattr(var_sym.type, 'size', '?')
                                val_str = f"<Array[{arr_size}]>"
                    except Exception:
                        pass

                    data.append((scope_label, name, str(address), val_str))

            current = current.parent
            total_depth -= 1

        return data

    def trace(self, message: str):
        if self.debug_trace and self.print_trace:
            print(f"\033[90m[TRACE] {message}\033[0m")

    def enter_scope(self):
        # Pushes a new local scope...
        new_env = Environment(parent=self.current_env)
        self.current_env = new_env

    def exit_scope(self):
        # Pops the current local scope...
        if self.current_env.parent is not None:
            self.current_env = self.current_env.parent
        else:
            raise Exception("Runtime Error: Cannot exit global scope.")

    def visitStatBlock(self, ctx: C4ChineseParser.StatBlockContext):
        self.trace("Entering new block {}")
        
        # 1. Push the scopes...
        self.symbol_table.enter_next_block()
        self.enter_scope()
        
        current_block_scope = self.symbol_table.current_scope
        
        try:
            # 2. Execute the block...
            for statement in ctx.statement():
                self.visit(statement)
                
        finally:
            # 3. Even if a BreakException, ContinueException, or ReturnException 
            # is thrown, this will always execute and cleanly pop the scopes...
            current_block_scope.reset_block_index()
            
            self.exit_scope()
            self.symbol_table.exit_scope()
            self.trace("Exiting block {}")
            
        return None
    
    def visitFuncContent(self, ctx: C4ChineseParser.FuncContentContext):
        if ctx.children:
            for child in ctx.children:
                self.visit(child)
        return None    

    def visitFuncCall(self, ctx: C4ChineseParser.FuncCallContext):
        func_name = ctx.idWrapper().getText()
        
        # 1. Evaluate arguments BEFORE changing the environment...
        arg_values = []
        if ctx.argList():
            arg_values = self.visit(ctx.argList())
            
        func_sym = self.symbol_table.resolve(func_name)
        func_body_ctx = self.function_bodies[func_name]
        
        # 2. Save the caller's environment AND symbol table scope...
        previous_env = self.current_env
        previous_scope = self.symbol_table.current_scope
        
        # 3. Create a new runtime environment...
        self.current_env = Environment(parent=self.global_env)
        
        # 4. Direct Jump: Sync the Symbol Table directly to the function scope...
        self.symbol_table.current_scope = func_sym 
        self.symbol_table.current_scope.reset_block_index() 
        param_names = [param.name for param in func_sym.parameters]
        param_values_str = ", ".join(f"{name}={val}" for name, val in zip(param_names, arg_values))
        self.call_stack.append(f"{func_name}({param_values_str})" )
        
        # 5. Allocate memory for parameters...
        for i, param_sym in enumerate(func_sym.parameters):
            param_name = param_sym.name
            size = TypeManager.get_size(param_sym.type)
            base_address = self.memory.allocate(size)
            self.current_env.define(param_name, base_address)
            self.memory.write(base_address, arg_values[i])
            
        # 6. Execute the function body...
        final_return_value = None
        try:
            self.visit(func_body_ctx)
        except ReturnException as ret:
            final_return_value = ret.value
        finally:
            # 7. ALWAYS restore both scopes...
            self.current_env = previous_env
            self.symbol_table.current_scope = previous_scope
            self.call_stack.pop()
        
        return final_return_value

    def visitArgList(self, ctx: C4ChineseParser.ArgListContext):
        # Loop through every expression passed into the function call,
        # evaluate it, and return the final values as a list...
        return [self.visit(expr) for expr in ctx.expression()]

    def visitVarDecl(self, ctx: C4ChineseParser.VarDeclContext):
        name = ctx.idWrapper().getText()
        self.trace(f"Declaring variable '{name}'")
        
        # 1. Get the pre-calculated type from the Symbol Table...
        var_sym = self.symbol_table.resolve(name) 
        if var_sym is None:
            raise Exception(f"Interpreter desync: Could not find '{name}' in SymbolTable scope.")
        
        # 2. Calculate its size...
        size = TypeManager.get_size(var_sym.type)
        
        # 3. Allocate that much contiguous memory...
        base_address = self.memory.allocate(size)
        
        # 4. Define it in the current runtime scope...
        self.current_env.define(name, base_address)
        
        # 5. Handle the optional assignment...
        if ctx.expression():
            val = self.visit(ctx.expression())
            self.trace(f"Assigning initial value {val} to {name} at address {base_address}")

            # Flatten multi-dimensional arrays into 1D memory
            if isinstance(val, list):
                
                # Helper to recursively flatten any nested list
                def flatten(nested_list):
                    flat = []
                    for item in nested_list:
                        if isinstance(item, list):
                            flat.extend(flatten(item))
                        else:
                            flat.append(item)
                    return flat
                    
                flat_val = flatten(val)
                for i, item_val in enumerate(flat_val):
                    self.memory.write(base_address + i, item_val)
                    
            else:
                self.memory.write(base_address, val)
                
        return None
    
    def visitArrayInitExp(self, ctx: C4ChineseParser.ArrayInitExpContext):
        # If the array is initialized with values (e.g., {1, 2, 3})...
        if ctx.expList():
            # This will return a Python list of the evaluated numbers...
            return self.visit(ctx.expList())
            
        # If it's an empty initialization (e.g., {})...
        return []

    def visitExpList(self, ctx: C4ChineseParser.ExpListContext):
        # Loop through every expression inside the curly braces, 
        # evaluate it, and return the final values as a Python list...
        return [self.visit(expr) for expr in ctx.expression()]
    
    def visitConstDecl(self, ctx: C4ChineseParser.ConstDeclContext):
        # Grab the raw text bypass just like we did for variables...
        name = ctx.idWrapper().getText()
        self.trace(f"Declaring constant: {name}")
        
        # 1. Get the pre-calculated type from the Symbol Table...
        var_sym = self.symbol_table.resolve(name) 
        if var_sym is None:
            raise Exception(f"Interpreter desync: Could not find '{name}' in SymbolTable scope.")
            
        # 2. Calculate its size using TypeManager...
        size = TypeManager.get_size(var_sym.type)
        
        # 3. Allocate that much contiguous memory...
        base_address = self.memory.allocate(size)
        
        # 4. Define it in the current runtime scope...
        self.current_env.define(name, base_address)
        
        # 5. Evaluate the mandatory assignment and write to memory...
        if ctx.expression():
            val = self.visit(ctx.expression())
            self.trace(f"Assigning constant value {val} to {name} at address {base_address}")
            
            # Flatten multi-dimensional arrays into 1D memory
            if isinstance(val, list):
                
                def flatten(nested_list):
                    flat = []
                    for item in nested_list:
                        if isinstance(item, list):
                            flat.extend(flatten(item))
                        else:
                            flat.append(item)
                    return flat
                    
                flat_val = flatten(val)
                for i, item_val in enumerate(flat_val):
                    self.memory.write(base_address + i, item_val)
                    
            else:
                self.memory.write(base_address, val)
                
        return None

    def visitRecordDecl(self, ctx: C4ChineseParser.RecordDeclContext):
        # Struct definitions are just blueprints. We do not allocate memory for them
        # until a user actually declares a variable of this struct type...

        # By returning None here, we stop the visitor from going inside and 
        # accidentally executing the blueprint's fields...
        
        struct_name = ctx.idWrapper().getText() if ctx.idWrapper() else "anonymous"
        self.trace(f"Skipping struct blueprint execution for: {struct_name}")
        return None

    def visitTypedefItem(self, ctx: C4ChineseParser.TypedefItemContext):
        # Typedefs are also just compile-time type aliases...
        # They don't require any runtime memory or execution...
        return None

    def visitAssignStat(self, ctx: C4ChineseParser.AssignStatContext):
        # 1. Evaluate the right side of the equals sign...
        value = self.visit(ctx.expression())

        assignable = ctx.assignableVal()
        
        # 2. Figure out the memory address of the left side
        # (ctx.assignableVal() contains either a refVal or deRefVal)...
        if assignable.refVal():
            target_address = self.get_lvalue_address(ctx.assignableVal().refVal())

        elif assignable.deRefVal():
            target_address = self.get_pointer_target(ctx.assignableVal().deRefVal())
            
        # 3. Write it to memory...
        self.memory.write(target_address, value)
        return None
    
    def visitRefVal(self, ctx: C4ChineseParser.RefValContext):
        # Address-of operator (&) check
        # If the user asks for &arr[5], we return the integer address directly...
        if getattr(self, 'is_address_of', False): 
            return self.get_lvalue_address(ctx)
            
        # Otherwise, find the address and read the value stored there...
        target_address = self.get_lvalue_address(ctx)
        return self.memory.read(target_address)

    def visitDeRefVal(self, ctx: C4ChineseParser.DeRefValContext):
        # To evaluate the pointer as an expression, we find where it points, 
        # and then read the value from that final memory address...
        target_address = self.get_pointer_target(ctx)
        return self.memory.read(target_address)
    
    def visitNumExp(self, ctx: C4ChineseParser.NumExpContext):
        # 1. Evaluate the very first operand in the chain...
        result = self.visit(ctx.numExp1(0))
        
        # 2. Loop through the remaining operands and operators...
        for i in range(1, len(ctx.numExp1())):
            next_val = self.visit(ctx.numExp1(i))
            op_type = ctx.getChild(2 * i - 1).getSymbol().type
            
            # --- SAFE STRING CONCATENATION ---
            if isinstance(result, str) and isinstance(next_val, str) and op_type == C4ChineseParser.ADD:
                result += next_val
            else:
                # --- C-STYLE CHAR MATH FALLBACK ---
                if isinstance(result, str) and len(result) == 1: result = ord(result)
                if isinstance(next_val, str) and len(next_val) == 1: next_val = ord(next_val)

                if op_type == C4ChineseParser.ADD:
                    result += next_val
                elif op_type == C4ChineseParser.SUB:
                    result -= next_val
                
        return result

    def visitNumExp1(self, ctx: C4ChineseParser.NumExp1Context):
        result = self.visit(ctx.numExp2(0))
        
        for i in range(1, len(ctx.numExp2())):
            next_val = self.visit(ctx.numExp2(i))
            op_type = ctx.getChild(2 * i - 1).getSymbol().type
            
            if op_type == C4ChineseParser.MULT:
                result *= next_val
            elif op_type == C4ChineseParser.DIV:
                if next_val == 0:
                    raise Exception("Runtime Error: Division by zero.")
                
                # C-style integer division if both are ints...
                if isinstance(result, int) and isinstance(next_val, int):
                    result //= next_val
                else:
                    result /= next_val
            elif op_type == C4ChineseParser.MOD:
                if next_val == 0:
                    raise Exception("Runtime Error: Modulo by zero.")
                result %= next_val
                
        return result
    
    def visitNumExp2(self, ctx: C4ChineseParser.NumExp2Context):

        # --- PRE / POST INCREMENT ---
        if ctx.INC() or ctx.DEC():
            return self._handle_inc_dec(ctx)
        
        # --- PARENTHESES ---
        if ctx.numExp():
            return self.visit(ctx.numExp())
            
        # --- LITERALS ---
        if ctx.LT_INT():
            return int(ctx.LT_INT().getText())
        if ctx.floatWrapper():
            return float(ctx.floatWrapper().getText())
        if ctx.charWrapper():
            # In C-like languages, chars are treated as ASCII integers during math
            return ctx.charWrapper().getText().strip("'")
            
        # --- VARIABLES ---
        if ctx.numRef():
            target_address = self.get_lvalue_address(ctx.numRef().refVal())
            return self.memory.read(target_address)
            
        # --- POINTERS ---
        if ctx.REF(): 
            return self.get_lvalue_address(ctx.refVal())
            
        if ctx.deRefVal():
            target_address = self.get_pointer_target(ctx.deRefVal())
            return self.memory.read(target_address)
            
        # --- FUNCTIONS ---
        if ctx.funcCall():
            return self.visit(ctx.funcCall())
            
        return None
    
    def visitStrExp(self, ctx: C4ChineseParser.StrExpContext):
        # 1. Evaluate the first string part...
        result = str(self.visit(ctx.strBase(0)))
        
        # 2. Handle concatenation (ADD) if there are multiple parts (e.g., "Hello " + name)...
        for i in range(1, len(ctx.strBase())):
            next_val = self.visit(ctx.strBase(i))
            result += str(next_val)
            
        return result

    def visitStrBase(self, ctx: C4ChineseParser.StrBaseContext):
        # --- LITERALS ---
        if ctx.stringWrapper():
            # Strip the surrounding quotes from the raw text...
            return ctx.stringWrapper().getText().strip('"')
            
        if ctx.charWrapper():
            return ctx.charWrapper().getText().strip("'")
            
        # --- VARIABLES ---
        if ctx.strVal():
            target_address = self.get_lvalue_address(ctx.strVal().refVal())
            return self.memory.read(target_address)
            
        # --- POINTERS ---
        if ctx.deRefVal():
            target_address = self.get_pointer_target(ctx.deRefVal())
            return self.memory.read(target_address)
            
        # --- FUNCTIONS ---
        if ctx.funcCall():
            return self.visit(ctx.funcCall())
        
        if ctx.strExp():
            return self.visit(ctx.strExp())
            
        return None
    
    def visitBoolExp(self, ctx: C4ChineseParser.BoolExpContext):
        # 1. Evaluate the first condition...
        result = self.visit(ctx.boolExp1(0))
        
        # 2. Check the rest of the chain...
        for i in range(1, len(ctx.boolExp1())):
            # SHORT-CIRCUIT: If it's already True, an OR statement will always be True...
            if result is True:
                return True
                
            # Otherwise, evaluate the next condition...
            next_val = self.visit(ctx.boolExp1(i))
            
            # The operator is located between operands...
            op_type = ctx.getChild(2 * i - 1).getSymbol().type
            if op_type == C4ChineseParser.OR:
                result = result or next_val
                
        return bool(result)
    
    def visitBoolExp1(self, ctx: C4ChineseParser.BoolExp1Context):
        result = self.visit(ctx.boolExp2(0))
        
        for i in range(1, len(ctx.boolExp2())):
            # SHORT-CIRCUIT: If it's already False, an AND statement will always be False...
            if result is False:
                return False
                
            next_val = self.visit(ctx.boolExp2(i))
            
            op_type = ctx.getChild(2 * i - 1).getSymbol().type
            if op_type == C4ChineseParser.AND:
                result = result and next_val
                
        return bool(result)
    
    def visitBoolExp2(self, ctx: C4ChineseParser.BoolExp2Context):
        # Handle the chained boolean equality (e.g., a == b == c)...
        if ctx.boolExp3():
            result = self.visit(ctx.boolExp3(0))
            for i in range(1, len(ctx.boolExp3())):
                next_val = self.visit(ctx.boolExp3(i))
                op_type = ctx.getChild(2 * i - 1).getSymbol().type
                
                if op_type == C4ChineseParser.EQ:
                    result = (result == next_val)
                elif op_type == C4ChineseParser.NEQ:
                    result = (result != next_val)
            return result

        # Handle numeric/string equality (e.g., 5 == 5 or "hi" != "bye")...
        # In the grammar, the operator is always the middle child (index 1)...
        left = self.visit(ctx.getChild(0))
        right = self.visit(ctx.getChild(2))
        
        op_type = ctx.getChild(1).getSymbol().type
        
        if op_type == C4ChineseParser.EQ:
            return left == right
        elif op_type == C4ChineseParser.NEQ:
            return left != right
            
        return None
    
    def visitBoolExp3(self, ctx: C4ChineseParser.BoolExp3Context):
        # Pass-through to the next precedence level...
        if ctx.boolExp4():
            return self.visit(ctx.boolExp4())
            
        # Handle relational comparisons...
        left = self.visit(ctx.getChild(0))
        right = self.visit(ctx.getChild(2))
        
        op_type = ctx.getChild(1).getSymbol().type
        
        if op_type == C4ChineseParser.LT:
            return left < right
        elif op_type == C4ChineseParser.GT:
            return left > right
        elif op_type == C4ChineseParser.LTE:
            return left <= right
        elif op_type == C4ChineseParser.GTE:
            return left >= right
            
        return None
    
    def visitBoolExp4(self, ctx: C4ChineseParser.BoolExp4Context):
        # --- PARENTHESES ---
        if ctx.boolExp():
            return self.visit(ctx.boolExp())
            
        # --- NOT OPERATOR (!) ---
        if ctx.NOT():
            val = self.visit(ctx.boolExp4())
            return not val
            
        # --- LITERALS ---
        if ctx.LT_BOOL():
            text = ctx.LT_BOOL().getText().lower()
            return text == 'zhen' or text == "真"
            
        # --- VARIABLES ---
        if ctx.boolVal():
            target_address = self.get_lvalue_address(ctx.boolVal().refVal())
            return self.memory.read(target_address)
            
        # --- POINTER DEREFERENCE ---
        if ctx.deRefVal():
            target_address = self.get_pointer_target(ctx.deRefVal())
            return self.memory.read(target_address)
            
        # --- FUNCTION CALLS ---
        if ctx.funcCall():
            return self.visit(ctx.funcCall())
            
        return None
    
    def visitStatBreak(self, ctx: C4ChineseParser.StatBreakContext):
        raise BreakException()

    def visitStatContinue(self, ctx: C4ChineseParser.StatContinueContext):
        raise ContinueException()
    
    def visitIfStat(self, ctx: C4ChineseParser.IfStatContext):
        # Evaluate the boolean condition
        condition = self.visit(ctx.expression())
        
        if condition:
            # If true, execute the block
            self.visit(ctx.statement())
            # Skip the unexecuted elif/else chains to maintain scope sync
            if ctx.elifList():
                self.skip_blocks(ctx.elifList())
        else:
            # Skip the true block
            self.skip_blocks(ctx.statement())
            # Check if there's an elif/else chain...
            if ctx.elifList():
                self.visit(ctx.elifList())
            
        return None

    def visitElifList(self, ctx: C4ChineseParser.ElifListContext):
        if ctx.ELIF():
            condition = self.visit(ctx.expression())
            if condition:
                self.visit(ctx.statement())
                if ctx.elifList():
                    self.skip_blocks(ctx.elifList())
            else:
                self.skip_blocks(ctx.statement())
                if ctx.elifList():
                    self.visit(ctx.elifList())
                
        elif ctx.ELSE():
            self.visit(ctx.statement())
            
        return None
    
    def visitWhileStat(self, ctx: C4ChineseParser.WhileStatContext):
        saved_index = self.symbol_table.current_scope.block_index
        
        while self.visit(ctx.expression()):
            # Rewind the index for every loop iteration to reuse the same scope
            self.symbol_table.current_scope.block_index = saved_index
            
            try:
                self.visit(ctx.statement())
                
            except BreakException:
                self.symbol_table.current_scope.block_index = saved_index
                break
                
            except ContinueException:
                pass 
                
        # Once the loop ends, restore the original index and skip exactly once 
        # to advance past the loop's internal blocks
        self.symbol_table.current_scope.block_index = saved_index
        self.skip_blocks(ctx.statement())

        return None
    
    def visitRepeatUntilStat(self, ctx: C4ChineseParser.RepeatUntilStatContext):
        saved_index = self.symbol_table.current_scope.block_index
        
        while True:
            self.symbol_table.current_scope.block_index = saved_index
            
            try:
                self.visit(ctx.statement())
            except BreakException:
                self.symbol_table.current_scope.block_index = saved_index
                break
            except ContinueException:
                pass
                
            condition = self.visit(ctx.expression())
            if condition:
                break
                
        self.symbol_table.current_scope.block_index = saved_index
        self.skip_blocks(ctx.statement())

        return None
    
    def visitForStat(self, ctx: C4ChineseParser.ForStatContext):
        # 1. Sync BOTH scopes...
        
        self.enter_scope()
        self.symbol_table.enter_next_block() 

        # 2. Initialization
        if ctx.varDeclFor():
            self.visit(ctx.varDeclFor())
        elif ctx.assignStat():
            self.visit(ctx.assignStat())

        # 3. The Loop Execution
        while self.visit(ctx.expression()):
            
            saved_index = self.symbol_table.current_scope.block_index
            
            try:
                self.visit(ctx.statement())
            except BreakException:
                self.symbol_table.current_scope.block_index = saved_index
                break
            except ContinueException:
                pass
                
            self.symbol_table.current_scope.block_index = saved_index
            
            self.visit(ctx.assignStatNoEnd())

        # 4. Pop BOTH scopes when the loop is totally finished...
        self.exit_scope()
        self.symbol_table.exit_scope()
        
        return None
    
    def visitVarDeclFor(self, ctx: C4ChineseParser.VarDeclForContext):
        name = ctx.idWrapper().getText()
        
        # 1. Resolve type and size...
        var_sym = self.symbol_table.resolve(name)
        size = TypeManager.get_size(var_sym.type)
        
        # 2. Allocate and define in the local loop scope...
        base_address = self.memory.allocate(size)
        self.current_env.define(name, base_address)
        
        # 3. Write the initial value (e.g., the '0' in i = 0)...
        if ctx.expression():
            val = self.visit(ctx.expression())
            self.memory.write(base_address, val)
            
        return None
    
    def visitAssignStatNoEnd(self, ctx: C4ChineseParser.AssignStatNoEndContext):
        # 1. Evaluate the right side...
        value = self.visit(ctx.expression())
        assignable = ctx.assignableVal()
        
        # 2. Find the memory address to update...
        if assignable.refVal():
            target_address = self.get_lvalue_address(assignable.refVal())
        elif assignable.deRefVal():
            target_address = self.get_pointer_target(assignable.deRefVal())
            
        # 3. Write the new value to memory...
        self.memory.write(target_address, value)
        
        return None
    
    def visitStatPrint(self, ctx: C4ChineseParser.StatPrintContext):
        # 1. Evaluate the expression to get the actual value...
        val = self.visit(ctx.expression())
        
        self.trace(f"Executing geini (PRINT) for value: {val} of type {type(val).__name__}")
        
        # 2. Format booleans to match the language keywords...
        if isinstance(val, bool):
            val = "zhen" if val else "buzhen"
            
        # 3. Print it to the console...
        print(val)
        
        return None
    
    def visitStatInput(self, ctx: C4ChineseParser.StatInputContext):
        for assignable_ctx in ctx.assignableVal():
            
            # 1. Determine the memory address and the expected data type...
            if assignable_ctx.refVal():
                lvalue_ctx = assignable_ctx.refVal()

                # Get the memory address using the unified resolver...
                target_address = self.get_lvalue_address(lvalue_ctx)
                
                final_type = self.get_lvalue_type(lvalue_ctx)
                expected_type = final_type.name.split('[')[0] if final_type else "unknown"
                display_name = lvalue_ctx.getText()
                
            elif assignable_ctx.deRefVal():
                lvalue_ctx = assignable_ctx.deRefVal()

                # Get the memory address the pointer points to...
                target_address = self.get_pointer_target(lvalue_ctx)
                
                final_type = self.get_deref_type(lvalue_ctx)
                expected_type = final_type.name.split('[')[0] if final_type else "unknown"
                display_name = lvalue_ctx.getText()
                                
            # 2. Prompt the user for input using Python's native input()...
            self.trace(f"Waiting for user input for '{display_name}'...")
            prompt_str = f"{display_name} > "
            
            # NOTE: This should be uncommented if using Main.py...
            # user_in = input(f"{display_name} > ")

            # NOTE: This should be uncommented if using IDE...
            if getattr(self, 'input_hook', None):
                user_in = self.input_hook(prompt_str)
            else:
                user_in = input(prompt_str)

            
            # 3. Cast the raw string input to the correct data type...
            try:
                if expected_type == "int":
                    final_val = int(user_in)
                elif expected_type == "float":
                    final_val = float(user_in)
                elif expected_type == "bool":
                    # Map language's boolean keywords...
                    final_val = (user_in.lower() in ["zhen", "真", "1"])
                else:
                    # Leave strings, chars, and unknown pointer dereferences as raw text...
                    final_val = user_in 
            except ValueError:
                raise Exception(f"Runtime Error: Invalid input '{user_in}'. Expected type '{expected_type}'.")
                
            # 4. Write the casted value to simulated memory...
            self.memory.write(target_address, final_val)
            
        return None
    
    def visitReturnStat(self, ctx: C4ChineseParser.ReturnStatContext):
        return_value = None
        
        # If there is an expression to return, evaluate it...
        if ctx.expression():
            return_value = self.visit(ctx.expression())
            
        # Stop executing the function and throw the value back to the caller...
        raise ReturnException(return_value)
    
    def visitFuncRet(self, ctx: C4ChineseParser.FuncRetContext):
        name = ctx.idWrapper().getText()
        self.function_bodies[name] = ctx.funcContent()
        return None

    def visitFuncVoid(self, ctx: C4ChineseParser.FuncVoidContext):
        name = ctx.idWrapper().getText()
        self.function_bodies[name] = ctx.funcContent()
        return None

    def visitMainFunc(self, ctx: C4ChineseParser.MainFuncContext):
        self.trace("Registering 'main' function")
        self.function_bodies["main"] = ctx.funcContent()
        return None
    
    def visitProgram(self, ctx: C4ChineseParser.ProgramContext):
        # 1. Visit everything to register global variables and function bodies...
        self.visitChildren(ctx)
        
        # 2. Manually trigger the 'main' function...
        if "main" not in self.function_bodies:
            raise Exception("Runtime Error: No main function found to execute.")
            
        self.trace("--- Starting execution of 'main' ---")
        main_body_ctx = self.function_bodies["main"]
        
        # Sync the static Symbol Table to 'main'
        self.symbol_table.enter_scope_by_name("main")
        self.symbol_table.current_scope.reset_block_index()
        
        # Create the runtime Environment for 'main'
        previous_env = self.current_env
        self.current_env = Environment(parent=self.global_env)
        self.call_stack.append("main")
        
        exit_code = 0
        try:
            self.visit(main_body_ctx)
        except ReturnException as ret:
            exit_code = ret.value if ret.value is not None else 0

        self.final_env_state = self.get_environment_data()
        self.final_call_stack = list(self.call_stack)
            
        # Clean up both scopes when the program ends...
        self.current_env = previous_env
        self.symbol_table.exit_scope()
        self.call_stack.pop()
        
        return exit_code
    
    # Helper to dig through an expression AST to find the assignable variable
    def _find_lvalue_context(self, ctx):
        if hasattr(ctx, 'refVal') and ctx.refVal():
            return ctx.refVal()
        if hasattr(ctx, 'deRefVal') and ctx.deRefVal():
            return ctx.deRefVal()
            
        # Recursively search children if we haven't hit the variable yet...
        if hasattr(ctx, 'getChildren'):
            for child in ctx.getChildren():
                found = self._find_lvalue_context(child)
                if found:
                    return found
        return None
    
    # Helper to process ++x, --x, x++, x--
    def _handle_inc_dec(self, ctx: C4ChineseParser.NumExp2Context):
        is_inc = ctx.INC() is not None
        
        # 1. Get current address and value...
        target_address = self.get_lvalue_address(ctx.numRef().refVal())
        current_value = self.memory.read(target_address)
        
        # 2. Determine if it's pre-increment (++x) or post-increment (x++)
        # If the first child is NOT numRef, then it must be the ++/-- token (pre-increment)...
        is_pre = (ctx.getChild(0) != ctx.numRef())
        
        # 3. Write the new value to memory...
        new_value = current_value + 1 if is_inc else current_value - 1
        self.memory.write(target_address, new_value)
        
        # 4. Return the correct value for the expression...
        return new_value if is_pre else current_value

    # Evaluates a pointer chain (^p or ^^p) and returns the memory address it points to.
    def get_pointer_target(self, ctx: C4ChineseParser.DeRefValContext):
        if ctx.refVal():
            # Base case: ^p 
            # Get the address of 'p' itself
            ptr_address = self.get_lvalue_address(ctx.refVal())
            
            # Read the value stored inside 'p' (which is the address it points to)...
            target_address = self.memory.read(ptr_address)
            
            if target_address is None:
                raise Exception("Runtime Error: Null pointer dereference.")
                
            return target_address
            
        elif ctx.deRefVal():
            # Recursive case: ^^p 
            # Recursively get the address that ^p points to
            ptr_address = self.get_pointer_target(ctx.deRefVal())
            
            # Read the next address in the chain...
            target_address = self.memory.read(ptr_address)
            
            if target_address is None:
                raise Exception("Runtime Error: Null pointer dereference.")
                
            return target_address

    def resolve_struct_member_address(self, base_var_name, field_name, struct_type):
        # 1. Get where the struct starts in memory...
        base_address = self.current_env.resolve_address(base_var_name)
        
        # 2. Ask the TypeManager for the struct's layout...
        offsets = TypeManager.get_struct_offsets(struct_type)
        
        if field_name not in offsets:
            raise Exception(f"Runtime Error: Field '{field_name}' not found.")
            
        # 3. Add the offset to the base address...
        field_address = base_address + offsets[field_name]
        
        return field_address
    
    # Calculates the absolute memory address of any chained variable.
    def get_lvalue_address(self, ctx: C4ChineseParser.RefValContext):
        
        # 1. Start with the base variable (e.g., 'arr' or 'student')...
        var_name = ctx.idWrapper().getText()
        current_address = self.current_env.resolve_address(var_name)
        
        # We need the SymbolTable type to know element sizes and struct layouts...
        var_sym = self.symbol_table.resolve(var_name)
        current_type = var_sym.type if isinstance(var_sym, VarSymbol) else var_sym
        
        # 2. Process the chain (e.g., [5], .gpa, etc.)...
        prime_ctx = ctx.refValPrime()
        
        while prime_ctx and prime_ctx.getText() != "":
            
            # --- ARRAY ACCESS ---
            if prime_ctx.LBAR(): 
                # Evaluate the index (e.g., the '5' in arr[5])...
                index_val = self.visit(prime_ctx.numExp())
                
                # Bounds Checking
                if index_val < 0 or index_val >= current_type.size:
                    raise Exception(f"Runtime Error: Index {index_val} out of bounds for array of size {current_type.size}.")
                
                # Get the size of a single element (stride)...
                element_type = current_type.base_type
                element_size = TypeManager.get_size(element_type)
                
                # Move the address forward by (index * stride)...
                current_address += (index_val * element_size)
                
                # Update the type for the next link in the chain...
                current_type = element_type
                
                # Advance the chain...
                prime_ctx = prime_ctx.refValPrime()
                
            # --- STRUCT ACCESS ---
            elif prime_ctx.DOT():
                # Get the right side of the dot (e.g., 'gpa')...
                ref_val_ctx = prime_ctx.refVal()
                member_name = ref_val_ctx.idWrapper().getText()
                
                # Ask TypeManager for the pre-calculated offsets...
                offsets = TypeManager.get_struct_offsets(current_type)
                
                if member_name not in offsets:
                    raise Exception(f"Runtime Error: Field '{member_name}' not found in struct.")
                
                # Move the address forward by the field's offset...
                current_address += offsets[member_name]
                
                # Update the type for the next link in the chain...
                member_sym = current_type.symbols[member_name]
                current_type = member_sym.type if isinstance(member_sym, VarSymbol) else member_sym
                
                # Advance the chain (handling nested chains inside the refVal)...
                if ref_val_ctx.refValPrime() and ref_val_ctx.refValPrime().getText() != "":
                    prime_ctx = ref_val_ctx.refValPrime()
                else:
                    prime_ctx = prime_ctx.refValPrime()
                    
        return current_address
    
    def visit(self, tree):
        # Determine the name of the ANTLR context class...
        class_name = type(tree).__name__
        
        # Check if this node is one of the labeled statements...
        is_statement = class_name.startswith('Stat') and class_name.endswith('Context') and class_name != 'StatBlockContext'
        
        if self.interactive_debug and is_statement:
            line = getattr(tree.start, 'line', 'Unknown')
            
            # Extract raw text without spaces
            if hasattr(tree, 'start') and hasattr(tree, 'stop') and tree.start and tree.stop:
                input_stream = tree.start.getInputStream()
                # Grab the exact character slice from the original source file...
                text = input_stream.getText(tree.start.start, tree.stop.stop)
            else:
                # Fallback just in case...
                text = tree.getText()
                
            # Clean up newlines/tabs so it prints nicely on one line in the console...
            text = text.replace('\n', ' ').replace('\r', '').replace('\t', ' ').strip()
            
            # Truncate text if it's a massive while loop or if block...
            if len(text) > 60:
                text = text[:57] + "..."
                
            print(f"\n\033[93m\033[1m>>> [Line {line}]\033[0m \033[90mExecuting: {text}\033[0m")
            
            try:
                # Actually execute the statement...
                result = super().visit(tree)
                return result
            finally:
                # Print the updated state (Useful for command line)...
                if not getattr(self, 'debug_hook', None):
                    self.print_callstack()
                    self.print_runtime_table()
                
                if self.interactive_debug:

                    if getattr(self, 'debug_hook', None):
                        # IDE MODE: Pass 'tree' because it IS the 'ctx'
                        self.debug_hook(self, tree)
                    else:
                        # COMMAND LINE MODE: Fallback to input()
                        command = input("\033[92m[DEBUG] Press Enter to step, or type 'c' to run continuously: \033[0m").strip().lower()
                        
                        if command == 'c':
                            self.interactive_debug = False
                            self.debug_trace = True
                            print("\033[90mContinuing execution without pausing...\033[0m")
                
        else:
            # If it's just an expression or math node, evaluate normally
            return super().visit(tree)
        

    # Prints the current chain of function calls...
    def print_callstack(self):
        print("\n\033[95m\033[1m=== CALLSTACK ===\033[0m")
        if not self.call_stack:
            print("  (Empty)")
        else:
            for i, func in enumerate(reversed(self.call_stack)):
                if i == 0:
                    print(f"  -> \033[92m{func}\033[0m (Current)")
                else:
                    print(f"     {func}")
        print("\033[95m=================\033[0m\n")

    # Prints all variables in the current environment chain and their memory values.
    def print_runtime_table(self):
        print("\033[96m\033[1m=== RUNTIME ENVIRONMENT TABLE ===\033[0m")
        # Widened 'Variable Name' to 35 characters to support deep visual nesting
        print(f"{'Scope Level':<15} | {'Variable Name':<35} | {'Address':<10} | {'Value'}")
        print("-" * 85)

        current = self.current_env
        depth = 0
        
        while current is not None:
            scope_label = "Global" if current.parent is None else f"Local (Scope {depth})"
            
            if not current.variables:
                print(f"{scope_label:<15} | \033[90m{'(No variables)':<35}\033[0m | {'-':<10} | -")
            else:
                for name, address in current.variables.items():
                    var_sym = self.symbol_table.resolve(name)
                    
                    if var_sym and hasattr(var_sym, 'type') and isinstance(var_sym.type, StructTypeSymbol):
                        print(f"{scope_label:<15} | \033[93m{name:<35}\033[0m | \033[94m{address:<10}\033[0m | \033[90m<Struct>\033[0m")
                        self._print_struct_fields(name, address, var_sym.type, scope_label, indent_level=1)
                        
                    elif var_sym and hasattr(var_sym, 'type') and isinstance(var_sym.type, ArrayType):
                        print(f"{scope_label:<15} | \033[93m{name:<35}\033[0m | \033[94m{address:<10}\033[0m | \033[90m<Array[{var_sym.type.size}]>\033[0m")
                        self._print_array_elements(name, address, var_sym.type, scope_label, indent_level=1)
                        
                    else:
                        try:
                            val = self.memory.read(address)
                            val_str = str(val) if val is not None else "null"
                            if len(val_str) > 30:
                                val_str = val_str[:27] + "..."
                        except Exception:
                            val_str = "\033[91m<Unallocated>\033[0m"
                            
                        print(f"{scope_label:<15} | \033[93m{name:<35}\033[0m | \033[94m{address:<10}\033[0m | {val_str}")
            
            current = current.parent
            depth += 1
            
        print("\033[96m=================================\033[0m\n")
        
    # Recursively prints the fields of a struct and their memory values...
    def _print_struct_fields(self, base_name, base_address, struct_type, scope_label, indent_level=1):
        offsets = TypeManager.get_struct_offsets(struct_type)
        
        # Multiply the indentation spacing based on how deep we are...
        indent_str = "  " * indent_level + "↳ "
        
        for field_name, offset in offsets.items():
            field_addr = base_address + offset
            full_name = f"{indent_str}{base_name}.{field_name}" 
            
            member_sym = struct_type.symbols.get(field_name)
            field_type = member_sym.type if isinstance(member_sym, VarSymbol) else member_sym
            
            # The clean base name we pass down to the next recursion level...
            clean_base_name = f"{base_name}.{field_name}"
            
            if isinstance(field_type, StructTypeSymbol):
                print(f"{scope_label:<15} | \033[93m{full_name:<35}\033[0m | \033[94m{field_addr:<10}\033[0m | \033[90m<Struct>\033[0m")
                self._print_struct_fields(clean_base_name, field_addr, field_type, scope_label, indent_level + 1)
                
            elif isinstance(field_type, ArrayType):
                print(f"{scope_label:<15} | \033[93m{full_name:<35}\033[0m | \033[94m{field_addr:<10}\033[0m | \033[90m<Array[{field_type.size}]>\033[0m")
                self._print_array_elements(clean_base_name, field_addr, field_type, scope_label, indent_level + 1)
                
            else:
                try:
                    val = self.memory.read(field_addr)
                    val_str = str(val) if val is not None else "null"
                    if len(val_str) > 30:
                        val_str = val_str[:27] + "..."
                except Exception:
                    val_str = "\033[91m<Unallocated>\033[0m"
                    
                print(f"{scope_label:<15} | \033[93m{full_name:<35}\033[0m | \033[94m{field_addr:<10}\033[0m | {val_str}")
    
    # Recursively prints ALL array elements without truncation.
    def _print_array_elements(self, base_name, base_address, array_type, scope_label, indent_level=1):
        element_type = array_type.base_type
        element_size = TypeManager.get_size(element_type)
        
        # Multiply the indentation spacing based on how deep we are...
        indent_str = "  " * indent_level + "↳ "
        
        for i in range(array_type.size):
            elem_addr = base_address + (i * element_size)
            full_name = f"{indent_str}{base_name}[{i}]"
            clean_base_name = f"{base_name}[{i}]"
            
            if isinstance(element_type, StructTypeSymbol):
                print(f"{scope_label:<15} | \033[93m{full_name:<35}\033[0m | \033[94m{elem_addr:<10}\033[0m | \033[90m<Struct>\033[0m")
                self._print_struct_fields(clean_base_name, elem_addr, element_type, scope_label, indent_level + 1)
                
            elif isinstance(element_type, ArrayType):
                print(f"{scope_label:<15} | \033[93m{full_name:<35}\033[0m | \033[94m{elem_addr:<10}\033[0m | \033[90m<Array[{element_type.size}]>\033[0m")
                self._print_array_elements(clean_base_name, elem_addr, element_type, scope_label, indent_level + 1)
                
            else:
                try:
                    val = self.memory.read(elem_addr)
                    val_str = str(val) if val is not None else "null"
                    if len(val_str) > 30:
                        val_str = val_str[:27] + "..."
                except Exception:
                    val_str = "\033[91m<Unallocated>\033[0m"
                    
                print(f"{scope_label:<15} | \033[93m{full_name:<35}\033[0m | \033[94m{elem_addr:<10}\033[0m | {val_str}")
                
     # Recursively counts and skips blocks to keep the SymbolTable scopes in sync.
    def skip_blocks(self, ctx):
        if not ctx: return
        
        if isinstance(ctx, list):
            for c in ctx:
                self.skip_blocks(c)
            return

        ctx_class = type(ctx).__name__
        
        # If we hit a block-creating node, advance the index and stop recursing into it
        if ctx_class in ["StatBlockContext", "ForStatContext"]:
            self.symbol_table.current_scope.block_index += 1
            return
            
        # Otherwise, recurse into children
        if hasattr(ctx, 'getChildren'):
            for child in ctx.getChildren():
                self.skip_blocks(child)       

    # Recursively resolves the exact datatype of chained variables (arrays/structs)...
    def get_lvalue_type(self, ctx: C4ChineseParser.RefValContext):
        var_name = ctx.idWrapper().getText()
        var_sym = self.symbol_table.resolve(var_name)
        current_type = var_sym.type if hasattr(var_sym, 'type') else var_sym
        
        prime_ctx = ctx.refValPrime()
        while prime_ctx and prime_ctx.getText() != "":
            if prime_ctx.LBAR():
                current_type = current_type.base_type
                prime_ctx = prime_ctx.refValPrime()
            elif prime_ctx.DOT():
                ref_val_ctx = prime_ctx.refVal()
                member_name = ref_val_ctx.idWrapper().getText()
                
                member_sym = current_type.symbols[member_name]
                current_type = member_sym.type if hasattr(member_sym, 'type') else member_sym
                
                if ref_val_ctx.refValPrime() and ref_val_ctx.refValPrime().getText() != "":
                    prime_ctx = ref_val_ctx.refValPrime()
                else:
                    prime_ctx = prime_ctx.refValPrime()
                    
        return current_type

    # Recursively resolves the datatype that a pointer is pointing to...
    def get_deref_type(self, ctx: C4ChineseParser.DeRefValContext):
        if ctx.refVal():
            base_type = self.get_lvalue_type(ctx.refVal())
            return base_type.base_type if hasattr(base_type, 'base_type') else base_type
        elif ctx.deRefVal():
            base_type = self.get_deref_type(ctx.deRefVal())
            return base_type.base_type if hasattr(base_type, 'base_type') else base_type

class TypeManager:
    @staticmethod
    def get_size(type_sym) -> int:
        """Recursively calculates the memory size required for a given TypeSymbol."""
        
        # 1. Primitives & Pointers: Always take exactly 1 memory address...
        if isinstance(type_sym, (PrimitiveTypeSymbol, PointerType)):
            return 1
            
        # 2. Arrays: Number of elements * size of the base type...
        elif isinstance(type_sym, ArrayType):
            base_size = TypeManager.get_size(type_sym.base_type)
            return type_sym.size * base_size
            
        # 3. Structs / Records: Sum of the sizes of all its fields...
        elif isinstance(type_sym, StructTypeSymbol):
            total_size = 0
            # StructTypeSymbol inherits from Scope, so it holds its members in .symbols...
            for member_name, member_sym in type_sym.symbols.items():
                # Only count variables (ignore nested type definitions if any exist)...
                if isinstance(member_sym, VarSymbol):
                    total_size += TypeManager.get_size(member_sym.type)
            return total_size
            
        # 4. Typedefs: Get the size of the underlying actual type...
        elif isinstance(type_sym, TypedefSymbol):
            return TypeManager.get_size(type_sym.actual)
            
        else:
            raise Exception(f"Runtime Error: Cannot determine size of unknown type '{type(type_sym)}'")

    # Calculates the memory offset for each attribute inside a struct.
    # Returns a dictionary: { 'field_name': integer_offset }
    @staticmethod
    def get_struct_offsets(struct_sym: StructTypeSymbol) -> dict:
        offsets = {}
        current_offset = 0
        
        for member_name, member_sym in struct_sym.symbols.items():
            if isinstance(member_sym, VarSymbol):
                offsets[member_name] = current_offset
                # Increment the offset by the size of the current field
                current_offset += TypeManager.get_size(member_sym.type)
                
        return offsets
    
