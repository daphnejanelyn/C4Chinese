from C4ChineseParser import C4ChineseParser
from C4ChineseParserVisitor import C4ChineseParserVisitor
from antlr4.tree.Tree import TerminalNodeImpl
from antlr4.Token import CommonToken

class ConstPropagationOptimizer(C4ChineseParserVisitor):

    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BOLD = '\033[1m'
    RESET = '\033[0m'
    MAGENTA = '\033[95m'

    def __init__(self, symbol_table):
        self.symbol_table = symbol_table
        self.symbol_table.return_to_global_scope()

    def visitMainFunc(self, ctx: C4ChineseParser.MainFuncContext):
        
        self.symbol_table.enter_scope_by_name("main")
        self.visit(ctx.funcContent())
        self.symbol_table.exit_scope()

        return None
    
    def visitFuncRet(self, ctx: C4ChineseParser.FuncRetContext):

        name = ctx.idWrapper().getText()
        self.symbol_table.enter_scope_by_name(name)
        self.visit(ctx.funcContent())
        self.symbol_table.exit_scope()
        
        return None

    def visitFuncVoid(self, ctx: C4ChineseParser.FuncVoidContext):
        
        name = ctx.idWrapper().getText()
        self.symbol_table.enter_scope_by_name(name)
        self.visit(ctx.funcContent())
        self.symbol_table.exit_scope()

        return None
    
    def visitStatBlock(self, ctx: C4ChineseParser.StatBlockContext):

        self.symbol_table.enter_next_block()
        for statement in ctx.statement():
            self.visit(statement)
        self.symbol_table.exit_scope()
        
        return None
    
    def visitConstDecl(self, ctx):
        name = ctx.idWrapper().getText()
        expr_val = self.visit(ctx.expression())
        
        symbol = self.symbol_table.resolve(name)

        if isinstance(expr_val, float) and symbol.type.name == 'int':
            expr_val = int(expr_val)

        symbol.set_val(expr_val)


        # --- HIERARCHICAL CONSTANT PROPAGATION ---
        
        if expr_val is not None:
            expr_ctx = ctx.expression()
            
            # 1. Handle Boolean Replacement
            # (Must go before int, because isinstance(True, int) is True in Python)

            if isinstance(expr_val, bool):
                new_token = CommonToken(type=C4ChineseParser.LT_BOOL)
                new_token.text = 'zhen' if expr_val else 'buzhen'
                new_leaf = TerminalNodeImpl(new_token)
                
                # Instantiate the 5 levels of boolean contexts...
                bool_exp4 = C4ChineseParser.BoolExp4Context(None, None)
                bool_exp3 = C4ChineseParser.BoolExp3Context(None, None)
                bool_exp2 = C4ChineseParser.BoolExp2Context(None, None)
                bool_exp1 = C4ChineseParser.BoolExp1Context(None, None)
                bool_exp  = C4ChineseParser.BoolExpContext(None, None)
                
                # Wire bottom-up...
                new_leaf.parentCtx = bool_exp4
                bool_exp4.children = [new_leaf]
                
                bool_exp4.parentCtx = bool_exp3
                bool_exp3.children = [bool_exp4]
                
                bool_exp3.parentCtx = bool_exp2
                bool_exp2.children = [bool_exp3]
                
                bool_exp2.parentCtx = bool_exp1
                bool_exp1.children = [bool_exp2]
                
                bool_exp1.parentCtx = bool_exp
                bool_exp.children = [bool_exp1]
                
                bool_exp.parentCtx = expr_ctx
                expr_ctx.children = [bool_exp]

            # 2. Handle Integer Replacement
            elif isinstance(expr_val, int):
                new_token = CommonToken(type=C4ChineseParser.LT_INT)
                new_token.text = str(expr_val)
                new_leaf = TerminalNodeImpl(new_token)
                
                num_exp2 = C4ChineseParser.NumExp2Context(None, None)
                num_exp1 = C4ChineseParser.NumExp1Context(None, None)
                num_exp  = C4ChineseParser.NumExpContext(None, None)
                
                new_leaf.parentCtx = num_exp2
                num_exp2.children = [new_leaf]
                
                num_exp2.parentCtx = num_exp1
                num_exp1.children = [num_exp2]
                
                num_exp1.parentCtx = num_exp
                num_exp.children = [num_exp1]
                
                num_exp.parentCtx = expr_ctx
                expr_ctx.children = [num_exp]
                
            # 3. Handle Float Replacement
            elif isinstance(expr_val, float):

                new_token = CommonToken(type=C4ChineseParser.LT_FLOAT)
                new_token.text = str(expr_val)
                new_leaf = TerminalNodeImpl(new_token)
                
                float_wrap = C4ChineseParser.FloatWrapperContext(None, None)
                num_exp2 = C4ChineseParser.NumExp2Context(None, None)
                num_exp1 = C4ChineseParser.NumExp1Context(None, None)
                num_exp  = C4ChineseParser.NumExpContext(None, None)
                
                new_leaf.parentCtx = float_wrap
                float_wrap.children = [new_leaf]
                
                float_wrap.parentCtx = num_exp2
                num_exp2.children = [float_wrap]
                
                num_exp2.parentCtx = num_exp1
                num_exp1.children = [num_exp2]
                
                num_exp1.parentCtx = num_exp
                num_exp.children = [num_exp1]
                
                num_exp.parentCtx = expr_ctx
                expr_ctx.children = [num_exp]

            # 4. Handle String Replacement
            elif isinstance(expr_val, str):

                new_token = CommonToken(type=C4ChineseParser.LT_STR)
                new_token.text = f'"{expr_val}"' # Add quotes back
                new_leaf = TerminalNodeImpl(new_token)
                
                str_wrap = C4ChineseParser.StringWrapperContext(None, None)
                str_base = C4ChineseParser.StrBaseContext(None, None)
                str_exp  = C4ChineseParser.StrExpContext(None, None)
                
                new_leaf.parentCtx = str_wrap
                str_wrap.children = [new_leaf]
                
                str_wrap.parentCtx = str_base
                str_base.children = [str_wrap]
                
                str_base.parentCtx = str_exp
                str_exp.children = [str_base]
                
                str_exp.parentCtx = expr_ctx
                expr_ctx.children = [str_exp]

        return None

    def visitVarDecl(self, ctx):
        name = ctx.idWrapper().getText()

        if ctx.expression():
            expr_val = self.visit(ctx.expression())
            symbol = self.symbol_table.resolve(name)


            if isinstance(expr_val, float) and symbol.type.name == 'int':
                expr_val = int(expr_val)

            # Note: Remove if needed.
            symbol.set_val(expr_val)

            # --- HIERARCHICAL CONSTANT PROPAGATION ---
            
            if expr_val is not None:
                expr_ctx = ctx.expression()

                # 1. Handle Boolean Replacement
                # (Must go before int, because isinstance(True, int) is True in Python)
                if isinstance(expr_val, bool):
                    new_token = CommonToken(type=C4ChineseParser.LT_BOOL)
                    new_token.text = 'zhen' if expr_val else 'buzhen'
                    new_leaf = TerminalNodeImpl(new_token)
                    
                    # Instantiate the 5 levels of boolean contexts...
                    bool_exp4 = C4ChineseParser.BoolExp4Context(None, None)
                    bool_exp3 = C4ChineseParser.BoolExp3Context(None, None)
                    bool_exp2 = C4ChineseParser.BoolExp2Context(None, None)
                    bool_exp1 = C4ChineseParser.BoolExp1Context(None, None)
                    bool_exp  = C4ChineseParser.BoolExpContext(None, None)
                    
                    # Wire bottom-up...
                    new_leaf.parentCtx = bool_exp4
                    bool_exp4.children = [new_leaf]
                    
                    bool_exp4.parentCtx = bool_exp3
                    bool_exp3.children = [bool_exp4]
                    
                    bool_exp3.parentCtx = bool_exp2
                    bool_exp2.children = [bool_exp3]
                    
                    bool_exp2.parentCtx = bool_exp1
                    bool_exp1.children = [bool_exp2]
                    
                    bool_exp1.parentCtx = bool_exp
                    bool_exp.children = [bool_exp1]
                    
                    bool_exp.parentCtx = expr_ctx
                    expr_ctx.children = [bool_exp]

                # 2. Handle Integer Replacement
                elif isinstance(expr_val, int):
                    new_token = CommonToken(type=C4ChineseParser.LT_INT)
                    new_token.text = str(expr_val)
                    new_leaf = TerminalNodeImpl(new_token)
                    
                    num_exp2 = C4ChineseParser.NumExp2Context(None, None)
                    num_exp1 = C4ChineseParser.NumExp1Context(None, None)
                    num_exp  = C4ChineseParser.NumExpContext(None, None)
                    
                    new_leaf.parentCtx = num_exp2
                    num_exp2.children = [new_leaf]
                    
                    num_exp2.parentCtx = num_exp1
                    num_exp1.children = [num_exp2]
                    
                    num_exp1.parentCtx = num_exp
                    num_exp.children = [num_exp1]
                    
                    num_exp.parentCtx = expr_ctx
                    expr_ctx.children = [num_exp]
                    
                # 3. Handle Float Replacement
                elif isinstance(expr_val, float):
                    new_token = CommonToken(type=C4ChineseParser.LT_FLOAT)
                    new_token.text = str(expr_val)
                    new_leaf = TerminalNodeImpl(new_token)
                    
                    float_wrap = C4ChineseParser.FloatWrapperContext(None, None)
                    num_exp2 = C4ChineseParser.NumExp2Context(None, None)
                    num_exp1 = C4ChineseParser.NumExp1Context(None, None)
                    num_exp  = C4ChineseParser.NumExpContext(None, None)
                    
                    new_leaf.parentCtx = float_wrap
                    float_wrap.children = [new_leaf]
                    
                    float_wrap.parentCtx = num_exp2
                    num_exp2.children = [float_wrap]
                    
                    num_exp2.parentCtx = num_exp1
                    num_exp1.children = [num_exp2]
                    
                    num_exp1.parentCtx = num_exp
                    num_exp.children = [num_exp1]
                    
                    num_exp.parentCtx = expr_ctx
                    expr_ctx.children = [num_exp]

                # 4. Handle String Replacement
                elif isinstance(expr_val, str):
                    new_token = CommonToken(type=C4ChineseParser.LT_STR)
                    new_token.text = f'"{expr_val}"' # Add quotes back
                    new_leaf = TerminalNodeImpl(new_token)
                    
                    str_wrap = C4ChineseParser.StringWrapperContext(None, None)
                    str_base = C4ChineseParser.StrBaseContext(None, None)
                    str_exp  = C4ChineseParser.StrExpContext(None, None)
                    
                    new_leaf.parentCtx = str_wrap
                    str_wrap.children = [new_leaf]
                    
                    str_wrap.parentCtx = str_base
                    str_base.children = [str_wrap]
                    
                    str_base.parentCtx = str_exp
                    str_exp.children = [str_base]
                    
                    str_exp.parentCtx = expr_ctx
                    expr_ctx.children = [str_exp]

        return None
    
    def visitAssignStat(self, ctx):
        if ctx.assignableVal().deRefVal():
            self.visit(ctx.expression())
            return None
        
        name = ctx.assignableVal().getText()
        expr_val = self.visit(ctx.expression())

        if ctx.expression():
            # Assuming 'name' is the full string like "s1.grades.grades"
            parts = name.split('.')

            # 1. Resolve the base variable (e.g., 's1')
            # Strip out array indices in case it's something like s1[0].grades...
            base_var_name = parts[0].split('[')[0]
            current_symbol = self.symbol_table.resolve(base_var_name)

            if not current_symbol:
                raise Exception(f"Undefined variable: {base_var_name}")

            # This holds the type as a string (e.g., 'StudentRecord')...
            current_type_name = current_symbol.type 

            # 2. Iterate through the rest of the chain (e.g., ['grades', 'grades'])...
            for part in parts[1:]:
                # Strip array access from the field name (e.g., arr[10] -> arr)...
                field_name = part.split('[')[0]
                
                # Strip array brackets from the TYPE before looking up the struct definition
                # (e.g., 'OtherStruct[10]' -> 'OtherStruct')...
                
                struct_base_type = current_type_name.name.split('[')[0]
                
                # Resolve the struct's definition using the clean base type...
                struct_def = self.symbol_table.resolve(struct_base_type)
                
                #self.symbol_table.print_contents()

                if not struct_def:
                    raise Exception(f"Type {struct_base_type} is not defined or is not a struct.")
                
                # Find the field inside the struct definition...
                field_symbol = None
                if hasattr(struct_def, 'resolve'):
                    
                    field_symbol = struct_def.resolve(field_name)
                else:
                    for sym in struct_def.symbols:
                        if sym.name == field_name:
                            field_symbol = sym
                            break
                            
                if not field_symbol:
                    raise Exception(f"Struct {struct_base_type} has no member named '{field_name}'")
                    
                # Update the running type for the next iteration
                # This might be another array like 'int[5]', which is fine because 
                # the next loop will strip it, or the final check will strip it.
                current_type_name = field_symbol.type

            # 3. Final Evaluation
            # current_type_name is now 'int[10]'
            # Check if the base type (stripping array brackets) is 'int'
            final_base_type = current_type_name.name.split('[')[0] 

            if isinstance(expr_val, float) and final_base_type == 'int':
                expr_val = int(expr_val)

            # Note: Remove if needed.
            current_symbol.set_val(expr_val)

            # --- HIERARCHICAL CONSTANT PROPAGATION ---
            
            if expr_val is not None:
                expr_ctx = ctx.expression()

                # 1. Handle Boolean Replacement
                # (Must go before int, because isinstance(True, int) is True in Python)
                if isinstance(expr_val, bool):
                    new_token = CommonToken(type=C4ChineseParser.LT_BOOL)
                    new_token.text = 'zhen' if expr_val else 'buzhen'
                    new_leaf = TerminalNodeImpl(new_token)
                    
                    # Instantiate the 5 levels of boolean contexts...
                    bool_exp4 = C4ChineseParser.BoolExp4Context(None, None)
                    bool_exp3 = C4ChineseParser.BoolExp3Context(None, None)
                    bool_exp2 = C4ChineseParser.BoolExp2Context(None, None)
                    bool_exp1 = C4ChineseParser.BoolExp1Context(None, None)
                    bool_exp  = C4ChineseParser.BoolExpContext(None, None)
                    
                    # Wire bottom-up...
                    new_leaf.parentCtx = bool_exp4
                    bool_exp4.children = [new_leaf]
                    
                    bool_exp4.parentCtx = bool_exp3
                    bool_exp3.children = [bool_exp4]
                    
                    bool_exp3.parentCtx = bool_exp2
                    bool_exp2.children = [bool_exp3]
                    
                    bool_exp2.parentCtx = bool_exp1
                    bool_exp1.children = [bool_exp2]
                    
                    bool_exp1.parentCtx = bool_exp
                    bool_exp.children = [bool_exp1]
                    
                    bool_exp.parentCtx = expr_ctx
                    expr_ctx.children = [bool_exp]

                # 2. Handle Integer Replacement
                elif isinstance(expr_val, int):
                    new_token = CommonToken(type=C4ChineseParser.LT_INT)
                    new_token.text = str(expr_val)
                    new_leaf = TerminalNodeImpl(new_token)
                    
                    num_exp2 = C4ChineseParser.NumExp2Context(None, None)
                    num_exp1 = C4ChineseParser.NumExp1Context(None, None)
                    num_exp  = C4ChineseParser.NumExpContext(None, None)
                    
                    new_leaf.parentCtx = num_exp2
                    num_exp2.children = [new_leaf]
                    
                    num_exp2.parentCtx = num_exp1
                    num_exp1.children = [num_exp2]
                    
                    num_exp1.parentCtx = num_exp
                    num_exp.children = [num_exp1]
                    
                    num_exp.parentCtx = expr_ctx
                    expr_ctx.children = [num_exp]
                    
                # 3. Handle Float Replacement
                elif isinstance(expr_val, float):
                    new_token = CommonToken(type=C4ChineseParser.LT_FLOAT)
                    new_token.text = str(expr_val)
                    new_leaf = TerminalNodeImpl(new_token)
                    
                    float_wrap = C4ChineseParser.FloatWrapperContext(None, None)
                    num_exp2 = C4ChineseParser.NumExp2Context(None, None)
                    num_exp1 = C4ChineseParser.NumExp1Context(None, None)
                    num_exp  = C4ChineseParser.NumExpContext(None, None)
                    
                    new_leaf.parentCtx = float_wrap
                    float_wrap.children = [new_leaf]
                    
                    float_wrap.parentCtx = num_exp2
                    num_exp2.children = [float_wrap]
                    
                    num_exp2.parentCtx = num_exp1
                    num_exp1.children = [num_exp2]
                    
                    num_exp1.parentCtx = num_exp
                    num_exp.children = [num_exp1]
                    
                    num_exp.parentCtx = expr_ctx
                    expr_ctx.children = [num_exp]

                # 4. Handle String Replacement
                elif isinstance(expr_val, str):
                    new_token = CommonToken(type=C4ChineseParser.LT_STR)
                    new_token.text = f'"{expr_val}"' # Add quotes back
                    new_leaf = TerminalNodeImpl(new_token)
                    
                    str_wrap = C4ChineseParser.StringWrapperContext(None, None)
                    str_base = C4ChineseParser.StrBaseContext(None, None)
                    str_exp  = C4ChineseParser.StrExpContext(None, None)
                    
                    new_leaf.parentCtx = str_wrap
                    str_wrap.children = [new_leaf]
                    
                    str_wrap.parentCtx = str_base
                    str_base.children = [str_wrap]
                    
                    str_base.parentCtx = str_exp
                    str_exp.children = [str_base]
                    
                    str_exp.parentCtx = expr_ctx
                    expr_ctx.children = [str_exp]

        return None

    def visitNumExp(self, ctx):

        result = self.visit(ctx.numExp1(0))
        if result is None:
            return None
            
        for i in range(1, len(ctx.numExp1())):
            
            next_val = self.visit(ctx.numExp1(i))
            if next_val is None:
                return None
                
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
        
    def visitNumExp1(self, ctx):
        result = self.visit(ctx.numExp2(0))
        
        if result is None:
            return None
            
        for i in range(1, len(ctx.numExp2())):
            
            next_val = self.visit(ctx.numExp2(i))
            if next_val is None:
                return None
                
            op_type = ctx.getChild(2 * i - 1).getSymbol().type
            if op_type == C4ChineseParser.MULT:
                result *= next_val
            elif op_type == C4ChineseParser.DIV:
                if next_val == 0:
                    return None
                result /= next_val
            elif op_type == C4ChineseParser.MOD:
                if next_val == 0:
                    return None
                result %= next_val
                
        return result

    def visitNumExp2(self, ctx: C4ChineseParser.NumExp2Context):
        if ctx.numExp():
            return self.visit(ctx.numExp())
        if ctx.charWrapper():
            return ctx.charWrapper().getText().strip("'")
        if ctx.floatWrapper():
            return float(ctx.floatWrapper().getText())
        if ctx.LT_INT():
            return int(ctx.LT_INT().getText())

        if ctx.INC() or ctx.DEC():
            # 1. Find the variable being mutated
            ref_node = ctx.numRef() if ctx.numRef() else ctx.numId() # Fallback just in case
            ref_name = ref_node.getText()
            base_var_name = ref_name.split('[')[0].split('.')[0]
            
            # 2. Strip its constant value so the optimizer leaves it alone downstream!
            sym = self.symbol_table.resolve(base_var_name)
            if sym:
                sym.val = None
                
            # 3. Return None to stop constant propagation for this expression
            return None
            
        if ctx.numRef():
            ref_name = ctx.numRef().getText()
            symbol = self.symbol_table.current_scope.resolve(ref_name)
            
            if symbol:
                val = symbol.val
                if val is not None:
                    ref_node = ctx.numRef()
                    new_val_str = str(val)
                    
                    if symbol.type.name == "int":
                        new_token_type = C4ChineseParser.LT_INT
                    elif symbol.type.name == "float":
                        new_token_type = C4ChineseParser.LT_FLOAT
                    elif symbol.type.name == "bool":
                        new_token_type = C4ChineseParser.LT_BOOL
                        new_val_str = 'zhen' if val else 'buzhen'
                    elif symbol.type.name == "string":
                        new_token_type = C4ChineseParser.LT_STR
                        new_val_str = f'"{val}"'  # Ensure quotes are added back for strings..
                    elif symbol.type.name == "char":
                        new_token_type = C4ChineseParser.LT_CHAR
                        new_val_str = f"'{val}'"  # Ensure quotes are added back for chars..
                        
                        
                    new_token = CommonToken(type=new_token_type)
                    new_token.text = new_val_str
                    new_leaf = TerminalNodeImpl(new_token)
                    
                    # SCENARIO A: IT IS A NUMBER (Int / Float)
                    # Safe to replace in-place inside the numExp2 node...
                    if symbol.type.name == "int":
                        new_leaf.parentCtx = ctx
                        idx = ctx.children.index(ref_node)
                        ctx.children[idx] = new_leaf
                        
                    elif symbol.type.name == "float":
                        float_wrap = C4ChineseParser.FloatWrapperContext(None, None)
                        new_leaf.parentCtx = float_wrap
                        float_wrap.children = [new_leaf]
                        
                        float_wrap.parentCtx = ctx
                        idx = ctx.children.index(ref_node)
                        ctx.children[idx] = float_wrap
                        
                    elif symbol.type.name == "char":
                        char_wrap = C4ChineseParser.CharWrapperContext(None, None)
                        new_leaf.parentCtx = char_wrap
                        char_wrap.children = [new_leaf]
                        
                        char_wrap.parentCtx = ctx
                        idx = ctx.children.index(ref_node)
                        ctx.children[idx] = char_wrap

                    # SCENARIO B: IT IS A STRING OR BOOL
                    # Climb up the tree and replace the entire numExp branch...
                    else:
                        # 1. Traverse upwards to find the ExpressionContext...
                        current = ctx
                        top_num_exp = None
                        expr_ctx = None
                        
                        while current.parentCtx is not None:
                            if isinstance(current.parentCtx, C4ChineseParser.ExpressionContext):
                                top_num_exp = current
                                expr_ctx = current.parentCtx
                                break
                            current = current.parentCtx
                            
                        # 2. Re-wire the AST branch ONLY if it's safe!
                        # If this variable is part of a larger operation (e.g., str4 + str3),
                        # replacing the top expression here would corrupt the AST and delete the other operands.
                        is_safe_to_replace = (top_num_exp is not None) and (top_num_exp.getText() == ctx.getText())
                        
                        if expr_ctx and top_num_exp and is_safe_to_replace and (top_num_exp in expr_ctx.children):
                            
                            # --- BOOLEAN AST RE-WIRING ---
                            if symbol.type.name == "bool":
                                bool_exp4 = C4ChineseParser.BoolExp4Context(None, None)
                                bool_exp3 = C4ChineseParser.BoolExp3Context(None, None)
                                bool_exp2 = C4ChineseParser.BoolExp2Context(None, None)
                                bool_exp1 = C4ChineseParser.BoolExp1Context(None, None)
                                bool_exp  = C4ChineseParser.BoolExpContext(None, None)
                                
                                new_leaf.parentCtx = bool_exp4
                                bool_exp4.children = [new_leaf]
                                bool_exp4.parentCtx = bool_exp3
                                bool_exp3.children = [bool_exp4]
                                bool_exp3.parentCtx = bool_exp2
                                bool_exp2.children = [bool_exp3]
                                bool_exp2.parentCtx = bool_exp1
                                bool_exp1.children = [bool_exp2]
                                bool_exp1.parentCtx = bool_exp
                                bool_exp.children = [bool_exp1]
                                
                                bool_exp.parentCtx = expr_ctx
                                
                                # Replace the old numExp with the new boolExp...
                                idx = expr_ctx.children.index(top_num_exp)
                                expr_ctx.children[idx] = bool_exp
                                
                            # --- STRING AST RE-WIRING ---
                            elif symbol.type.name == "string":
                                str_wrap = C4ChineseParser.StringWrapperContext(None, None)
                                str_base = C4ChineseParser.StrBaseContext(None, None)
                                str_exp  = C4ChineseParser.StrExpContext(None, None)
                                
                                new_leaf.parentCtx = str_wrap
                                str_wrap.children = [new_leaf]
                                str_wrap.parentCtx = str_base
                                str_base.children = [str_wrap]
                                str_base.parentCtx = str_exp
                                str_exp.children = [str_base]
                                
                                str_exp.parentCtx = expr_ctx
                                
                                # Replace the old numExp with the new strExp...
                                idx = expr_ctx.children.index(top_num_exp)
                                expr_ctx.children[idx] = str_exp

                    if symbol.type.name == 'int':
                        return int(val)
                    elif symbol.type.name == 'float':
                        return float(val)
                    elif symbol.type.name == 'bool':
                        return bool(val)
                    elif symbol.type.name == 'string':
                        return str(val)
                    elif symbol.type.name == 'char':
                        return str(val)
                        
        return None

    def visitStrExp(self, ctx):
        result = self.visit(ctx.strBase(0))
        
        if result is None:
            return None
            
        for i in range(1, len(ctx.strBase())):
            next_val = self.visit(ctx.strBase(i))
            if next_val is None:
                return None
                
            op_type = ctx.getChild(2 * i - 1).getSymbol().type
            if op_type == C4ChineseParser.ADD:
                result += str(next_val)
                
        return result

    def visitStrBase(self, ctx):
            
        if ctx.stringWrapper():
            return ctx.stringWrapper().getText().strip('"')
            
        if ctx.charWrapper():
            return ctx.charWrapper().getText().strip("'")

        if ctx.strVal():
            ref_name = ctx.strVal().getText()
            symbol = self.symbol_table.current_scope.resolve(ref_name)
            
            if symbol:
                val = symbol.val
                if val is not None:
                    ref_node = ctx.strVal()

                    # 1. Create the new string token...
                    new_token = CommonToken(type=C4ChineseParser.LT_STR)
                    new_token.text = f'"{val}"'
                    new_leaf = TerminalNodeImpl(new_token)
                    
                    # 2. Wrap it legally in a StringWrapperContext...
                    str_wrap = C4ChineseParser.StringWrapperContext(None, None)
                    new_leaf.parentCtx = str_wrap
                    str_wrap.children = [new_leaf]
                    
                    # 3. Safely swap the strVal node with the new stringWrapper node...
                    str_wrap.parentCtx = ctx
                    idx = ctx.children.index(ref_node)
                    ctx.children[idx] = str_wrap

                    return str(val)

        return None
    
    def visitBoolExp(self, ctx):
        result = self.visit(ctx.boolExp1(0))
        if result is None:
            return None
            
        for i in range(1, len(ctx.boolExp1())):
            # Short-circuit OR: If result is already True, no need to evaluate the rest...
            if result is True:
                return True
                
            next_val = self.visit(ctx.boolExp1(i))
            if next_val is None:
                return None
                
            op_type = ctx.getChild(2 * i - 1).getSymbol().type
            if op_type == C4ChineseParser.OR:
                result = result or next_val
                
        return bool(result)

    def visitBoolExp1(self, ctx):
        result = self.visit(ctx.boolExp2(0))
        if result is None:
            return None
            
        for i in range(1, len(ctx.boolExp2())):

            # Short-circuit AND: If result is already False, no need to evaluate the rest...
            if result is False:
                return False
                
            next_val = self.visit(ctx.boolExp2(i))
            if next_val is None:
                return None
                
            op_type = ctx.getChild(2 * i - 1).getSymbol().type
            if op_type == C4ChineseParser.AND:
                result = result and next_val
                
        return bool(result)

    def visitNullExp(self, ctx):
        return None

    def visitBoolExp2(self, ctx):
        
        # Check if this is the 3rd alternative: boolExp3 (EQ|NEQ boolExp3)*
        if ctx.boolExp3():
            result = self.visit(ctx.boolExp3(0))
            if result is None:
                return None
                
            for i in range(1, len(ctx.boolExp3())):
                next_val = self.visit(ctx.boolExp3(i))
                if next_val is None:
                    return None
                    
                op_type = ctx.getChild(2 * i - 1).getSymbol().type
                if op_type == C4ChineseParser.EQ:
                    result = (result == next_val)
                elif op_type == C4ChineseParser.NEQ:
                    result = (result != next_val)
            return result

        left = self.visit(ctx.getChild(0))
        right = self.visit(ctx.getChild(2))

        if left is None or right is None:
            return None
        
        # Get the operator token type...
        op_type = ctx.getChild(1).getSymbol().type
        
        if op_type == C4ChineseParser.EQ:
            return left == right
        elif op_type == C4ChineseParser.NEQ:
            return left != right
            
        return None

    def visitBoolExp3(self, ctx):
        if ctx.boolExp4():
            return self.visit(ctx.boolExp4())
            
        left = self.visit(ctx.getChild(0))
        right = self.visit(ctx.getChild(2))
        
        if left is None or right is None:
            return None
            
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

    def visitBoolExp4(self, ctx):
        if ctx.boolExp():
            return self.visit(ctx.boolExp())
            
        if ctx.NOT():
            val = self.visit(ctx.boolExp4())
            if val is None:
                return None
            return not val
            
        if ctx.LT_BOOL():
            text = ctx.LT_BOOL().getText().lower()
            return text == 'zhen' or text == "真"
        
        if ctx.boolVal():
            ref_name = ctx.boolVal().getText()
            symbol = self.symbol_table.current_scope.resolve(ref_name)
            if symbol:
                val = symbol.val
                if val is not None:
                    ref_node = ctx.boolVal()

                    new_token = CommonToken(
                        type=C4ChineseParser.LT_BOOL
                    )
                    new_token.text = "zhen" if val else "buzhen"
                    
                    new_leaf = TerminalNodeImpl(new_token)
                    new_leaf.parentCtx = ctx
                    
                    idx = ctx.children.index(ref_node)
                    ctx.children[idx] = new_leaf

                    return int(val)

        return None
    
    def visitForStat(self, ctx: C4ChineseParser.ForStatContext):
        self.symbol_table.enter_next_block()

        if ctx.varDeclFor():
            self.visit(ctx.varDeclFor())
        elif ctx.assignStat():
            self.visit(ctx.assignStat())

        mutated = set()
        self._find_mutated_variables(ctx.statement(), mutated)
        self._find_mutated_variables(ctx.assignStatNoEnd(), mutated)

        for var_name in mutated:
            sym = self.symbol_table.resolve(var_name)
            if sym:
                sym.val = None

        self.visit(ctx.expression())
        self.visit(ctx.statement())
        self.visit(ctx.assignStatNoEnd())

        for var_name in mutated:
            sym = self.symbol_table.resolve(var_name)
            if sym:
                sym.val = None

        self.symbol_table.exit_scope()
        return None
    
    def _find_mutated_variables(self, ctx, mutated_vars: set):

        if not ctx:
            return
        
        # 1. Check for standard assignments (e.g., counter = ...)
        if isinstance(ctx, C4ChineseParser.AssignStatContext) or isinstance(ctx, C4ChineseParser.AssignStatNoEndContext):
            lhs_text = ctx.assignableVal().getText()
            # Strip array brackets and struct dots to get the root variable name...
            base_var_name = lhs_text.split('[')[0].split('.')[0]
            mutated_vars.add(base_var_name)
            
        # 2. Check for INPUT statements (e.g., geiwo(counter))...
        if isinstance(ctx, C4ChineseParser.StatInputContext):
            for assignable in ctx.assignableVal():
                lhs_text = assignable.getText()
                base_var_name = lhs_text.split('[')[0].split('.')[0]
                mutated_vars.add(base_var_name)

        # 3. Check for Increment / Decrement Mutations...
        if isinstance(ctx, C4ChineseParser.NumExp2Context):
            if ctx.INC() or ctx.DEC():
                lhs_text = ctx.numRef().getText()
                base_var_name = lhs_text.split('[')[0].split('.')[0]
                mutated_vars.add(base_var_name)
                
        # 3. Recursively search all nested blocks/children...
        if hasattr(ctx, 'getChildren'):
            for child in ctx.getChildren():
                self._find_mutated_variables(child, mutated_vars)
    
    def visitWhileStat(self, ctx: C4ChineseParser.WhileStatContext):
        # 1. Look ahead and find every variable that changes inside this loop...
        mutated = set()
        self._find_mutated_variables(ctx.statement(), mutated)
        
        # 2. Invalidate their constant values so the optimizer leaves them alone...
        for var_name in mutated:
            sym = self.symbol_table.resolve(var_name)
            if sym:
                sym.val = None  # Strip the constant value!
                
        # 3. Now, safe to optimize the condition and the loop body...
        self.visit(ctx.expression())
        
        # Now, just visit the statement directly...
        # If it's a { } block, visitStatBlock will safely handle the scope for us...
        self.visit(ctx.statement())
        
        return None
    
    def visitForStat(self, ctx: C4ChineseParser.ForStatContext):
        # 1. Sync the For loop's outer wrapper scope...
        self.symbol_table.enter_next_block()

        # 2. Visit initialization FIRST (so 'i = 0' gets registered)...
        if ctx.varDeclFor():
            self.visit(ctx.varDeclFor())
        elif ctx.assignStat():
            self.visit(ctx.assignStat())

        # 3. Look ahead to find mutations in BOTH the body and the incrementor...
        mutated = set()
        self._find_mutated_variables(ctx.statement(), mutated)
        self._find_mutated_variables(ctx.assignStatNoEnd(), mutated)

        # 4. Invalidate their constant values...
        for var_name in mutated:
            sym = self.symbol_table.resolve(var_name)
            if sym:
                sym.val = None

        # 5. Visit the rest safely (visitStatBlock will handle the {} body scope)...
        self.visit(ctx.expression())
        self.visit(ctx.statement())
        self.visit(ctx.assignStatNoEnd())

        # 6. Exit the outer wrapper scope...
        self.symbol_table.exit_scope()
        
        return None
    
    def visitRepeatUntilStat(self, ctx: C4ChineseParser.RepeatUntilStatContext):
        mutated = set()
        self._find_mutated_variables(ctx.statement(), mutated)

        for var_name in mutated:
            sym = self.symbol_table.resolve(var_name)
            if sym:
                sym.val = None

        self.visit(ctx.statement())
        self.visit(ctx.expression())

        for var_name in mutated:
            sym = self.symbol_table.resolve(var_name)
            if sym:
                sym.val = None

        return None
    
    def visitIfStat(self, ctx: C4ChineseParser.IfStatContext):
        mutated = set()
        self._find_mutated_variables(ctx, mutated)

        for var_name in mutated:
            sym = self.symbol_table.resolve(var_name)
            if sym:
                sym.val = None

        self.visit(ctx.expression())
        self.visit(ctx.statement())
        
        if ctx.elifList():
            self.visit(ctx.elifList())

        # Re-invalidate AFTER again...
        for var_name in mutated:
            sym = self.symbol_table.resolve(var_name)
            if sym:
                sym.val = None

        return None

    def visitElifList(self, ctx: C4ChineseParser.ElifListContext):
        # The variables were already invalidated by visitIfStat, 
        # so we just need to navigate the tree...
        if ctx.ELIF():
            self.visit(ctx.expression())
            self.visit(ctx.statement())
            
            if ctx.elifList():
                self.visit(ctx.elifList())
                
        elif ctx.ELSE():
            self.visit(ctx.statement())
            
        return None