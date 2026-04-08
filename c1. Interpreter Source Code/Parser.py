from antlr4 import *

from C4ChineseLexer import C4ChineseLexer
from C4ChineseParser import C4ChineseParser
from CheckingVisitor import CheckingVisitor

from antlr4.tree.Tree import TerminalNodeImpl

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

def check_for_hidden_errors(token_stream):
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BOLD = '\033[1m'
    RESET = '\033[0m'
    
    token_stream.fill()

    all_tokens = token_stream.tokens 

    for token in all_tokens:
        if token.type == C4ChineseLexer.ERROR_MULTI_COMMENT:
            print(f"{RED}{BOLD}Lexer Error{RESET} at Line {YELLOW}{token.line}{RESET}: "
                  f"Unclosed multi-line comment found.")
            
        elif token.type == C4ChineseLexer.ERROR_CATCHER:
            print(f"{RED}{BOLD}Lexer Error{RESET} at Line {YELLOW}{token.line}{RESET}, Column {YELLOW}{token.column}{RESET}: "
                  f"Unrecognized token '{RED}{token.text}{RESET}' found.")

def parse(input_file, p=False):
    input_stream = FileStream(input_file, encoding='utf-8')

    lexer = C4ChineseLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = C4ChineseParser(stream)
    tree = parser.program()

    # print("--- Parse Tree ---")
    pretty_print(tree, parser) if p else None

    visitor = CheckingVisitor()
    visitor.visit(tree)

    check_for_hidden_errors(stream)

    if p:
        print()
        visitor.symbol_table.print_contents()
        # visitor.symbol_table.print_variable_stats()

    errors = False

    if visitor.parser_error_count > 0:  
        print(f"{visitor.parser_error_count} parser error(s) found.")
        errors = True
    if visitor.semantic_error_count > 0:
        print(f"{visitor.semantic_error_count} semantic error(s) found.")
        errors = True
    if visitor.scope_error_count > 0:
        print(f"{visitor.scope_error_count} scope error(s) found.")
        errors = True

    if errors:
        return None
    else:
        return tree, parser, visitor.symbol_table