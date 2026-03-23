from UnusedVarsOptimizer import UnusedVarsOptimizer
from antlr4.tree.Tree import TerminalNodeImpl
from ConstPropagationOptimizer import ConstPropagationOptimizer

def pretty_print(tree, parser, prefix="", is_last=True):
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    
    if isinstance(tree, TerminalNodeImpl):
        token = tree.getSymbol()
        token_type_idx = token.type
        
        if token_type_idx == -1:
            token_name = "EOF"
        else:
            try:
                token_name = parser.symbolicNames[token_type_idx]
                
                if token_name is None:
                    token_name = parser.literalNames[token_type_idx]
                    
                if token_name is None:
                    token_name = str(token_type_idx)
            except IndexError:
                token_name = "UNKNOWN"

        token_text = token.text.replace("\n", "\\n").replace("\r", "\\r")
        
        node_text = f"{GREEN}{token_name}{RESET} ({CYAN}{token_text}{RESET})"
    
    else:
        rule_index = tree.getRuleIndex()
        rule_name = parser.ruleNames[rule_index]
        node_text = f"{BLUE}{rule_name}{RESET}"

    connector = "└── " if is_last else "├── "
    print(f"{prefix}{connector}{node_text}")
    
    child_prefix = prefix + ("    " if is_last else "│   ")

    count = tree.getChildCount()
    for i in range(count):
        child = tree.getChild(i)
        is_last_child = (i == count - 1)
        pretty_print(child, parser, child_prefix, is_last_child)

def optimize(tree, parser, symbol_table):

    unused_var_optimization = UnusedVarsOptimizer(symbol_table)
    unused_var_optimization.clean_unused_variables()

    #print("Before Optimization")
    #pretty_print(tree, parser)

    #symbol_table.print_contents()

    const_propagation_optimization = ConstPropagationOptimizer(symbol_table)
    const_propagation_optimization.visit(tree)

    #print("After Optimization")
    #pretty_print(tree, parser)

    return tree