parser grammar C4ChineseParser;

options { tokenVocab = C4ChineseLexer; }

/* PROGRAM STRUCTURE */

program
    : mainList mainFunc EOF
    ;

mainList
    : (typedefItem | globalDecl | panicMode)*
    ;

globalDecl
    : funcDecl | constDecl | recordDecl | varDecl
    ;

mainFunc
    : (dataType | VOID) KW_MAIN LPAR paramList RPAR LBRACE funcContent RBRACE
    ;

typedefItem
    : TYPEDEF (dataType | recordDecl) idWrapper SEMICOLON
    ;

/* DECLARATIONS */

constDecl
    : CONST dataType idWrapper (ASSIGN expression)? SEMICOLON
    ;

varDecl
    : dataType idWrapper (ASSIGN expression)? SEMICOLON
    ;

varDeclFor
    : dataType idWrapper (ASSIGN expression)? SEMICOLON
    ;

dataType
    : KW_INT                            # TypeInteger
    | KW_FLOAT                          # TypeFloat
    | KW_CHAR                           # TypeChar
    | KW_STR                            # TypeString
    | KW_BOOL                           # TypeBoolean
    | recordDecl                        # TypeRecord
    | idWrapper                         # TypeIdentifier
    | dataType DE_REF                   # TypePointer
    | dataType LBAR LT_INT RBAR         # TypeArray
    ;

recordDecl
    : KW_RECORD idWrapper? LBRACE recordContent RBRACE SEMICOLON
    ;

recordContent
    : (varDecl | recordDecl)*
    ;

/* FUNCTIONS */

funcDecl
    : funcRet 
    | funcVoid
    ;

funcRet
    : dataType idWrapper LPAR paramList RPAR LBRACE funcContent RBRACE
    ;

funcVoid
    : VOID idWrapper LPAR paramList RPAR LBRACE funcContent RBRACE
    ;

paramList
    : (dataType idWrapper (COMMA dataType idWrapper)*)?
    ;

funcContent
    : (statement | panicMode)*
    ;

/* STATEMENTS */

statement
    : expression SEMICOLON                                      # StatExp
    | funcCall SEMICOLON                                        # StatFuncCall
    | assignStat                                                # StatAssign
    | ifStat                                                    # StatIf
    | whileStat                                                 # StatWhile
    | repeatUntilStat                                           # StatRepeat
    | forStat                                                   # StatFor
    | returnStat                                                # StatReturn
    | LBRACE statement* RBRACE                                  # StatBlock
    | PRINT LPAR expression RPAR SEMICOLON                      # StatPrint
    | INPUT LPAR assignableVal (COMMA assignableVal)* RPAR SEMICOLON  # StatInput
    | BREAK SEMICOLON                                           # StatBreak
    | CONT SEMICOLON                                            # StatContinue
    | varDecl                                                   # StatVarDecl
    | constDecl                                                 # StatConstDecl
    ;

assignStat
    : assignableVal ASSIGN expression SEMICOLON
    ;

assignStatNoEnd
    : assignableVal ASSIGN expression
    ;

returnStat
    : RET expression? SEMICOLON
    ;

/* CONTROL FLOW */

ifStat
    : IF LPAR expression RPAR statement elifList?
    ;

elifList
    : ELIF LPAR expression RPAR statement elifList
    | ELSE statement
    ;

forStat
    : FOR LPAR varDeclFor expression SEMICOLON assignStatNoEnd RPAR statement
    | FOR LPAR assignStat expression SEMICOLON assignStatNoEnd RPAR statement
    ;

whileStat
    : WHILE LPAR expression RPAR statement
    ;

repeatUntilStat
    : REPEAT statement UNTIL LPAR expression RPAR SEMICOLON
    ;

/* GENERAL EXPRESSIONS */

expression
    : numExp
    | strExp
    | boolExp
    | funcCall
    | deRefVal
    | arrayInitExp 
    | nullExp
    ;

arrayInitExp
    : LBRACE expList RBRACE
    ;

/* <EXP_LIST> */
expList
    : (expression (COMMA expression)*)?
    ;

/* NULL EXP */
nullExp
    : NULL
    ;

/* <REF_VAL> -> <ID><REF_VAL'> 
   Handles 'variable', 'array[index]', and 'struct.member'
*/
refVal
    : idWrapper refValPrime
    ;

refValPrime
    : LBAR numExp RBAR refValPrime
    | DOT refVal refValPrime
    | /* epsilon */
    ;

/* <DE_REF_VAL> -> <DE_REF><DE_REF_VAL> | <DE_REF><POINTER_ID> */
deRefVal
    : DE_REF deRefVal
    | DE_REF refVal
    ;

pointerId
    : idWrapper
    ;


/* NUMERICAL EXPRESSIONS */

numExp
    : numExp1 ( (ADD | SUB) numExp1 )*
    ;

numExp1
    : numExp2 ( (MULT | DIV | MOD) numExp2 )*
    ;
    
numExp2
    : LPAR numExp RPAR
    | charWrapper
    | LT_INT
    | floatWrapper
    | INC numRef   /* Pre-increment */
    | DEC numRef   /* Pre-decrement */
    | numRef INC   /* Post-increment */
    | numRef DEC   /* Post-decrement */
    | numRef
    | REF refVal
    | deRefVal
    | funcCall
    ;

assignableVal
    : deRefVal
    | refVal
    ;

numId
    : idWrapper
    ;

numRef
    : refVal
    ;

/* STRING EXPRESSIONS */

strExp
    : strBase (ADD strBase)*
    ;

strBase
    : strVal
    | stringWrapper
    | charWrapper
    | funcCall
    | deRefVal
    | LPAR strExp RPAR
    ;

strVal
    : refVal
    ;

/* BOOLEAN EXPRESSIONS */
boolExp
    : boolExp1 (OR boolExp1)*
    ;

boolExp1
    : boolExp2 (AND boolExp2)*
    ;

boolExp2
    : (numExp|nullExp) (EQ | NEQ) (numExp|nullExp)
    | (strExp|nullExp) (EQ | NEQ) (strExp|nullExp)
    | boolExp3 ( (EQ | NEQ) boolExp3 )*
    ;

boolExp3
    : numExp (LT | GT | LTE | GTE) numExp
    | strExp (LT | GT | LTE | GTE) strExp
    | boolExp4                           
    ;

boolExp4
    : LPAR boolExp RPAR
    | NOT boolExp4
    | boolVal
    | LT_BOOL
    | funcCall
    | deRefVal
    ;

boolVal
    : refVal
    ;

funcCall
    : idWrapper LPAR argList RPAR
    ;

argList
    : (expression (COMMA expression)*)?
    ;

idWrapper
    : ID                # ValidID
    | ERROR_ID          # ErrorID
    ;

floatWrapper
    : LT_FLOAT          # ValidFloat
    | ERROR_FLOAT       # ErrorFloat
    ;

stringWrapper
    : LT_STR             # ValidString
    | ERROR_STRING       # ErrorString
    ;

charWrapper
    : LT_CHAR               # ValidChar
    | ERROR_CHAR            # ErrorChar
    | ERROR_CHAR_2          # ErrorChar2
    ;

panicMode
    : ~(RBRACE | EOF | KW_MAIN) .*? SEMICOLON
    ;