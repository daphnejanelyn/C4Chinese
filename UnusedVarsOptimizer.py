from C4ChineseParser import C4ChineseParser

class UnusedVarsOptimizer():

    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BOLD = '\033[1m'
    RESET = '\033[0m'
    MAGENTA = '\033[95m'

    def __init__(self, symbol_table):
        self.symbol_table = symbol_table

    def clean_unused_variables(self):        
        # Start the recursive cleaning process from the global scope...
        self._clean_scope(self.symbol_table.global_scope)
        
    def _clean_scope(self, scope):
        symbols_to_remove = []

        for name, sym in scope.symbols.items():
            if type(sym).__name__ == "VarSymbol":
        
                if hasattr(sym, 'struct_assignments'):
                    for assign_text, nodes in sym.struct_assignments.items():
                        
                        # We cannot statically predict dynamic indices like arr[i] vs arr[p].
                        # If it's an array access and the variable is read anywhere, keep it...
                        is_array_access = '[' in assign_text
                        
                        if is_array_access and sym.rhs_counter > 0:
                            is_used = True
                        else:
                            is_used = name in sym.struct_reads or any(
                                r.startswith(assign_text) or assign_text.startswith(r) for r in sym.struct_reads
                            )
                        
                        if not is_used:
                            for ctx in nodes:
                                line = ctx.start.line if hasattr(ctx, 'start') else "Unknown"
                                text = ctx.getText()
                                
                                # Physically remove the node from the AST...
                                if ctx.parentCtx and ctx in ctx.parentCtx.children:
                                    parent = ctx.parentCtx
                                    parent.children.remove(ctx)
                                    
                                    # Clean up the parent StatementContext if it is now empty...
                                    if len(parent.children) == 0 and isinstance(parent, C4ChineseParser.StatementContext):
                                        if parent.parentCtx and parent in parent.parentCtx.children:
                                            parent.parentCtx.children.remove(parent)

                                print(f"{self.YELLOW}Removing{self.RESET} unused field assignment '{self.RED}{assign_text}{self.RESET}' "
                                      f"at Line {self.YELLOW}{line}{self.RESET}: {text}")

                if sym.rhs_counter == 0 and not getattr(sym, 'isparam', False):
                    symbols_to_remove.append(name)
                    
                    for ctx in sym.var_decl_assign_nodes:
                        line = ctx.start.line if hasattr(ctx, 'start') else "Unknown"
                        text = ctx.getText()
                        
                        # Physically remove the node from the AST...
                        if ctx.parentCtx and ctx in ctx.parentCtx.children:
                            parent = ctx.parentCtx
                            parent.children.remove(ctx)

                            # Clean up the parent StatementContext if it is now empty...
                            if len(parent.children) == 0 and isinstance(parent, C4ChineseParser.StatementContext):
                                if parent.parentCtx and parent in parent.parentCtx.children:
                                    parent.parentCtx.children.remove(parent)
                                    
                        print(f"{self.YELLOW}Removing{self.RESET} unused variable '{self.RED}{name}{self.RESET}' "
                              f"at Line {self.YELLOW}{line}{self.RESET}: {text}")
            
            elif hasattr(sym, 'symbols'):
                self._clean_scope(sym)
                
        for name in symbols_to_remove:
            del scope.symbols[name]

        if hasattr(scope, 'blocks'):
            for block in scope.blocks:
                self._clean_scope(block)