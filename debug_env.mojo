from python import Python

def main():
    try:
        var sys = Python.import_module("sys")
        print("--- Mojo Python Environment ---")
        print("Executable:", sys.executable)
        print("Path:")
        var path = sys.path
        for p in path:
            print(p)
    except e:
        print("Error:", e)
