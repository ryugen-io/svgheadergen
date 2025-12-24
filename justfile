set shell := ["fish", "-c"]

# Run the Mojo generator (pass args: just run "My Text")
run +args='':
    mojo svg_gen.mojo {{args}}

# Run in Pixel Mode (default)
pixel TEXT *ARGS:
    mojo svg_gen.mojo {{TEXT}} {{ARGS}}

# Run in Text Mode (for 'future' font)
text TEXT *ARGS:
    mojo svg_gen.mojo {{TEXT}} -t {{ARGS}}

# Build the release binary
build:
    mojo build svg_gen.mojo -o svg_gen

# Format all Mojo files
fmt:
    mojo format .

# Run static checks/lints (build without output)
check:
    mojo build svg_gen.mojo -o /dev/null

# Clean up build artifacts
clean:
    rm -f svg_gen

# Show help message
help:
    mojo svg_gen.mojo --help

# Benchmark and Plot
benchmark: build
    @echo "--- Running Benchmarks ---"
    hyperfine --warmup 5 --runs 1000 --prepare 'sync' --export-json /tmp/benchmark.json \
        'python3 svg_gen.py "Test"' \
        './svg_gen "Test"' \
        'python3 svg_gen.py "Test" -o /tmp/bm_py.svg' \
        './svg_gen "Test" -o /tmp/bm_mojo.svg'
    @echo "--- Generating Graph ---"
    pixi run -e default bash -c "export MOJO_PYTHON_LIBRARY=\$(pwd)/.pixi/envs/default/lib/libpython3.so && export PYTHONPATH=\$(pwd)/.pixi/envs/default/lib/python3.14/site-packages:\$(pwd)/.pixi/envs/default/lib/python3.14 && mojo plot_benchmark.mojo"
