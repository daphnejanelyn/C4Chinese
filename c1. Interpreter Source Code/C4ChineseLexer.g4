lexer grammar C4ChineseLexer;

/* Boolean / Constants */
LT_BOOL     : 'zhen' | 'buzhen' | '真' | '不真';
NULL        : 'meiyou' | '没有' | '沒有';
CONST       : 'yongyuan' | '永远' | '永遠';

/* Control Flow */
IF          : 'ruguo' | '如果' ;
ELSE        : 'xiayige' | '下一个' | '下一個' ;
ELIF        : 'xiayigeruguo' | '下一个如果' | '下一個如果' ;
WHILE       : 'buduanruguo' | '不断如果' | '不斷如果' ;
REPEAT      : 'laiyibian' | '来一遍' | '來一遍' ;
UNTIL       : 'dao' | '到' ;
FOR         : 'buduan' | '不断' | '不斷' ;
RET         : 'huijia' | '回家' ;
BREAK       : 'ting' | '停' ;
CONT        : 'buting' | '不停' ;

/* Datatypes / Variables */
KW_INT      : 'hao' | '号' | '號' ;
KW_FLOAT    : 'erhao' | '二号' | '二號' ;
KW_CHAR     : 'pinyin' | '拼音' ;
KW_STR      : 'duopinyin' | '多拼音' ;
KW_BOOL     : 'zhende' | '真的' ;
KW_RECORD   : 'yinyue' | '音乐' | '音樂' ;
KW_MAIN     : 'main' | 'zhuyao' | '主要' ;
TYPEDEF     : 'yisi' | '意思' ;
VOID        : 'gan' | '干' | '乾' ;

/* Input / Output */
INPUT       : 'geiwo' | '给我' | '給我' ;
PRINT       : 'geini' | '给你' | '給你' ;

/* OPERATORS */

INC         : 'jiajia' | '++' | '加加' ;
DEC         : 'fufu' | '--' | '负负' | '負負' ;

GTE         : 'duozhege' | '>=' | '多这个' | '多這個' ;
LTE         : 'xiaozhege' | '<=' | '小这个' | '小這個' ;

EQ          : 'zhege' | '==' | '这个' | '這個' ;
NEQ         : 'buzhege' | '!=' | '不这个' | '不這個' ;

ADD         : 'jia' | '+' | '加' ;
SUB         : 'fu' | '-' | '负' | '負' ;
MULT        : 'duojia' | '*' | '多加' ;
DIV         : 'duofu' | '/' | '多负' | '多負' ;
MOD         : 'xialai' | '%' | '下来' | '下來' ;

ASSIGN      : 'shi' | '=' | '是' ;

LT          : 'xiao' | '<' | '小' ;
GT          : 'duo' | '>' | '多' ;

AND         : 'HE' | '&&' | '和' ;
OR          : 'HAI' | '||' | '还' | '還' ;
NOT         : 'LING' | '!' | '零' ;

/* DELIMITERS */

LPAR        : '(' ;
RPAR        : ')' ;
LBAR        : '[' ;
RBAR        : ']' ;
LBRACE      : '{' ;
RBRACE      : '}' ;
SEMICOLON   : ';' ;
COMMA       : ',' ;
REF         : '&' ;
DE_REF      : '^' ;
DOT         : '.' ;

/* LITERALS */

LT_FLOAT    : '-'? [0-9]+ '.' [0-9]+ ;
ERROR_FLOAT
    : '-'? [0-9]+ '.' [0-9]+ ( '.' [0-9]+ )+
    ;

LT_INT      : '-'? [0-9]+ ;

LT_STR
    : '"' ( ~["\\\r\n] | '\\' . )* '"' 
    ;
ERROR_STRING
    : '"' (~["\\\r\n;}])* EOF?
    ;


LT_CHAR
    : '\'' ( '\\' . | ~['\\\r\n] ) '\''
    ;
ERROR_CHAR 
    : '\'' (~['\r\n;}])* ;
ERROR_CHAR_2
    : '\'' ( '\\' . | ~['\\\r\n] ) ( '\\' . | ~['\\\r\n] )+ '\''
    ;

/* IDENTIFIER */

ID          : [a-zA-Z][a-zA-Z0-9_]* ;
ERROR_ID    : [0-9_][a-zA-Z0-9_]* ;

/* COMMENTS & WHITESPACE */

SINGLE_COMMENT
            : '//' ~[\r\n]* -> skip ;

MULTI_COMMENT
            : '/*' .*? '*/' -> skip ; 

ERROR_MULTI_COMMENT
    : '/*' ( ~'*' | '*' ~'/' )* EOF -> channel(HIDDEN)
    ;
    
W           : [ \t\r\n]+ -> skip ;

/* ERROR HANDLING */

ERROR_CATCHER
    : . -> channel(HIDDEN) 
    ;

