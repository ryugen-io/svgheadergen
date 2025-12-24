from python import Python

def main():
    try:
        var json = Python.import_module("json")
        var mpl = Python.import_module("matplotlib")
        mpl.use("Agg")
        var plt = Python.import_module("matplotlib.pyplot")
        var builtins = Python.import_module("builtins")

        # Load data
        print("Loading benchmark data from /tmp/benchmark.json...")
        var f = builtins.open("/tmp/benchmark.json")
        var data = json.load(f)
        f.close()

        print("Processing data...")
        var results = data["results"]
        var commands = Python.list()
        var means = Python.list()
        var stddevs = Python.list()

        for result in results:
            var cmd_str = builtins.str(result["command"])
            # Clean up command names for the plot
            if "svg_gen.py" in cmd_str:
                if "-o" in cmd_str:
                    commands.append("Python (File I/O)")
                else:
                    commands.append("Python (Stdout)")
            elif "./svg_gen" in cmd_str:
                if "-o" in cmd_str:
                    commands.append("Mojo (File I/O)")
                else:
                    commands.append("Mojo (Stdout)")
            else:
                commands.append("Unknown")
            
            means.append(result["mean"])
            stddevs.append(result["stddev"])

        # Plotting
        print("Generating plot...")
        plt.figure(figsize=Python.list(10, 6))
        
        # Create bars
        # Use Python's builtins.range/len so we stay in PythonObject world
        # and don't need to convert to Mojo Ints which can be tricky
        var count = builtins.len(commands)
        var y_pos = builtins.range(count)
        
        var bars = plt.barh(y_pos, means, xerr=stddevs, capsize=5, color="skyblue")
        
        # Styling
        plt.xlabel("Time (seconds)")
        plt.title("Execution Time: Python vs Mojo")
        plt.yticks(y_pos, commands)
        plt.grid(axis="x", linestyle="--", alpha=0.7)
        
        # Add values to bars
        # y_pos is a Python range, iterating it gives PythonObjects
        for i in y_pos:
            var val = means[i]
            var fmt_val = builtins.format(val, ".3f")
            var label = builtins.str("  ") + fmt_val + builtins.str(" s")
            plt.text(val, i, label, va="center")

        plt.tight_layout()
        
        # Save
        var output_file = "benchmark.png"
        plt.savefig(output_file)
        print("Benchmark plot saved to " + output_file)

    except e:
        print("Error occurred while plotting:")
        print(e)
