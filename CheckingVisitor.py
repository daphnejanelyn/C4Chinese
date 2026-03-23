from os import name

from C4ChineseParserVisitor import C4ChineseParserVisitor
from C4ChineseParser import C4ChineseParser

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    MAGENTA = '\033[95m'

# Symbols are anything that has a name. They can be variables, functions, types, etc...
class Symbol:
    def __init__(self, name: str):
        self.name = name
       

# Scopes are used to store symbols, making up the symbol table. 
# They can be global scope, function scope, block scope, etc...
# They can be nested within each other, with the global scope being the root.
class Scope:
    error_count = 0
    def __init__(self, parent=None):
        self.symbols = {}
        self.parent = parent

        # We need to keep track of blocked scopes because they are not
        # stored in the symbol table...
        self.blocks = []
        self.block_index = 0

    def define(self, symbol: Symbol):
        if symbol.name in self.symbols:
            Scope.error_count += 1
            print(f"{Colors.RED}Scope Error {Colors.RESET}'{symbol.name}' already defined in this scope{Colors.RESET}")
        else:
            self.symbols[symbol.name] = symbol

    def add_block(self, block):
        self.blocks.append(block)

    def resolve(self, name: str):

        # Check current scope...
        if name in self.symbols:
            return self.symbols[name]
        # Check parent scopes...
        elif self.parent is not None:
            return self.parent.resolve(name)
        # Not found in any scope...
        else:
            return None

    def __repr__(self):
        return f"{Colors.HEADER}Block{Colors.RESET}"

    def get_next_block(self):
        self.block_index += 1
        return self.blocks[self.block_index - 1]
    
    def reset_block_index(self):
        self.block_index = 0

    def print_tree(self, prefix="", is_last=True):
        def is_visible(node):
            if not isinstance(node, Scope):
                return True
            if node.symbols:
                return True
            children = getattr(node, "blocks", []) or getattr(node, "nested_scopes", [])
            return any(is_visible(c) for c in children)

        raw_blocks = getattr(self, "blocks", []) or getattr(self, "nested_scopes", [])
        raw_children = list(self.symbols.values()) + raw_blocks

        visible_children = [child for child in raw_children if is_visible(child)]

        if not visible_children:
            return ""

        connector = "└── " if is_last else "├── "
        output = f"{prefix}{connector}{self}\n"
        
        child_prefix = prefix + ("    " if is_last else "│   ")
        count = len(visible_children)
        
        for i, child in enumerate(visible_children):
            is_last_child = (i == count - 1)
            
            if isinstance(child, Scope):
                output += child.print_tree(child_prefix, is_last_child)
            else:
                leaf_connector = "└── " if is_last_child else "├── "
                output += f"{child_prefix}{leaf_connector}{child}\n"
                
        return output

# Symbols for types...
class TypeSymbol(Symbol):
    def __init__(self, name: str):
        super().__init__(name)
    def __repr__(self):
        return f"{Colors.CYAN}Type{Colors.RESET}(name='{Colors.YELLOW}{self.name}{Colors.RESET}')"

class PrimitiveTypeSymbol(TypeSymbol):
    def __init__(self, name: str):
        super().__init__(name)
    def __repr__(self): 
        return f"{Colors.GREEN}PrimitiveTypeSymbol{Colors.RESET}(name='{Colors.YELLOW}{self.name}{Colors.RESET}')"

# Technically, pointers and arrays are not symbols stored in the symbol table.
# For simplicity we treat them as symbols here, but later on, we will not store them in
# the symbol table, but rather create them on the fly when needed.
class PointerType(TypeSymbol):
    def __init__(self, base_type: TypeSymbol):
        super().__init__(f"{base_type.name}^")
        self.base_type = base_type
    def __repr__(self): 
        return f"{Colors.CYAN}PointerType{Colors.RESET}(base_type={self.base_type})"

class ArrayType(TypeSymbol):
    def __init__(self, base_type: TypeSymbol, size: int):
        super().__init__(f"{base_type.name}[{size}]")
        self.base_type = base_type
        self.size = size

    def set_val(self, val):
        self.val = val
    
    def __repr__(self): 
        return (f"{Colors.CYAN}ArrayType{Colors.RESET}("
                f"base_type={self.base_type}, "
                f"size={Colors.YELLOW}{self.size}{Colors.RESET})")

# Structs are both types and scopes, since they define a new type and also contain member variables.
class StructTypeSymbol(TypeSymbol, Scope):
    def __init__(self, name: str, parent_scope: Scope):
        Symbol.__init__(self, name)
        Scope.__init__(self, parent=parent_scope)
        self.parent_scope = parent_scope

    def __repr__(self):
        return f"{Colors.CYAN}StructTypeSymbol{Colors.RESET}(name='{Colors.YELLOW}{self.name}{Colors.RESET}')"


# Symbols for vars, consts, typedefs, and funcs...
class VarSymbol(Symbol):
    def __init__(self, name: str, type: TypeSymbol, is_const:bool=False):
        super().__init__(name)
        self.type = type
        self.is_const = is_const
        self.val = None
        self.rhs_counter = 0
        self.var_decl_assign_nodes = []
        self.struct_assignments = {} 
        self.struct_reads = set()
        self.isparam = False
        
    def set_val(self, val):
        self.val = val

    def __repr__(self):
        return (f"{Colors.BLUE}VarSymbol{Colors.RESET}("
            f"name='{Colors.YELLOW}{self.name}{Colors.RESET}', "
            f"type='{Colors.CYAN}{self.type.name}{Colors.RESET}', "
            f"const='{Colors.YELLOW}{self.is_const}{Colors.RESET}')")
    
class TypedefSymbol(TypeSymbol):
    def __init__(self, name: str, actual: TypeSymbol):
        super().__init__(name=name)
        self.actual = actual
    def __repr__(self):
        return (f"{Colors.CYAN}TypedefSymbol{Colors.RESET}("
                f"name='{Colors.YELLOW}{self.name}{Colors.RESET}', "
                f"actual='{Colors.CYAN}{self.actual.name}{Colors.RESET}')")

class FunctionSymbol(Symbol, Scope):
    def __init__(self, name: str, return_type: TypeSymbol, parameters: list, parent_scope: Scope):
        Symbol.__init__(self, name)
        Scope.__init__(self, parent=parent_scope)
        self.return_type = return_type
        self.parent_scope = parent_scope
        self.parameters = parameters
        for p in parameters:
            self.define(p)
    
    def __repr__(self):
        return (f"{Colors.MAGENTA}FunctionSymbol{Colors.RESET}("
                f"name='{Colors.YELLOW}{self.name}{Colors.RESET}', "
                f"return='{Colors.CYAN}{self.return_type.name}{Colors.RESET}')")

class SymbolTable:
    def __init__(self):
        # Initialize the global scope with primitive types...
        self.global_scope = Scope(parent=None)
        self.current_scope = self.global_scope

        self.current_scope.define(PrimitiveTypeSymbol("int"))
        self.current_scope.define(PrimitiveTypeSymbol("float"))
        self.current_scope.define(PrimitiveTypeSymbol("char"))
        self.current_scope.define(PrimitiveTypeSymbol("string"))
        self.current_scope.define(PrimitiveTypeSymbol("bool"))
        self.current_scope.define(PrimitiveTypeSymbol("void"))
        self.current_scope.define(PrimitiveTypeSymbol("null"))
        self.current_scope.define(PrimitiveTypeSymbol("int_null"))
        self.current_scope.define(PrimitiveTypeSymbol("string_null"))
        self.current_scope.define(PrimitiveTypeSymbol("float_null"))
        self.current_scope.define(PrimitiveTypeSymbol("char_null"))
        self.current_scope.define(PrimitiveTypeSymbol("bool_null"))
        

    def enter_scope(self, new_scope:Scope=None):
        # Used for named scopes, like functions and structs...
        if new_scope:
            self.current_scope = new_scope
        # Used for anonymous scopes, like blocks...
        else:
            block = Scope(self.current_scope)
            self.current_scope.add_block(block)
            self.current_scope = block

    def exit_scope(self):
        if self.current_scope.parent:
            self.current_scope = self.current_scope.parent
        else:
            raise Exception(f"Cannot exit out of global scope...")

    def enter_scope_by_name(self, name):
        for k in self.current_scope.symbols:
            if isinstance(self.current_scope.symbols[k], Scope):
                if self.current_scope.symbols[k].name == name:
                    self.current_scope = self.current_scope.symbols[k]
                    return

    def reset_all_block_indices(self):
        """Recursively resets all block counters back to 0 before execution."""
        self._reset_blocks_recursive(self.global_scope)

    def _reset_blocks_recursive(self, scope):
        # Reset this scope's index
        if hasattr(scope, 'reset_block_index'):
            scope.reset_block_index()
            
        # Traverse into anonymous blocks (if/while/for loops)
        if hasattr(scope, 'blocks'):
            for block in scope.blocks:
                self._reset_blocks_recursive(block)
                
        # Traverse into named scopes (functions, structs)
        if hasattr(scope, 'symbols'):
            for sym in scope.symbols.values():
                if isinstance(sym, Scope):
                    self._reset_blocks_recursive(sym)

    def enter_next_block(self):
        self.current_scope = self.current_scope.get_next_block()
    
    def define(self, symbol):
        self.current_scope.define(symbol)

    def resolve(self, name):
        return self.current_scope.resolve(name)
    
    def print_contents(self):
        print("=== Symbol Table Hierarchy ===")
        print(self.global_scope.print_tree())

    def return_to_global_scope(self):
        self.current_scope = self.global_scope

    # def print_variable_stats(self):
    #     print(f"\n{Colors.MAGENTA}{Colors.BOLD}=== SANITY CHECK ==={Colors.RESET}")
    #     self._print_scope_stats(self.global_scope, depth=0, scope_name="Global Scope")

    # def _print_scope_stats(self, scope: Scope, depth: int, scope_name: str):
    #     indent = "    " * depth
        
    #     print(f"{indent}{Colors.CYAN}{Colors.BOLD}► {scope_name}{Colors.RESET}")
        
    #     vars_found = False
    #     for name, sym in scope.symbols.items():
    #         if isinstance(sym, VarSymbol):
    #             vars_found = True
    #             assign_cnt = len(sym.var_decl_assign_nodes)
                
    #             # Extract line numbers for context, if available
    #             lines = []
    #             for ctx in sym.var_decl_assign_nodes:
    #                 if hasattr(ctx, 'start') and ctx.start:
    #                     lines.append(str(ctx.start.line))
                
    #             lines_str = f" (Lines: {', '.join(lines)})" if lines else ""
                
    #             print(f"{indent}    • {Colors.YELLOW}{name}{Colors.RESET} "
    #                   f"[{getattr(sym.type, 'name', 'unknown')}]: "
    #                   f"Reads (RHS) = {Colors.GREEN}{sym.rhs_counter}{Colors.RESET} | "
    #                   f"Writes/Decls = {Colors.BLUE}{assign_cnt}{Colors.RESET}{lines_str}")
        
    #     if not vars_found:
    #         print(f"{indent}    {Colors.RED}(No variables tracked in this scope){Colors.RESET}")

    #     for name, sym in scope.symbols.items():
    #         if isinstance(sym, Scope):
    #             self._print_scope_stats(sym, depth + 1, f"{type(sym).__name__}: {name}")
                
    #     for i, block in enumerate(scope.blocks):
    #         self._print_scope_stats(block, depth + 1, f"Anonymous Block {i + 1}")


class CheckingVisitor(C4ChineseParserVisitor):

    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

    def __init__(self):
        self.symbol_table = SymbolTable()
        Scope.error_count = 0
        self.current_function = None
        self.has_returned = False
        self.parser_error_count = 0
        self.semantic_error_count = 0
        self.is_lhs = False

    @property
    def scope_error_count(self):
        return Scope.error_count
        
    def visitValidID(self, ctx):
        return ctx.getText()

    def visitTypeInteger(self, ctx:C4ChineseParser.TypeIntegerContext):
        return self.symbol_table.resolve("int")

    def visitTypeFloat(self, ctx:C4ChineseParser.TypeIntegerContext):
        return self.symbol_table.resolve("float")
    
    def visitTypeChar(self, ctx:C4ChineseParser.TypeCharContext):
        return self.symbol_table.resolve("char")
    
    def visitTypeString(self, ctx:C4ChineseParser.TypeCharContext):
        return self.symbol_table.resolve("string")

    def visitTypeBoolean(self, ctx:C4ChineseParser.TypeBooleanContext):
        return self.symbol_table.resolve("bool")

    def visitTypeIdentifier(self, ctx):
        # 1. Get the name of the custom type...
        type_name = self.visit(ctx.idWrapper())
        
        # 2. Look it up in the symbol table...
        resolved_type = self.symbol_table.resolve(type_name)
        
        # 3. If it doesn't exist, throw an error and return a safe dummy type...
        if resolved_type is None:
            self.semanticError(ctx, f"Data type '{type_name}' has not been defined.")
            return TypeSymbol("unknown") # Prevents 'NoneType' crashes downstream
            
        while isinstance(resolved_type, TypedefSymbol):
            resolved_type = resolved_type.actual

        return resolved_type

    def visitTypePointer(self, ctx):
        base_type = self.visit(ctx.dataType())
        if base_type is None:
            return None
        else:
            return PointerType(base_type=base_type)
        
    def visitTypeArray(self, ctx):
        base_type = self.visit(ctx.dataType())
        size = int(ctx.LT_INT().getText())

        if base_type is None:
            return None
        else:
            return ArrayType(base_type=base_type, size=size)
        
    def visitArrayInitExp(self, ctx: C4ChineseParser.ArrayInitExpContext):
        # 1. Handle empty initialization {}
        if not ctx.expList():
            return ArrayType(base_type=TypeSymbol("unknown"), size=0)

        # 2. Get the list of types from expList...
        element_types = self.visit(ctx.expList())
        
        if not element_types:
            return ArrayType(base_type=TypeSymbol("unknown"), size=0)
            
        # 3. Enforce that all elements are exactly the same type...
        first_type = element_types[0]
        first_name = getattr(first_type, 'name', str(first_type)) if first_type else "unknown"
        
        for i, t in enumerate(element_types):
            t_name = getattr(t, 'name', str(t)) if t else "unknown"
            if t_name != first_name:
                self.semanticError(ctx, f"Array initialization contains mismatched types: expected '{first_name}', found '{t_name}' at index {i}.")
                return None
                
        # 4. Return the bundled ArrayType with its calculated size...
        return ArrayType(base_type=first_type, size=len(element_types))

    def visitExpList(self, ctx: C4ChineseParser.ExpListContext):
        # Collect and return a list of evaluated expression types
        return [self.visit(expr) for expr in ctx.expression()]
    
    def visitRecordDecl(self, ctx):
        name = self.visit(ctx.idWrapper())
        record = StructTypeSymbol(name=name, parent_scope=self.symbol_table.current_scope)

        self.symbol_table.define(record)
        self.symbol_table.enter_scope(record)

        self.visit(ctx.recordContent())

        self.symbol_table.exit_scope()

        return record

    def visitVarDecl(self, ctx: C4ChineseParser.VarDeclContext):
        data_type = self.visit(ctx.dataType())
        name = self.visit(ctx.idWrapper())
        data_name = getattr(data_type, 'name', str(data_type)) if data_type else "unknown"

        if ctx.expression():
            expr_type = self.visit(ctx.expression())
            
            # Array handling
            if isinstance(data_type, ArrayType) and isinstance(expr_type, ArrayType):
                # 1. Base types must match (e.g., both must be 'int')
                if data_type.base_type.name != expr_type.base_type.name:
                    self.semanticError(ctx, f"Cannot assign array of '{expr_type.base_type.name}' to array of '{data_type.base_type.name}'.")
                
                # 2. Expression size must be <= declared size
                elif expr_type.size > data_type.size:
                    self.semanticError(ctx, f"Array initializer size ({expr_type.size}) exceeds declared array size ({data_type.size}).")
                    
            # Not array
            else:
                expr_name = getattr(expr_type, 'name', str(expr_type)) if expr_type else "unknown"
                
                if expr_name and data_name and expr_name != data_name:
                    is_valid_null = (expr_name == "null") or (expr_name == f"{data_name}_null") or (data_name == "float" and expr_name == "int_null")
                    
                    is_implicit_cast = (data_name == "float" and expr_name in ["int", "char"]) or (data_name == "int" and expr_name == "char")
                    
                    if not (is_valid_null or is_implicit_cast):
                        self.semanticError(ctx, f"Cannot assign type '{expr_name}' to variable '{name}' of type '{data_name}'.")
                    elif expr_name == "null" or expr_name == f"{data_name}_null":
                        null_type = self.symbol_table.resolve(f"{data_name}_null")
                        if null_type:
                            data_type = null_type

        var_sym = VarSymbol(name=name, type=data_type, is_const=False)
        var_sym.var_decl_assign_nodes.append(ctx)
        self.symbol_table.define(var_sym)
        return None

    def visitConstDecl(self, ctx: C4ChineseParser.ConstDeclContext):
        data_type = self.visit(ctx.dataType())
        name = self.visit(ctx.idWrapper())

        if not ctx.expression():
            self.semanticError(ctx, f"Constant '{name}' must be initialized with a value at declaration.")
        else:
            expr_type = self.visit(ctx.expression())
            expr_name = getattr(expr_type, 'name', str(expr_type)) if expr_type else None
            data_name = getattr(data_type, 'name', str(data_type)) if data_type else None
            
            if expr_name and data_name and expr_name != data_name:
                is_valid_null = (expr_name == f"{data_name}_null")
                if not is_valid_null:
                    self.semanticError(ctx, f"Cannot assign type '{expr_name}' to constant '{name}' of type '{data_name}'.")

        var_sym = VarSymbol(name=name, type=data_type, is_const=True)
        var_sym.var_decl_assign_nodes.append(ctx)
        self.symbol_table.define(var_sym)        
        return None
    
    def check_assignment_types(self, ctx, lhs_text, var_sym, lhs_type, rhs_type):
        """Helper function to run type-checking on any assignment."""
        if isinstance(lhs_type, ArrayType) and isinstance(rhs_type, ArrayType):
            if lhs_type.base_type.name != rhs_type.base_type.name:
                self.semanticError(ctx, f"Cannot assign array of '{rhs_type.base_type.name}' to array of '{lhs_type.base_type.name}'.")
            elif rhs_type.size > lhs_type.size:
                self.semanticError(ctx, f"Assigned array size ({rhs_type.size}) exceeds target array size ({lhs_type.size}).")
        elif isinstance(lhs_type, ArrayType) or isinstance(rhs_type, ArrayType):
            lhs_name = getattr(lhs_type, 'name', str(lhs_type)) if lhs_type else "unknown"
            rhs_name = getattr(rhs_type, 'name', str(rhs_type)) if rhs_type else "unknown"
            self.semanticError(ctx, f"Cannot assign type '{rhs_name}' to '{lhs_text}' of type '{lhs_name}'.")
        else:
            lhs_name = getattr(lhs_type, 'name', str(lhs_type)) if lhs_type else "unknown"
            rhs_name = getattr(rhs_type, 'name', str(rhs_type)) if rhs_type else "unknown"

            if lhs_name and rhs_name and lhs_name != rhs_name:
                base_lhs = lhs_name.replace("_null", "")
                base_rhs = rhs_name.replace("_null", "")
                
                is_valid_null_assign = (base_lhs == base_rhs) or (rhs_name == "null")

                is_implicit_cast = (base_lhs == "float" and base_rhs in ["int", "char"]) or (base_lhs == "int" and base_rhs == "char")
                
                if not (is_valid_null_assign or is_implicit_cast):
                    self.semanticError(ctx, f"Cannot assign type '{rhs_name}' to '{lhs_text}' of type '{lhs_name}'.")

            # Null state transition tracking
            old_type_name = var_sym.type.name if var_sym and hasattr(var_sym, 'type') else "unknown"
            
            if rhs_name and (rhs_name == "null" or rhs_name.endswith("_null")) and not old_type_name.endswith("_null"):
                base_type = lhs_name.replace('_null', '')
                resolved_null = self.symbol_table.resolve(f"{base_type}_null")
                if isinstance(var_sym, VarSymbol) and resolved_null:
                    var_sym.type = resolved_null
                    
            elif lhs_name and lhs_name.endswith("_null") and rhs_name != "null" and not rhs_name.endswith("_null"):
                resolved_type = self.symbol_table.resolve(lhs_name.replace("_null", ""))
                if isinstance(var_sym, VarSymbol) and resolved_type:
                    var_sym.type = resolved_type

    def visitAssignStat(self, ctx: C4ChineseParser.AssignStatContext):
        lhs_text = ctx.assignableVal().getText() 
        base_var_name = lhs_text.replace('^', '').split('[')[0].split('.')[0]
        var_sym = self.symbol_table.resolve(base_var_name)
        
        if not var_sym:
            self.semanticError(ctx, f"Cannot assign to undefined variable '{base_var_name}'.")
            return None
        
        if isinstance(var_sym, VarSymbol) and var_sym.is_const:
            self.semanticError(ctx, f"Cannot reassign to constant variable '{base_var_name}'.")

        self.is_lhs = True
        lhs_type = self.visit(ctx.assignableVal())
        self.is_lhs = False
        rhs_type = self.visit(ctx.expression())        
        self.check_assignment_types(ctx, lhs_text, var_sym, lhs_type, rhs_type)
        if '.' in lhs_text or '[' in lhs_text:
            if lhs_text not in var_sym.struct_assignments:
                var_sym.struct_assignments[lhs_text] = []
            var_sym.struct_assignments[lhs_text].append(ctx)
        else:
            var_sym.var_decl_assign_nodes.append(ctx)
        return None

    def visitStatPrint(self, ctx: C4ChineseParser.StatPrintContext):
        prev_lhs = self.is_lhs
        self.is_lhs = False
        
        self.visit(ctx.expression())
        
        self.is_lhs = prev_lhs
        return None
    
    def visitStatInput(self, ctx: C4ChineseParser.StatInputContext):
        for assignable_ctx in ctx.assignableVal():
            
            prev_lhs = self.is_lhs
            self.is_lhs = False 
            
            # 1. Visit the node to verify it exists and get its type...
            var_type = self.visit(assignable_ctx)
            
            # Restore the LHS flag
            self.is_lhs = prev_lhs
            
            # 2. Prevent inputting directly into massive complex types...
            if var_type is not None:
                if isinstance(var_type, ArrayType):
                    self.semanticError(assignable_ctx, "Cannot read input directly into an entire array. You must specify an index (e.g., arr[0]).")
                elif isinstance(var_type, StructTypeSymbol):
                    self.semanticError(assignable_ctx, f"Cannot read input directly into struct '{var_type.name}'. You must specify a field (e.g., struct.field).")
                    
        return None
    
    def visitAssignStatNoEnd(self, ctx: C4ChineseParser.AssignStatNoEndContext):
        lhs_text = ctx.assignableVal().getText() 
        base_var_name = lhs_text.replace('^', '').split('[')[0].split('.')[0]
        var_sym = self.symbol_table.resolve(base_var_name)

        if isinstance(var_sym, VarSymbol) and var_sym.is_const:
            self.semanticError(ctx, f"Cannot reassign to constant variable '{base_var_name}'.")

        self.is_lhs = True
        lhs_type = self.visit(ctx.assignableVal())
        self.is_lhs = False
        rhs_type = self.visit(ctx.expression())
        
        self.check_assignment_types(ctx, lhs_text, var_sym, lhs_type, rhs_type)
        return None
    
    # Note: We need to have an exception for varDecls in forLoops,
    # since their scope should be inside the block, not outside...
    def visitVarDeclFor(self, ctx):
        data_type = self.visit(ctx.dataType())
        name = self.visit(ctx.idWrapper())
        var_sym = VarSymbol(name=name, type=data_type, is_const=False)
        var_sym.var_decl_assign_nodes.append(ctx)
        return var_sym

    def visitForStat(self, ctx):
        self.symbol_table.enter_scope()
        if ctx.varDeclFor():
            forVar = self.visit(ctx.varDeclFor())
            self.symbol_table.define(forVar)
        elif ctx.assignStat():
            self.visit(ctx.assignStat())
        
        self.visit(ctx.assignStatNoEnd())
        
        self.visit(ctx.statement())

        self.symbol_table.exit_scope()

        return None
    
    def visitParamList(self, ctx):
        params = []
        for i in range(0, len(ctx.dataType())):
            data_type = self.visit(ctx.dataType(i))
            name = self.visit(ctx.idWrapper(i))
            
            param_sym = VarSymbol(name=name, type=data_type, is_const=False)
            
            param_sym.isparam = True 
            param_sym.var_decl_assign_nodes.append(ctx)
            
            params.append(param_sym)
            # self.symbol_table.define(param_sym)
        return params
    
    def visitArgList(self, ctx: C4ChineseParser.ArgListContext):
        # Evaluate each expression in the argument list and return their types...
        return [self.visit(expr) for expr in ctx.expression()]

    def visitMainFunc(self, ctx: C4ChineseParser.MainFuncContext):
        if ctx.dataType() is None and ctx.VOID() is None:
            return None

        # Check if return type is void...
        if ctx.VOID():
            self.semanticError(ctx, "Main function must return 'int', not 'void'.")
            return_type = self.symbol_table.resolve("int")
        else:
            # Check if return type is something other than int...
            return_type = self.visit(ctx.dataType())
            if return_type.name != "int":
                self.semanticError(ctx, f"Main function must return 'int', not '{return_type.name}'.")

        main_function = FunctionSymbol(
            name='main',
            return_type=return_type,
            parameters=self.visit(ctx.paramList()),
            parent_scope=self.symbol_table.current_scope 
        )

        self.symbol_table.define(main_function)
        self.symbol_table.enter_scope(main_function)
        
        # Set current function context...
        prev_func = self.current_function
        self.current_function = main_function
        
        guarantees_return = self.visit(ctx.funcContent())

        # Check the captured boolean instead of the old flag...
        if not guarantees_return:
             self.semanticError(ctx, "Main function must return a value of type 'int' across all paths.")

        self.current_function = prev_func

        self.symbol_table.exit_scope()

        return None
    
    def visitFuncRet(self, ctx: C4ChineseParser.FuncRetContext):
        return_type = self.visit(ctx.dataType())
        name = self.visit(ctx.idWrapper())
        params = self.visit(ctx.paramList())

        function = FunctionSymbol(
            name=name,
            return_type=return_type,
            parameters=params,
            parent_scope=self.symbol_table.current_scope
        )

        self.symbol_table.define(function)
        self.symbol_table.enter_scope(function)

        prev_func = self.current_function
        self.current_function = function

        guarantees_return = self.visit(ctx.funcContent())

        if not guarantees_return:
            self.semanticError(ctx, f"Function '{name}' expects a return type of '{return_type.name}' but is missing a guaranteed return statement across all paths.")

        self.current_function = prev_func
        self.symbol_table.exit_scope()
        
        return None

    def visitFuncVoid(self, ctx: C4ChineseParser.FuncVoidContext):
        return_type = self.symbol_table.resolve("void")
        name = self.visit(ctx.idWrapper())
        params = self.visit(ctx.paramList()) if ctx.paramList() else []

        function = FunctionSymbol(name, return_type, params, self.symbol_table.current_scope)
        self.symbol_table.define(function)
        self.symbol_table.enter_scope(function)

        prev_func = self.current_function
        self.current_function = function

        if ctx.funcContent():
            self.visit(ctx.funcContent())

        self.current_function = prev_func
        self.symbol_table.exit_scope()
        return None
    
    def visitReturnStat(self, ctx: C4ChineseParser.ReturnStatContext):
        if not self.current_function:
            self.semanticError(ctx, "Return statement found outside of a function.")
            return None

        expected_type = self.current_function.return_type.name

        if ctx.expression():
            actual_type = self.visit(ctx.expression())
            if expected_type == "void":
                self.semanticError(ctx, f"Void function '{self.current_function.name}' cannot return a value.")
            elif actual_type and expected_type != actual_type.name:
                # Check if it is returning the valid typed null...
                if actual_type.name != f"{expected_type}_null":
                    self.semanticError(ctx, f"Return type mismatch. Expected '{expected_type}', got '{actual_type.name}'.")
        else:
            if expected_type != "void":
                self.semanticError(ctx, f"Function '{self.current_function.name}' must return a value of type '{expected_type}'.")

        return True
    def visitFuncCall(self, ctx: C4ChineseParser.FuncCallContext):
        # 1. Get the function name and resolve it from the symbol table...
        func_name = self.visit(ctx.idWrapper())
        func_sym = self.symbol_table.resolve(func_name)

        # 2. Check if it actually exists and is a function...
        if not func_sym:
            self.semanticError(ctx, f"Function '{func_name}' is not defined.")
            return None
        if not isinstance(func_sym, FunctionSymbol):
            self.semanticError(ctx, f"Identifier '{func_name}' is not a function.")
            return None

        # 3. Evaluate the provided arguments...
        actual_arg_types = []
        if ctx.argList():
            actual_arg_types = self.visit(ctx.argList())

        expected_params = func_sym.parameters

        # 4. Check if the Argument COUNT matches...
        if len(actual_arg_types) != len(expected_params):
            self.semanticError(ctx, f"Function '{func_name}' expects {len(expected_params)} arguments, but got {len(actual_arg_types)}.")
            return func_sym.return_type # Return the expected type anyway to prevent cascading errors

        # 5. Check if the Argument TYPES match...
        for i, (actual_type, param_sym) in enumerate(zip(actual_arg_types, expected_params)):
            expected_type = param_sym.type
            
            actual_name = getattr(actual_type, 'name', str(actual_type)) if actual_type else "unknown"
            expected_name = getattr(expected_type, 'name', str(expected_type)) if expected_type else "unknown"

            # 1. Array parameter matching
            if isinstance(actual_type, ArrayType) and isinstance(expected_type, ArrayType):
                if actual_type.base_type.name != expected_type.base_type.name:
                    self.semanticError(ctx, f"Argument {i+1} of '{func_name}': Expected array of '{expected_type.base_type.name}', got array of '{actual_type.base_type.name}'.")
                    
            # 2. Prevent mixing arrays and primitives...
            elif isinstance(actual_type, ArrayType) or isinstance(expected_type, ArrayType):
                self.semanticError(ctx, f"Argument {i+1} of '{func_name}': Type mismatch. Expected '{expected_name}', got '{actual_name}'.")

            # 3. Primitive parameter matching
            elif actual_name != expected_name:
                base_expected = expected_name.replace("_null", "")
                
                is_valid_null = (actual_name == "null") or (actual_name == f"{base_expected}_null")
                is_implicit_cast = (base_expected == "float" and actual_name in ["int", "char"]) or (base_expected == "int" and actual_name == "char")
                
                if not (is_valid_null or is_implicit_cast):
                    self.semanticError(ctx, f"Argument {i+1} of '{func_name}': Type mismatch. Expected '{expected_name}', got '{actual_name}'.")
               
        # 6. Return the function's return type so expressions work...
        return func_sym.return_type
    def visitFuncContent(self, ctx: C4ChineseParser.FuncContentContext):
        guarantees_return = False
        
        # A function block guarantees a return if any of its statements do...
        for child in ctx.children:
            result = self.visit(child)
            if result is True:
                guarantees_return = True
                
        return guarantees_return
    
    def visitIfStat(self, ctx: C4ChineseParser.IfStatContext):
        # 1. Type check the boolean expression...
        self.visit(ctx.expression())
        
        # 2. Check the main 'ruguo' block...
        if_returns = self.visit(ctx.statement()) == True
        
        # 3. Check the 'xiayigeruguo' / 'xiayige' blocks...
        else_returns = False
        if ctx.elifList():
            else_returns = self.visit(ctx.elifList()) == True
            
        # 4. Only guaranteed if ALL branches return...
        return if_returns and else_returns

    def visitElifList(self, ctx: C4ChineseParser.ElifListContext):
        if ctx.ELIF():
            self.visit(ctx.expression())
            
            elif_returns = self.visit(ctx.statement()) == True
            
            rest_returns = False
            if ctx.elifList():
                rest_returns = self.visit(ctx.elifList()) == True
                
            return elif_returns and rest_returns
            
        elif ctx.ELSE():
            # It's an else block, just check its statement...
            return self.visit(ctx.statement()) == True
            
        return False

    def visitStatBlock(self, ctx: C4ChineseParser.StatBlockContext):
        self.symbol_table.enter_scope()
        
        guarantees_return = False
        for statement in ctx.statement():
            if self.visit(statement) is True:
                guarantees_return = True
                
        self.symbol_table.exit_scope()
        
        return guarantees_return
    
    def visitTypedefItem(self, ctx):
        if ctx.dataType():
            actual_type = self.visit(ctx.dataType())
        elif ctx.recordDecl():
            actual_type = self.visit(ctx.recordDecl())
        
        name = self.visit(ctx.idWrapper())

        typedef = TypedefSymbol(name=name, actual=actual_type)
        self.symbol_table.current_scope.define(typedef)

        return typedef

    # Null Checking
    def visitNullExp(self, ctx: C4ChineseParser.NullExpContext):
        return self.symbol_table.resolve("null")
    
    def visitNumExp(self, ctx: C4ChineseParser.NumExpContext):
        types = [self.visit(child) for child in ctx.numExp1()]
        
        if len(types) > 1:
            type_names = []
            for t in types:
                if t:
                    if t.name in ["null", "int_null", "float_null"]:
                        self.semanticError(ctx, "Cannot perform addition or subtraction with 'null'.")
                        return self.symbol_table.resolve("int_null")
                    type_names.append(t.name)
            
            if "string" in type_names:
                for t_name in type_names:
                    if t_name != "string":
                        self.semanticError(ctx, "Cannot mix string and numeric types in addition.")
                        return self.symbol_table.resolve("string_null")
                        
                for i in range(1, len(ctx.numExp1())):
                    op_type = ctx.getChild(2 * i - 1).getSymbol().type
                    if op_type == C4ChineseParser.SUB:
                        self.semanticError(ctx, "Cannot perform subtraction (-) on strings.")
                        return self.symbol_table.resolve("string_null")
                        
                return self.symbol_table.resolve("string")

            # Math type promotion 
            if "float" in type_names:
                return self.symbol_table.resolve("float")
            else:
                # If there are multiple operands (math is happening), chars promote to ints...
                return self.symbol_table.resolve("int")
                
        return types[0] if types else None

    def visitNumExp1(self, ctx: C4ChineseParser.NumExp1Context):
        types = [self.visit(child) for child in ctx.numExp2()]
        
        if len(types) > 1:
            type_names = []
            for t in types:
                if t:
                    if t.name in ["null", "int_null", "float_null"]:
                        self.semanticError(ctx, "Cannot perform multiplication, division, or modulo with 'null'.")
                        return self.symbol_table.resolve("int_null")
                    type_names.append(t.name)
            
            if "string" in type_names:
                self.semanticError(ctx, "Cannot perform multiplication, division, or modulo on strings.")
                return self.symbol_table.resolve("string_null")
            
            # Math type promotion 
            if "float" in type_names:
                return self.symbol_table.resolve("float")
            else:
                return self.symbol_table.resolve("int")
                
        return types[0] if types else None

    def visitStrExp(self, ctx: C4ChineseParser.StrExpContext):
        types = [self.visit(child) for child in ctx.strBase()]
        if len(types) > 1:
            for t in types:
                if t and (t.name == "null" or t.name == "string_null"):
                    self.semanticError(ctx, "Cannot concatenate strings with 'null'.")
                    return self.symbol_table.resolve("string_null")
        return types[0] if types else None
    
    def visitValidString(self, ctx: C4ChineseParser.ValidStringContext):
        return self.symbol_table.resolve("string")

    def visitValidFloat(self, ctx: C4ChineseParser.ValidFloatContext):
        return self.symbol_table.resolve("float")
    
    def visitValidInt(self, ctx):
        return self.symbol_table.resolve("int")
    
    def visitValidChar(self, ctx):
        return self.symbol_table.resolve("char")
    
    def visitValidBool(self, ctx):
        return self.symbol_table.resolve("bool")
    
    def visitValidNull(self, ctx):
        return self.symbol_table.resolve("null")

    def visitNumExp2(self, ctx: C4ChineseParser.NumExp2Context):
        # Need to check if intWrapper exists in the context...
        if hasattr(ctx, 'intWrapper') and ctx.intWrapper():
            return self.symbol_table.resolve("int")
        elif ctx.LT_INT():
             return self.symbol_table.resolve("int")
        
        # Address-of (&variable, &arr, &struct.field)...
        if ctx.REF():
            # visitRefVal does all the heavy lifting to find the base type!
            var_type = self.visit(ctx.refVal())
            
            if not var_type:
                return None
                
            # Wrap the resolved type in a pointer and return it
            return PointerType(base_type=var_type)

        # Dereference (^variable) handled by deRefVal rule usually, 
        # but check if numExp2 has it directly or via deRefVal rule..
        if ctx.deRefVal():
            return self.visit(ctx.deRefVal())

        if ctx.INC() or ctx.DEC():
            # 1. Treat this as an assignment (LHS) so unused vars optimizer knows it's a write...
            self.is_lhs = True
            var_type = self.visit(ctx.numRef())
            self.is_lhs = False
            
            # 2. Check if the type is numeric...
            var_name = getattr(var_type, 'name', 'unknown')
            if var_name not in ['int', 'float']:
                self.semanticError(ctx, f"Cannot increment/decrement non-numeric type '{var_name}'.")
                
            # 3. Check if they are trying to increment a constant...
            base_name = ctx.numRef().getText().split('[')[0].split('.')[0]
            var_sym = self.symbol_table.resolve(base_name)
            if isinstance(var_sym, VarSymbol) and var_sym.is_const:
                self.semanticError(ctx, f"Cannot increment/decrement constant variable '{base_name}'.")
                
            return var_type
            
        # Explicit check for function calls...
        if ctx.funcCall():
            return self.visit(ctx.funcCall())

        return self.visitChildren(ctx)

    def visitDeRefVal(self, ctx: C4ChineseParser.DeRefValContext):
        # deRefVal : DE_REF deRefVal | DE_REF pointerId
        
        # Case 1: Recursive dereference "^^ptr" 
        if ctx.deRefVal():
            base_type = self.visit(ctx.deRefVal())
            if isinstance(base_type, PointerType):
                return base_type.base_type
            elif isinstance(base_type, VarSymbol):
                 # Case where we got a symbol back instead of type, unpack it...
                 if isinstance(base_type.type, PointerType):
                     return base_type.type.base_type
            
            # If we got here, it's invalid...
            if base_type:
                 name = getattr(base_type, 'name', str(base_type))
                 self.semanticError(ctx, f"Cannot dereference non-pointer type '{name}'.")
            return None
                
        # Case 2: Base dereference "^ptr"
        if ctx.refVal():
            name = self.visit(ctx.refVal().idWrapper())
            var_sym = self.symbol_table.resolve(name)
            
            if not var_sym:
                self.semanticError(ctx, f"Cannot dereference undefined variable '{name}'.")
                return None
            
            # Pointers MUST be read to find the memory address they point to, 
            # even if they are on the left side of an assignment...
            if isinstance(var_sym, VarSymbol):
                var_sym.rhs_counter += 1    
                
            var_type = var_sym.type if isinstance(var_sym, VarSymbol) else var_sym
            
            if isinstance(var_type, PointerType):
                return var_type.base_type
            else:
                self.semanticError(ctx, f"Cannot dereference non-pointer variable '{name}' of type '{getattr(var_type, 'name', 'unknown')}'.")
                return None

    def visitPointerId(self, ctx: C4ChineseParser.PointerIdContext):
        return self.visitChildren(ctx)

    def visitBoolExp(self, ctx: C4ChineseParser.BoolExpContext):
        # boolExp1 (OR boolExp1)*
        # Visit all children so variables get counted...
        types = [self.visit(child) for child in ctx.boolExp1()]
        
        if len(types) > 1:
            return self.symbol_table.resolve("bool")
        
        return types[0] if types else None

    def visitBoolExp1(self, ctx: C4ChineseParser.BoolExp1Context):
        # boolExp2 (AND boolExp2)*
        # Visit all children...
        types = [self.visit(child) for child in ctx.boolExp2()]
        
        if len(types) > 1:
            return self.symbol_table.resolve("bool")
            
        return types[0] if types else None

    def visitBoolExp2(self, ctx: C4ChineseParser.BoolExp2Context):
        # 1. Check for null comparisons...
        if ctx.nullExp():
            self.visitChildren(ctx) # Ensure we visit the variable being compared to null
            return self.symbol_table.resolve("bool")

        # 2. numExp (EQ | NEQ) numExp...
        if len(ctx.numExp()) == 2:
            left = self.visit(ctx.numExp(0))
            right = self.visit(ctx.numExp(1))
            return self.symbol_table.resolve("bool")
        
        # 3. strExp (EQ | NEQ) strExp...
        if len(ctx.strExp()) == 2:
            left = self.visit(ctx.strExp(0))
            right = self.visit(ctx.strExp(1))
            return self.symbol_table.resolve("bool")
        
        # 4. boolExp3 ( (EQ | NEQ) boolExp3 )* ...
        if len(ctx.boolExp3()) > 1:
            for child in ctx.boolExp3():
                self.visit(child)
            return self.symbol_table.resolve("bool")
            
        return self.visit(ctx.boolExp3(0))
    def visitBoolExp3(self, ctx: C4ChineseParser.BoolExp3Context):
        # 1. numExp (LT | GT | LTE | GTE) numExp...
        if len(ctx.numExp()) == 2:
            left = self.visit(ctx.numExp(0))
            right = self.visit(ctx.numExp(1))
            
            # Check if left and right are actually numbers...
            # if not (left.name in ['int', 'float'] and right.name in ['int', 'float']):
            #     self.semanticError(ctx, "Comparison requires numeric types.")

            if (left and (left.name == "null" or left.name.endswith("_null"))) or (right and (right.name == "null" or right.name.endswith("_null"))):
                self.semanticError(ctx, "Cannot compare 'null' with numeric types.")
                return self.symbol_table.resolve("bool_null")

            # when doing comparison ensure that both operands additionally, ensure that only int, float, string, char pairs are allowed (no nulls, no bools)...TOTODO
            
            if left and right:
                valid_comparison = (
                    (left.name in ['int', 'float', 'char'] and right.name in ['int', 'float', 'char']) 
                )
                if not valid_comparison:
                    self.semanticError(ctx, f"Invalid comparison between '{left.name}' and '{right.name}'.")
                    return self.symbol_table.resolve("bool_null")

            return self.symbol_table.resolve("bool")
        
        # 2. strExp (LT | GT | LTE | GTE) strExp
        if len(ctx.strExp()) == 2:
            left = self.visit(ctx.strExp(0))
            right = self.visit(ctx.strExp(1))
            
            if (left and (left.name == "null" or left.name.endswith("_null"))) or (right and (right.name == "null" or right.name.endswith("_null"))):
                self.semanticError(ctx, "Cannot compare 'null' with string types.")
                return self.symbol_table.resolve("bool_null")

            if left and right:
                if left.name != 'string' or right.name != 'string':
                     self.semanticError(ctx, f"Invalid comparison between '{left.name}' and '{right.name}'.")
                     return self.symbol_table.resolve("bool_null")
            
            return self.symbol_table.resolve("bool")

        # 3. boolExp4 
        if ctx.boolExp4():
            return self.visit(ctx.boolExp4())
        return None

    def visitBoolExp4(self, ctx: C4ChineseParser.BoolExp4Context):
        if ctx.LT_BOOL():
            return self.symbol_table.resolve("bool")
        return self.visitChildren(ctx)

    def visitRefVal(self, ctx: C4ChineseParser.RefValContext):
        name = self.visit(ctx.idWrapper())
        sym = self.symbol_table.resolve(name)
        
        if not sym:
            self.semanticError(ctx, f"Variable '{name}' is not defined.")
            return None
        
        # Increment rhs_counter if we are not on the left side of an assignment...
        if not self.is_lhs:
            sym.rhs_counter += 1
            if isinstance(sym, VarSymbol):
                sym.struct_reads.add(ctx.getText())

        # Get the base type (e.g., StructTypeSymbol, ArrayType, or PrimitiveTypeSymbol)...
        current_type = sym.type if isinstance(sym, VarSymbol) else sym
        
        # If there is no chained access (like .id or [0]), just return the base type...
        if not ctx.refValPrime() or ctx.refValPrime().getText() == "":
            return current_type
            
        # If there is chained access, traverse down the chain...
        return self._resolve_ref_chain(current_type, ctx.refValPrime())

    def _resolve_ref_chain(self, current_type, ctx_prime: C4ChineseParser.RefValPrimeContext):
        if not ctx_prime or ctx_prime.getText() == "":
            return current_type
            
        # CASE 1: DOT ACCESS (e.g., .id)
        if ctx_prime.DOT():
            if not isinstance(current_type, StructTypeSymbol):
                self.semanticError(ctx_prime, f"Type '{getattr(current_type, 'name', 'unknown')}' is not a record/struct.")
                return None
                
            # Grab the right side of the dot...
            ref_val_ctx = ctx_prime.refVal()
            member_name = self.visit(ref_val_ctx.idWrapper())
            
            if member_name not in current_type.symbols:
                self.semanticError(ctx_prime, f"Record '{current_type.name}' has no member named '{member_name}'.")
                return None
                
            member_sym = current_type.symbols[member_name]
            
           # Increment rhs_counter if field is accessed and we are not on the left side of an assignment...
            if not self.is_lhs:
                member_sym.rhs_counter += 1

            next_type = member_sym.type if isinstance(member_sym, VarSymbol) else member_sym
            
            # Handle inner chains (e.g., the [0] in .grades[0])...
            if ref_val_ctx.refValPrime() and ref_val_ctx.refValPrime().getText() != "":
                next_type = self._resolve_ref_chain(next_type, ref_val_ctx.refValPrime())
                
            # Handle outer chains (e.g., .id.next)...
            if ctx_prime.refValPrime() and ctx_prime.refValPrime().getText() != "":
                next_type = self._resolve_ref_chain(next_type, ctx_prime.refValPrime())
                
            return next_type
            
        # CASE 2: ARRAY ACCESS (e.g., [0])
        elif ctx_prime.LBAR():
            if not isinstance(current_type, ArrayType):
                self.semanticError(ctx_prime, f"Cannot index into non-array type '{getattr(current_type, 'name', 'unknown')}'.")
                return None
                
            # Validate that the index is an integer...
            idx_type = self.visit(ctx_prime.numExp())
            if idx_type and idx_type.name != "int":
                self.semanticError(ctx_prime, "Array index must be an integer (hao).")
                
            # Unwrap the array to get its base type...
            next_type = current_type.base_type
            
            # Continue the chain if there is more (e.g., [0].name)...
            if ctx_prime.refValPrime() and ctx_prime.refValPrime().getText() != "":
                next_type = self._resolve_ref_chain(next_type, ctx_prime.refValPrime())
                
            return next_type
            
        return current_type


    def visitErrorID(self, ctx:C4ChineseParser.ErrorIDContext):
        node = ctx.ERROR_ID()
        token = node.getSymbol()
        line = token.line
        column = token.column  
        original_text = token.text
        corrected_text = "x" + original_text

        print(f"{Colors.RED}{Colors.BOLD}Lexer Error{Colors.RESET} at Line {Colors.YELLOW}{line}{Colors.RESET}, Column {Colors.YELLOW}{column}{Colors.RESET}: "
              f"Invalid ID '{Colors.RED}{original_text}{Colors.RESET}'. "
              f"Recommend fix: '{Colors.GREEN}{corrected_text}{Colors.RESET}'")
        
        return corrected_text
    
    def visitErrorFloat(self, ctx:C4ChineseParser.ErrorFloatContext):
        node = ctx.ERROR_FLOAT()
        token = node.getSymbol()
        line = token.line
        column = token.column
        original_text = token.text
        
        parts = original_text.split('.')
        corrected_text = parts[0] + '.' + "".join(parts[1:])
        
        print(f"{Colors.RED}{Colors.BOLD}Lexer Error{Colors.RESET} at Line {Colors.YELLOW}{line}{Colors.RESET}, Column {Colors.YELLOW}{column}{Colors.RESET}: "
              f"Malformed Float '{Colors.RED}{original_text}{Colors.RESET}'. "
              f"Recommend fix: '{Colors.GREEN}{corrected_text}{Colors.RESET}'")
        
        return corrected_text

    def visitErrorString(self, ctx:C4ChineseParser.ErrorStringContext):
        node = ctx.ERROR_STRING()
        token = node.getSymbol()
        line = token.line
        column = token.column
        original_text = token.text
        corrected_text = original_text + '"'
        
        print(f"{Colors.RED}{Colors.BOLD}Lexer Error{Colors.RESET} at Line {Colors.YELLOW}{line}{Colors.RESET}, Column {Colors.YELLOW}{column}{Colors.RESET}: "
              f"Unclosed String {Colors.RED}{original_text}{Colors.RESET}. "
              f"Recommend fix: Append closing quote '{Colors.GREEN}\"{Colors.RESET}'")
        
        return corrected_text

    def visitErrorChar(self, ctx:C4ChineseParser.ErrorCharContext):
        node = ctx.ERROR_CHAR()
        token = node.getSymbol()
        line = token.line
        column = token.column
        original_text = token.text
        corrected_text = original_text + "'"
        
        print(f"{Colors.RED}{Colors.BOLD}Lexer Error{Colors.RESET} at Line {Colors.YELLOW}{line}{Colors.RESET}, Column {Colors.YELLOW}{column}{Colors.RESET}: "
              f"Unclosed character literal '{Colors.RED}{original_text}{Colors.RESET}'. "
              f"Recommend fix: '{Colors.GREEN}{corrected_text}{Colors.RESET}'")
        
        return corrected_text

    def visitErrorChar2(self, ctx:C4ChineseParser.ErrorChar2Context):
        node = ctx.ERROR_CHAR_2()
        token = node.getSymbol()
        line = token.line
        column = token.column
        original_text = token.text
        
        content = original_text.strip("'")
        if len(content) > 0:
            corrected_text = f"'{content[0]}'"
        else:
            corrected_text = "' '"
            
        print(f"{Colors.RED}{Colors.BOLD}Lexer Error{Colors.RESET} at Line {Colors.YELLOW}{line}{Colors.RESET}, Column {Colors.YELLOW}{column}{Colors.RESET}: "
              f"Char literal too long '{Colors.RED}{original_text}{Colors.RESET}'. "
              f"Recommend fix: '{Colors.GREEN}{corrected_text}{Colors.RESET}'")
        
        return corrected_text

    def visitPanicMode(self, ctx: C4ChineseParser.PanicModeContext):
        expression = ctx.getText()
        token = ctx.start
        print(f"{Colors.RED}{Colors.BOLD}Parser Error{Colors.RESET} at Line {Colors.YELLOW}{token.line}{Colors.RESET}, Column {Colors.YELLOW}{token.column}{Colors.RESET}: "
              f"Invalid expression '{expression.strip()}' found.")
        self.parser_error_count += 1
        return None

    def semanticError(self, ctx, message: str):
        self.semantic_error_count += 1
        token = ctx.start
        print(f"{Colors.RED}{Colors.BOLD}Semantic Error{Colors.RESET} at Line {Colors.YELLOW}{token.line}{Colors.RESET}, Column {Colors.YELLOW}{token.column}{Colors.RESET}: {message}")
        