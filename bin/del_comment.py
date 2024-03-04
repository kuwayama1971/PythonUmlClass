#!/usr/bin/env python3

import sys
import ast
import astor
import pprint

def remove_comments_from_code(code):
    # コードをASTに変換
    tree = ast.parse(code)

    #print("----------")
    #print(ast.dump(tree, indent=4))
    #print("----------")

    # ASTを操作してコメントを削除
    for node in ast.walk(tree):

        #print(vars(node))
        #print("--------------------------------------------------")
        #pprint.pprint(vars(node))
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Str) and isinstance(node.value.s, str):
            # 文字列としてコメントが格納されているExprノードを削除
            if node.value.s.startswith(("#", '"""', "'''")):
                node.value.s = ""  # コメントを空文字列に設定

    # ASTからコードに変換
    modified_code = astor.to_source(tree)

    return modified_code

if __name__ == "__main__":
    file = sys.argv[1]
    f = open(file, "r")
    code_without_comments = remove_comments_from_code(f.read())
    print(code_without_comments)
