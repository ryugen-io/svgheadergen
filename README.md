# SVG Header Generator

A high-performance SVG header generator built in Mojo that converts ASCII art into pixel-perfect SVG graphics with customizable gradient fills.

## Features

- 🚀 **Blazing Fast**: Written in Mojo for maximum performance
- 🎨 **Gradient Support**: Built-in color gradient presets
- 🔤 **Multiple Fonts**: Works with figlet/toilet fonts
- 🎯 **Two Rendering Modes**: Pixel mode for simple fonts, text mode for Unicode
- 📦 **Zero Dependencies**: Standalone binary (when compiled)
- 🐍 **Python Fallback**: Includes Python implementation for compatibility

## Installation

### Prerequisites

- [Mojo](https://www.modular.com/mojo) (for Mojo implementation)
- [Pixi](https://prefix.dev/docs/pixi/overview) (for dependency management)
- `figlet` and/or `toilet` (for ASCII art rendering)

```bash
# Install figlet/toilet on most Linux distros
sudo pacman -S figlet toilet  # Arch
sudo apt install figlet toilet  # Debian/Ubuntu
```

### Setup

```bash
# Clone the repository
git clone git@github.com:ryugen-io/svgheadergen.git
cd svgheadergen

# Install dependencies with pixi
pixi install

# Build the binary (optional)
just build
# or: mojo build svg_gen.mojo -o svg_gen
```

## Usage

### Basic Usage

```bash
# Using Mojo directly
mojo svg_gen.mojo "Hello World"

# Using compiled binary
./svg_gen "Hello World"

# Using Python fallback
python3 svg_gen.py "Hello World"
```

### With Options

```bash
# Specify output file and font
mojo svg_gen.mojo "Hello" -o header.svg -f banner3

# Use text mode with custom gradient
mojo svg_gen.mojo "World" -f future -t -g cyber_cyan

# Custom scale
mojo svg_gen.mojo "Test" -s 15
```

### Using Just

```bash
# Run with justfile shortcuts
just run "My Text"
just pixel "Hello" -f big
just text "Future" -g sunset

# Build and benchmark
just build
just benchmark
```

## Rendering Modes

### Pixel Mode (Default)

Converts ASCII art characters to SVG path rectangles. Best for fonts using simple characters like `#`:
- `banner3`
- `big`
- `standard`

```bash
mojo svg_gen.mojo "Hello" -f banner3
```

### Text Mode

Uses toilet's native SVG export. Best for fonts using Unicode box-drawing characters:
- `future`
- `pagga`

```bash
mojo svg_gen.mojo "Hello" -f future -t
```

## Command Line Options

```
Usage: svg_gen.mojo [TEXT] [OPTIONS]

Arguments:
  TEXT              The text to render

Options:
  -o, --output      Output SVG file path (default: stdout)
  -f, --font        Figlet/toilet font name (default: banner3)
  -s, --scale       Scale factor for pixel mode (default: 10)
  -g, --gradient    Gradient preset name
  -t, --text-mode   Use text mode instead of pixel mode
  -h, --help        Show this help message
```

## Performance

The Mojo implementation is significantly faster than the Python version:

```bash
just benchmark
```

Typical results show ~10-100x speedup for the Mojo implementation depending on the operation.

## Development

```bash
# Format code
just fmt

# Run static checks
just check

# Clean build artifacts
just clean
```

## Project Structure

```
.
├── svg_gen.mojo           # Main Mojo implementation
├── svg_gen.py             # Python fallback implementation
├── plot_benchmark.mojo    # Benchmarking utilities
├── justfile               # Task automation
├── pixi.toml              # Pixi environment config
└── README.md              # This file
```

## License

MIT

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.
