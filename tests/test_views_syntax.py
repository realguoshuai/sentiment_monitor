import py_compile
import sys
import traceback

def test_views_syntax():
    print("Testing backend/api/views.py for syntax errors...")
    try:
        py_compile.compile('../backend/api/views.py', doraise=True)
        print("Syntax is OK.")
    except py_compile.PyCompileError as e:
        print("Reproduced Syntax Error:")
        print(e)
        sys.exit(1)

if __name__ == '__main__':
    test_views_syntax()
